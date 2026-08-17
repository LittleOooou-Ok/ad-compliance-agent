"""
批量审核 API 路径
支持上传多个文件，逐条处理，实时进度
"""

import json
import time
import uuid
import shutil
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import List
from agents import Runner, Agent

from backend.review_agents.orchestrator import create_orchestrator
from backend.knowledge.mimo_client import mimo_client

router = APIRouter()

# 文件类型
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".wmv"}
TEXT_EXTS = {".json", ".md", ".txt"}
SUPPORTED_EXTS = IMAGE_EXTS | VIDEO_EXTS | TEXT_EXTS

# 限制
MAX_IMAGE_SIZE = 20 * 1024 * 1024
MAX_VIDEO_SIZE = 40 * 1024 * 1024
MAX_TEXT_SIZE = 100 * 1024 * 1024
MAX_TEXT_LENGTH = 300

# 批量任务存储
batch_tasks: dict[str, dict] = {}


@router.post("/batch/upload")
async def upload_batch_files(files: List[UploadFile] = File(...)):
    """上传批量审核文件"""
    from backend.api.settings import load_settings
    settings = load_settings()
    max_items = settings.get("max_items_per_file", 20)

    task_id = str(uuid.uuid4())
    task_dir = Path(tempfile.gettempdir()) / "ad_review_batch" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    uploaded_files = []
    for file in files:
        filename = file.filename or "unknown"
        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED_EXTS:
            continue

        file_path = task_dir / filename
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        uploaded_files.append({
            "name": filename,
            "path": str(file_path),
            "ext": ext,
            "status": "pending"
        })

    if not uploaded_files:
        raise HTTPException(status_code=400, detail="没有有效的文件被上传")

    # 展开任务
    all_items = []
    for file_info in uploaded_files:
        items = _extract_items(file_info, max_items)
        all_items.extend(items)

    batch_tasks[task_id] = {
        "task_id": task_id,
        "total": len(all_items),
        "completed": 0,
        "passed": 0,
        "rejected": 0,
        "manual_review": 0,
        "items": all_items,
        "results": [],
        "status": "ready",
        "created_at": datetime.now().isoformat()
    }

    return {
        "task_id": task_id,
        "total_files": len(uploaded_files),
        "total_items": len(all_items),
        "message": f"已上传 {len(uploaded_files)} 个文件，共 {len(all_items)} 条待审核"
    }


@router.post("/batch/{task_id}/start")
async def start_batch_processing(task_id: str):
    """启动批量处理"""
    if task_id not in batch_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = batch_tasks[task_id]
    if task["status"] == "processing":
        return {"message": "任务已在处理中"}

    task["status"] = "processing"
    thread = threading.Thread(target=_process_batch_sync, args=(task_id,), daemon=True)
    thread.start()

    return {"message": "处理已启动", "task_id": task_id}


@router.get("/batch/{task_id}/status")
async def get_batch_status(task_id: str):
    """获取批量任务状态"""
    if task_id not in batch_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = batch_tasks[task_id]
    total = task["total"]
    completed = task["completed"]

    return {
        "task_id": task["task_id"],
        "total": total,
        "completed": completed,
        "passed": task["passed"],
        "rejected": task["rejected"],
        "manual_review": task["manual_review"],
        "status": task["status"],
        "progress": round(completed / total * 100, 1) if total > 0 else 0,
        "results": task["results"],
    }


@router.get("/batch/{task_id}/results")
async def get_batch_results(task_id: str):
    """获取批量任务完整结果"""
    if task_id not in batch_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    return batch_tasks[task_id]


# ── 核心处理逻辑（同步） ──

def _process_batch_sync(task_id: str):
    """同步处理批量任务，逐条处理，实时更新状态"""
    from backend.evaluation.scoring import calculate_risk_score

    task = batch_tasks[task_id]
    items = task["items"]

    for i, item in enumerate(items):
        # 检查是否暂停
        if task["status"] != "processing":
            break

        display_name = item[0]
        content = item[1]
        source_path = item[2] if len(item) > 2 else None

        try:
            # 评分
            scoring_result = calculate_risk_score(content)

            # 生成报告（拒绝/复审用 Agent 生成详细报告）
            if scoring_result.conclusion in ("reject", "manual_review"):
                report = _generate_detailed_report(content, scoring_result)
            else:
                report = _generate_report(content, scoring_result)

            # 构建维度数据（基于评分结果）
            # 合规性：有敏感词或规则命中 → 不通过
            compliance_passed = scoring_result.sensitive_word_score < 10 and scoring_result.rule_match_score < 15
            # 真实性：语义分析得分低 → 通过
            authenticity_passed = scoring_result.semantic_score < 10
            # 安全性：无高危敏感词 → 通过
            safety_passed = not any(sw.get("severity") == "high" for sw in scoring_result.sensitive_words_found)

            result = {
                "file": display_name,
                "original_content": content,
                "source_path": source_path,
                "conclusion": scoring_result.conclusion,
                "confidence": scoring_result.confidence,
                "risk_level": scoring_result.risk_level,
                "latency_ms": 0,
                "dimensions": {
                    "compliance": {
                        "passed": compliance_passed,
                        "details": f"敏感词得分: {scoring_result.sensitive_word_score:.1f}, 规则命中: {scoring_result.rule_match_score:.1f}",
                        "confidence": scoring_result.confidence
                    },
                    "authenticity": {
                        "passed": authenticity_passed,
                        "details": f"语义分析得分: {scoring_result.semantic_score:.1f}",
                        "confidence": scoring_result.confidence
                    },
                    "safety": {
                        "passed": safety_passed,
                        "details": f"发现 {len(scoring_result.sensitive_words_found)} 个敏感词",
                        "confidence": scoring_result.confidence
                    }
                },
                "violations": [{"type": sw.get("category", "敏感词"), "content": sw["word"], "rule_ref": sw.get("rule_ref", ""), "severity": sw["severity"], "suggestion": f"删除'{sw['word']}'"} for sw in scoring_result.sensitive_words_found],
                "similar_cases": [],
                "report_markdown": report,
                "scoring_breakdown": scoring_result.score_breakdown,
            }

        except Exception as e:
            result = {
                "file": display_name,
                "original_content": content,
                "source_path": source_path,
                "conclusion": "error",
                "confidence": 0,
                "risk_level": "unknown",
                "latency_ms": 0,
                "reason": str(e)[:200],
                "dimensions": {},
                "violations": [],
                "similar_cases": [],
                "report_markdown": "",
            }

        # 更新状态
        task["completed"] = i + 1
        task["results"].append(result)

        conclusion = result["conclusion"]
        if conclusion == "pass":
            task["passed"] += 1
        elif conclusion == "reject":
            task["rejected"] += 1
        elif conclusion == "manual_review":
            task["manual_review"] += 1

        # 保存到文件夹
        try:
            from backend.api.settings import save_review_result
            save_review_result(
                conclusion=conclusion,
                file_name=display_name,
                content=content,
                report=result.get("report_markdown", ""),
                source_path=source_path
            )
        except:
            pass

        # 短暂延迟
        time.sleep(0.1)

    task["status"] = "completed"


def _generate_detailed_report(content: str, scoring_result) -> str:
    """调用 Agent 生成详细审核报告"""
    try:
        orchestrator = create_orchestrator()

        # 构建提示
        sensitive_words_info = ""
        if scoring_result.sensitive_words_found:
            sensitive_words_info = "发现以下敏感词：\n"
            for sw in scoring_result.sensitive_words_found[:5]:
                sensitive_words_info += f"- {sw['word']}（{sw['severity']}，{sw.get('category', '')}）\n"

        rules_info = ""
        if scoring_result.rules_matched:
            rules_info = "命中以下规则：\n"
            for rule in scoring_result.rules_matched[:3]:
                rules_info += f"- {rule.get('title', '未知')}（相似度:{rule.get('similarity', 0):.0%}）\n"

        prompt = f"""请对以下广告素材生成详细的审核报告：

广告内容：{content}

## 自动检测结果

### 敏感词检测
{f"发现 {len(scoring_result.sensitive_words_found)} 个敏感词" if scoring_result.sensitive_words_found else "未检测到敏感词"}
{sensitive_words_info}

### 规则检索
命中 {len(scoring_result.rules_matched)} 条相关规则
{rules_info}

### 案例参考
拒绝案例: {scoring_result.reject_cases_count} 个, 通过案例: {scoring_result.pass_cases_count} 个

### 评分结果
总风险分: {scoring_result.total_score:.1f}/100
- 敏感词得分: {scoring_result.sensitive_word_score:.1f}/35
- 规则命中得分: {scoring_result.rule_match_score:.1f}/35
- 案例参考得分: {scoring_result.case_reference_score:.1f}/10
- 语义分析得分: {scoring_result.semantic_score:.1f}/20

### 初步结论
结论: {scoring_result.conclusion}
风险等级: {scoring_result.risk_level}
置信度: {scoring_result.confidence:.0%}

请基于以上检测结果，生成完整的审核报告（Markdown格式）。报告必须包含：
1. 审核对象
2. 敏感词检测结果分析
3. 规则检索结果分析
4. 三个维度详细分析（合规性、真实性、安全性）
5. 违规项汇总
6. 审核结论及理由
7. 修改建议"""

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(Runner.run(orchestrator, prompt))
            return result.final_output
        finally:
            loop.close()

    except Exception as e:
        # Agent 调用失败，降级为基本报告
        return _generate_report(content, scoring_result)


def _generate_report(content: str, scoring_result) -> str:
    """生成审核报告"""
    emoji = {"pass": "✅", "reject": "❌", "manual_review": "⚠️"}.get(scoring_result.conclusion, "❓")
    label = {"pass": "通过", "reject": "拒绝", "manual_review": "需人工复审"}.get(scoring_result.conclusion, "未知")

    report = f"""{emoji} {label}

**风险等级**：{scoring_result.risk_level}
**置信度**：{scoring_result.confidence:.0%}

## 评分详情
{scoring_result.score_breakdown}
"""

    if scoring_result.sensitive_words_found:
        report += "\n## 敏感词\n"
        for sw in scoring_result.sensitive_words_found:
            report += f"- {sw['word']}（{sw['severity']}）\n"

    if scoring_result.rules_matched:
        report += "\n## 命中规则\n"
        for rule in scoring_result.rules_matched[:5]:
            report += f"- {rule.get('title', '未知')}（相似度:{rule.get('similarity', 0):.0%}）\n"

    return report


# ── 文件提取 ──

def _extract_items(file_info: dict, max_items: int = 20) -> list:
    """从文件中提取待审核条目"""
    file_path = file_info["path"]
    ext = file_info["ext"]
    file_name = file_info["name"]

    try:
        file_size = Path(file_path).stat().st_size

        # 图片
        if ext in IMAGE_EXTS:
            if file_size > MAX_IMAGE_SIZE:
                return [(file_name, f"【文件过大】{file_size/1024/1024:.1f}MB", None)]
            desc = mimo_client.understand_image(file_path)
            return [(file_name, f"【图片素材】\n{desc}", file_path)]

        # 视频
        if ext in VIDEO_EXTS:
            if file_size > MAX_VIDEO_SIZE:
                return [(file_name, f"【文件过大】{file_size/1024/1024:.1f}MB", None)]
            desc = mimo_client.understand_video(file_path)
            return [(file_name, f"【视频素材】\n{desc}", file_path)]

        # 文本
        if ext in TEXT_EXTS:
            if file_size > MAX_TEXT_SIZE:
                return [(file_name, f"【文件过大】{file_size/1024/1024:.1f}MB", None)]

            content = mimo_client.understand_text_file(file_path)

            # JSON：拆分为多条
            if ext == ".json":
                items = _parse_json_items(content)
                if items:
                    selected = items[:max_items] if max_items > 0 else items
                    result = []
                    for i, item in enumerate(selected):
                        text = _extract_ad_text(item)
                        if len(text) > MAX_TEXT_LENGTH:
                            text = text[:MAX_TEXT_LENGTH] + "..."
                        result.append((f"{file_name}[{i+1}]", text, None))
                    return result

            # MD/TXT
            if len(content) > MAX_TEXT_LENGTH * 3:
                content = content[:MAX_TEXT_LENGTH * 3] + "..."
            return [(file_name, content, None)]

        return []
    except Exception as e:
        return [(file_name, f"【读取失败】{str(e)}", None)]


def _parse_json_items(content: str) -> list:
    """解析JSON或JSONL"""
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return [data]
    except json.JSONDecodeError:
        pass

    items = []
    for line in content.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return items


def _extract_ad_text(item) -> str:
    """从JSON对象提取广告文本"""
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return str(item)

    content = str(item.get("content", "") or "")
    summary = str(item.get("summary", "") or "")

    if content and summary:
        return f"【产品属性】{content}\n【广告文案】{summary}"
    elif content:
        return content
    elif summary:
        return summary

    for key in ["text", "ad", "ad_text", "description", "body"]:
        if key in item and item[key]:
            return str(item[key])

    return json.dumps(item, ensure_ascii=False)

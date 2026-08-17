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
    import logging

    # 配置日志输出到文件，方便排查
    log_file = Path(__file__).parent.parent.parent / "data" / "batch_log.txt"
    logging.basicConfig(
        filename=str(log_file),
        level=logging.INFO,
        format='%(asctime)s %(message)s',
        force=True
    )
    logger = logging.getLogger("batch")

    task = batch_tasks[task_id]
    items = task["items"]
    logger.info(f"[{task_id}] 开始处理，共 {len(items)} 条")

    for i, item in enumerate(items):
        # 检查是否暂停
        if task["status"] != "processing":
            break

        display_name = item[0]
        content = item[1]
        source_path = item[2] if len(item) > 2 else None

        result = None
        item_start_time = time.time()

        # 先更新进度（显示正在处理）
        task["completed"] = i + 1
        task["results"].append({
            "file": display_name,
            "conclusion": "processing",
            "confidence": 0,
            "risk_level": "unknown",
            "latency_ms": 0,
            "dimensions": {},
            "violations": [],
            "report_markdown": "处理中...",
        })
        logger.info(f"[{task_id}] 开始处理第 {i+1}/{len(items)} 条: {display_name}")

        try:
            # 评分
            scoring_result = calculate_risk_score(content)
            logger.info(f"[{task_id}] 评分完成: {scoring_result.conclusion}, 分数: {scoring_result.total_score:.1f}")

            # 调用 Agent 生成详细报告
            logger.info(f"[{task_id}] 开始调用 Agent...")
            report = _generate_detailed_report(content, scoring_result)
            logger.info(f"[{task_id}] Agent 调用完成，报告长度: {len(report)}")

            # 构建维度数据
            compliance_passed = scoring_result.sensitive_word_score < 10 and scoring_result.rule_match_score < 15
            authenticity_passed = scoring_result.semantic_score < 10
            safety_passed = not any(sw.get("severity") == "high" for sw in scoring_result.sensitive_words_found)

            item_latency = int((time.time() - item_start_time) * 1000)

            result = {
                "file": display_name,
                "original_content": content,
                "source_path": source_path,
                "conclusion": scoring_result.conclusion,
                "confidence": scoring_result.confidence,
                "risk_level": scoring_result.risk_level,
                "latency_ms": item_latency,
                "dimensions": {
                    "compliance": {"passed": compliance_passed, "details": f"敏感词得分: {scoring_result.sensitive_word_score:.1f}, 规则命中: {scoring_result.rule_match_score:.1f}", "confidence": scoring_result.confidence},
                    "authenticity": {"passed": authenticity_passed, "details": f"语义分析得分: {scoring_result.semantic_score:.1f}", "confidence": scoring_result.confidence},
                    "safety": {"passed": safety_passed, "details": f"发现 {len(scoring_result.sensitive_words_found)} 个敏感词", "confidence": scoring_result.confidence}
                },
                "violations": [{"type": sw.get("category", "敏感词"), "content": sw["word"], "rule_ref": sw.get("rule_ref", ""), "severity": sw["severity"], "suggestion": f"删除'{sw['word']}'"} for sw in scoring_result.sensitive_words_found],
                "similar_cases": [],
                "report_markdown": report,
                "scoring_breakdown": scoring_result.score_breakdown,
            }

        except Exception as e:
            item_latency = int((time.time() - item_start_time) * 1000)
            logger.error(f"[{task_id}] 第 {i+1} 条处理失败: {str(e)[:200]}")
            result = {
                "file": display_name,
                "original_content": content,
                "source_path": source_path,
                "conclusion": "error",
                "confidence": 0,
                "risk_level": "unknown",
                "latency_ms": item_latency,
                "reason": str(e)[:200],
                "dimensions": {},
                "violations": [],
                "similar_cases": [],
                "report_markdown": f"处理失败: {str(e)[:200]}",
            }

        # 用真实结果替换占位结果
        task["results"][-1] = result

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

        logger.info(f"[{task_id}] 第 {i+1} 条处理完成: {result['conclusion']}")

        # 短暂延迟
        time.sleep(0.1)

    task["status"] = "completed"
    logger.info(f"[{task_id}] 全部处理完成")


def _generate_detailed_report(content: str, scoring_result) -> str:
    """调用 Agent 生成详细审核报告（带超时）"""
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

        prompt = f"""请对以下广告素材生成详细的审核报告（纯Markdown格式，不要输出JSON）：

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

请直接输出Markdown格式的审核报告，不要输出JSON。报告包含：
1. 审核对象
2. 敏感词检测结果分析
3. 规则检索结果分析
4. 三个维度详细分析（合规性、真实性、安全性）
5. 违规项汇总
6. 审核结论及理由
7. 修改建议"""

        import asyncio

        async def run_with_timeout():
            """带超时的 Agent 调用"""
            try:
                return await asyncio.wait_for(
                    Runner.run(orchestrator, prompt),
                    timeout=30.0  # 30秒超时
                )
            except asyncio.TimeoutError:
                return None

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run_with_timeout())

            if result is None:
                # 超时，降级为基本报告
                return _generate_report(content, scoring_result)

            output = result.final_output

            # 提取 Markdown 报告
            if "```json" in output:
                try:
                    json_start = output.find("```json")
                    json_end = output.find("```", json_start + 7)
                    json_str = output[json_start + 7:json_end].strip()
                    data = json.loads(json_str)
                    if "report_markdown" in data:
                        return data["report_markdown"]
                except:
                    pass

            if "# " in output:
                report_start = output.find("# ")
                return output[report_start:]

            return output
        finally:
            loop.close()

    except Exception as e:
        # Agent 调用失败，降级为基本报告
        return _generate_report(content, scoring_result)


def _generate_report(content: str, scoring_result) -> str:
    """生成详细审核报告"""
    emoji = {"pass": "✅", "reject": "❌", "manual_review": "⚠️"}.get(scoring_result.conclusion, "❓")
    label = {"pass": "通过", "reject": "拒绝", "manual_review": "需人工复审"}.get(scoring_result.conclusion, "未知")

    # 维度判定
    compliance_passed = scoring_result.sensitive_word_score < 10 and scoring_result.rule_match_score < 15
    authenticity_passed = scoring_result.semantic_score < 10
    safety_passed = not any(sw.get("severity") == "high" for sw in scoring_result.sensitive_words_found)

    report = f"""# 广告合规审核报告

## 一、审核对象
**广告内容**：{content[:200]}

## 二、审核结论
{emoji} **{label}**

- **风险等级**：{scoring_result.risk_level}
- **置信度**：{scoring_result.confidence:.0%}
- **总风险分**：{scoring_result.total_score:.1f}/100

## 三、维度分析

### 合规性 {'✅ 通过' if compliance_passed else '❌ 未通过'}
- 敏感词得分：{scoring_result.sensitive_word_score:.1f}/35
- 规则命中得分：{scoring_result.rule_match_score:.1f}/35
"""

    if scoring_result.sensitive_words_found:
        report += "\n**发现的敏感词：**\n"
        for sw in scoring_result.sensitive_words_found[:5]:
            report += f"- 「{sw['word']}」（{sw['severity']}，{sw.get('category', '')}）— 依据：{sw.get('rule_ref', '')}\n"

    if scoring_result.rules_matched:
        report += "\n**命中的规则：**\n"
        for rule in scoring_result.rules_matched[:3]:
            report += f"- {rule.get('title', '未知')}（相似度：{rule.get('similarity', 0):.0%}）\n"

    report += f"""
### 真实性 {'✅ 通过' if authenticity_passed else '❌ 未通过'}
- 语义分析得分：{scoring_result.semantic_score:.1f}/20
- 判断依据：{'未发现虚假宣传或夸大功效表述' if authenticity_passed else '存在疑似虚假宣传或夸大功效表述'}

### 安全性 {'✅ 通过' if safety_passed else '❌ 未通过'}
- 敏感词数量：{len(scoring_result.sensitive_words_found)} 个
- 判断依据：{'无高危敏感词' if safety_passed else '发现高严重程度敏感词'}

## 四、案例参考
- 拒绝案例：{scoring_result.reject_cases_count} 个
- 通过案例：{scoring_result.pass_cases_count} 个

## 五、违规项汇总
"""

    if scoring_result.sensitive_words_found:
        for sw in scoring_result.sensitive_words_found:
            report += f"- **{sw.get('category', '敏感词')}**：「{sw['word']}」— {sw.get('rule_ref', '')}\n"
    else:
        report += "无违规项\n"

    report += f"""
## 六、评分详情
```
{scoring_result.score_breakdown}
```
"""

    if scoring_result.conclusion == "reject":
        report += """
## 七、修改建议
1. 删除所有违禁词和绝对化用语
2. 确保广告内容真实、可验证
3. 避免夸大功效或虚假宣传
4. 参考《广告法》相关条款进行修改
"""

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

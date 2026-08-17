"""
自动化工作流 API V2
支持文件夹处理、JSON数据集逐条拆分、进度持久化、断点续传
"""

import json
import time
import uuid
import threading
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from agents import Runner

from backend.api.settings import load_settings, save_review_result
from backend.review_agents.orchestrator import create_orchestrator
from backend.knowledge.mimo_client import mimo_client

router = APIRouter()

# 文件类型
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".wmv"}
TEXT_EXTS = {".json", ".md", ".txt"}
SUPPORTED_EXTS = IMAGE_EXTS | VIDEO_EXTS | TEXT_EXTS

# 工作流状态存储
WORKFLOW_DIR = Path(__file__).parent.parent.parent / "data" / "workflows"


class WorkflowConfig(BaseModel):
    source_folder: str
    auto_start: bool = False


def _get_workflow_file(workflow_id: str) -> Path:
    WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)
    return WORKFLOW_DIR / f"{workflow_id}.json"


def _save_workflow_state(workflow_id: str, state: dict):
    wf_file = _get_workflow_file(workflow_id)
    with open(wf_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _load_workflow_state(workflow_id: str) -> Optional[dict]:
    wf_file = _get_workflow_file(workflow_id)
    if wf_file.exists():
        with open(wf_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _scan_folder(folder_path: str) -> list:
    """扫描文件夹，展开JSON数据集为逐条任务"""
    folder = Path(folder_path)
    if not folder.exists():
        return []

    tasks = []

    for f in sorted(folder.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in SUPPORTED_EXTS:
            continue

        ext = f.suffix.lower()

        # JSON文件：展开为逐条任务
        if ext == ".json":
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    content = fp.read()
                    items = _parse_json_items(content)
                    for i, item in enumerate(items):
                        text = _extract_ad_text(item)
                        tasks.append({
                            "task_id": f"{f.name}[{i+1}]",
                            "source_file": str(f),
                            "source_path": str(f),
                            "item_index": i,
                            "content": text,
                            "type": "json_item",
                        })
            except Exception as e:
                tasks.append({
                    "task_id": f.name,
                    "source_file": str(f),
                    "source_path": str(f),
                    "content": f"【读取失败】{str(e)}",
                    "type": "error",
                })
        else:
            # 图片/视频/MD/TXT：单文件单任务
            tasks.append({
                "task_id": f.name,
                "source_file": str(f),
                "source_path": str(f),
                "content": None,  # 处理时再提取
                "type": "file",
            })

    return tasks


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


@router.post("/workflow/create")
async def create_workflow(config: WorkflowConfig):
    """创建自动化工作流"""
    folder = Path(config.source_folder)
    if not folder.exists():
        raise HTTPException(status_code=400, detail=f"文件夹不存在: {config.source_folder}")

    # 扫描并展开任务
    tasks = _scan_folder(config.source_folder)
    if not tasks:
        raise HTTPException(status_code=400, detail="文件夹中没有找到支持的文件")

    workflow_id = str(uuid.uuid4())[:8]
    state = {
        "workflow_id": workflow_id,
        "source_folder": config.source_folder,
        "status": "ready",
        "total_tasks": len(tasks),
        "completed_tasks": 0,
        "passed": 0,
        "rejected": 0,
        "manual_review": 0,
        "tasks": tasks,
        "results": {},
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    _save_workflow_state(workflow_id, state)

    return {
        "workflow_id": workflow_id,
        "total_tasks": len(tasks),
        "message": f"工作流已创建，共 {len(tasks)} 条待审核"
    }


@router.post("/workflow/{workflow_id}/start")
async def start_workflow(workflow_id: str):
    """启动工作流"""
    state = _load_workflow_state(workflow_id)
    if not state:
        raise HTTPException(status_code=404, detail="工作流不存在")

    if state["status"] == "processing":
        return {"message": "已在处理中"}

    state["status"] = "processing"
    state["updated_at"] = datetime.now().isoformat()
    _save_workflow_state(workflow_id, state)

    thread = threading.Thread(target=_process_workflow, args=(workflow_id,), daemon=True)
    thread.start()

    return {"message": "工作流已启动", "workflow_id": workflow_id}


@router.post("/workflow/{workflow_id}/pause")
async def pause_workflow(workflow_id: str):
    """暂停工作流"""
    state = _load_workflow_state(workflow_id)
    if not state:
        raise HTTPException(status_code=404, detail="工作流不存在")

    state["status"] = "paused"
    state["updated_at"] = datetime.now().isoformat()
    _save_workflow_state(workflow_id, state)

    return {"message": "已暂停"}


@router.get("/workflow/{workflow_id}/status")
async def get_workflow_status(workflow_id: str):
    """获取工作流状态"""
    state = _load_workflow_state(workflow_id)
    if not state:
        raise HTTPException(status_code=404, detail="工作流不存在")

    total = state["total_tasks"]
    completed = state["completed_tasks"]
    progress = (completed / total * 100) if total > 0 else 0

    return {
        "workflow_id": state["workflow_id"],
        "source_folder": state["source_folder"],
        "status": state["status"],
        "total_tasks": total,
        "completed_tasks": completed,
        "passed": state["passed"],
        "rejected": state["rejected"],
        "manual_review": state["manual_review"],
        "progress": round(progress, 1),
        "updated_at": state["updated_at"],
    }


@router.get("/workflow/{workflow_id}/results")
async def get_workflow_results(workflow_id: str):
    """获取详细结果"""
    state = _load_workflow_state(workflow_id)
    if not state:
        raise HTTPException(status_code=404, detail="工作流不存在")

    return {
        "workflow_id": state["workflow_id"],
        "results": state["results"],
    }


@router.get("/workflow/list")
async def list_workflows():
    """列出所有工作流"""
    WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)
    workflows = []

    for wf_file in WORKFLOW_DIR.glob("*.json"):
        try:
            with open(wf_file, "r", encoding="utf-8") as f:
                state = json.load(f)
                total = state.get("total_tasks", state.get("total_files", 0))
                completed = state.get("completed_tasks", state.get("processed_files", 0))
                workflows.append({
                    "workflow_id": state["workflow_id"],
                    "source_folder": state["source_folder"],
                    "status": state["status"],
                    "total_tasks": total,
                    "completed_tasks": completed,
                    "progress": round(completed / total * 100, 1) if total > 0 else 0,
                    "created_at": state["created_at"],
                })
        except:
            continue

    return {"workflows": workflows}


# ── 后台处理逻辑 ──

def _process_workflow(workflow_id: str):
    """后台处理工作流"""
    from backend.evaluation.scoring import calculate_risk_score

    while True:
        state = _load_workflow_state(workflow_id)
        if not state or state["status"] != "processing":
            break

        # 找到下一个未处理的任务
        next_task = None
        for task in state["tasks"]:
            if task["task_id"] not in state["results"]:
                next_task = task
                break

        if not next_task:
            state["status"] = "completed"
            state["updated_at"] = datetime.now().isoformat()
            _save_workflow_state(workflow_id, state)
            break

        # 处理任务
        try:
            result = _process_task(next_task, calculate_risk_score)

            state["results"][next_task["task_id"]] = result
            state["completed_tasks"] += 1

            conclusion = result.get("conclusion", "error")
            if conclusion == "pass":
                state["passed"] += 1
            elif conclusion == "reject":
                state["rejected"] += 1
            elif conclusion == "manual_review":
                state["manual_review"] += 1

            state["updated_at"] = datetime.now().isoformat()
            _save_workflow_state(workflow_id, state)

            # 保存到结果文件夹
            try:
                save_review_result(
                    conclusion=conclusion,
                    file_name=next_task["task_id"],
                    content=result.get("content", ""),
                    report=result.get("report_markdown", ""),
                    source_path=next_task.get("source_path")
                )
            except:
                pass

        except Exception as e:
            state["results"][next_task["task_id"]] = {
                "conclusion": "error",
                "error": str(e)[:200],
            }
            state["completed_tasks"] += 1
            state["updated_at"] = datetime.now().isoformat()
            _save_workflow_state(workflow_id, state)

        # 检查暂停
        state = _load_workflow_state(workflow_id)
        if state["status"] == "paused":
            break

        time.sleep(0.3)


def _process_task(task: dict, scoring_fn) -> dict:
    """处理单个任务"""
    task_type = task.get("type", "file")
    content = task.get("content")

    # 提取内容
    if not content:
        source_path = task.get("source_path", "")
        ext = Path(source_path).suffix.lower()

        if ext in IMAGE_EXTS:
            content = mimo_client.understand_image(source_path)
        elif ext in VIDEO_EXTS:
            content = mimo_client.understand_video(source_path)
        elif ext in TEXT_EXTS:
            content = mimo_client.understand_text_file(source_path)

    if not content or "读取失败" in content:
        return {"conclusion": "error", "error": "无法提取内容", "content": content or ""}

    # 评分
    scoring_result = scoring_fn(content)

    # 生成报告
    report = _generate_report(content, scoring_result)

    return {
        "conclusion": scoring_result.conclusion,
        "confidence": scoring_result.composite_risk_score / 100,
        "risk_level": scoring_result.risk_level,
        "content": content,
        "report_markdown": report,
        "scoring_breakdown": scoring_result.score_breakdown,
    }


def _generate_report(content: str, scoring_result) -> str:
    """生成审核报告"""
    emoji = {"pass": "✅", "reject": "❌", "manual_review": "⚠️"}.get(scoring_result.conclusion, "❓")
    label = {"pass": "通过", "reject": "拒绝", "manual_review": "需人工复审"}.get(scoring_result.conclusion, "未知")

    report = f"""{emoji} {label}

**风险等级**：{scoring_result.risk_level}
**综合风险分**：{scoring_result.composite_risk_score:.0f}/100

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

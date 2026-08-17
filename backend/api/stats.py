"""
数据统计 API 路由
合并单次审核、批量审核和工作流的结果
"""

import json
from pathlib import Path
from fastapi import APIRouter
from backend.api.review import review_store
from backend.api.batch import batch_tasks

router = APIRouter()


def _load_workflow_results() -> list:
    """加载所有工作流的结果"""
    from backend.api.workflow import WORKFLOW_DIR
    results = []

    if not WORKFLOW_DIR.exists():
        return results

    for wf_file in WORKFLOW_DIR.glob("*.json"):
        try:
            with open(wf_file, "r", encoding="utf-8") as f:
                state = json.load(f)
                for task_id, r in state.get("results", {}).items():
                    if r.get("conclusion") in ("pass", "reject", "manual_review"):
                        results.append({
                            "title": task_id,
                            "conclusion": r["conclusion"],
                            "confidence": r.get("confidence", 0.5),
                            "risk_level": r.get("risk_level", "medium"),
                            "latency_ms": 0,
                            "dimensions": {},
                            "violations": [],
                            "similar_cases": [],
                            "report_markdown": r.get("report_markdown", ""),
                            "content": r.get("content", ""),
                        })
        except:
            continue

    return results


@router.get("/stats/recent")
async def get_recent_reviews():
    """获取最近的审核记录"""
    recent = []

    # 从单次审核收集
    for r in review_store.values():
        recent.append({
            "title": f"单次审核 - {r.review_id[:8]}",
            "conclusion": r.conclusion.value,
            "confidence": r.confidence,
            "risk_level": r.risk_level.value,
            "latency_ms": r.latency_ms or 0,
            "dimensions": {k: {"passed": v.passed, "details": v.details, "confidence": v.confidence} for k, v in r.dimensions.items()},
            "violations": [{"type": v.type if isinstance(v.type, str) else v.type.value, "content": v.content, "rule_ref": v.rule_ref, "severity": v.severity, "suggestion": v.suggestion} for v in r.violations],
            "similar_cases": [{"case_id": c.case_id, "content": c.content, "conclusion": c.conclusion, "similarity": c.similarity} for c in r.similar_cases],
            "report_markdown": r.report_markdown,
        })

    # 从批量审核收集
    for task in batch_tasks.values():
        for r in task.get("results", []):
            if r.get("conclusion") in ("pass", "reject", "manual_review"):
                recent.append({
                    "title": r.get("file", "未知文件"),
                    "conclusion": r["conclusion"],
                    "confidence": r.get("confidence", 0.5),
                    "risk_level": r.get("risk_level", "medium"),
                    "latency_ms": r.get("latency_ms", 0),
                    "dimensions": r.get("dimensions", {}),
                    "violations": r.get("violations", []),
                    "similar_cases": r.get("similar_cases", []),
                    "report_markdown": r.get("report_markdown", ""),
                })

    # 从工作流收集
    recent.extend(_load_workflow_results())

    return recent


@router.get("/stats")
async def get_stats():
    """
    获取审核数据统计

    合并单次审核和批量审核的所有结果。
    """
    all_results = []

    # 1. 从单次审核收集
    for r in review_store.values():
        all_results.append({
            "conclusion": r.conclusion.value,
            "confidence": getattr(r, 'confidence', None) or (r.composite_risk_score / 100 if hasattr(r, 'composite_risk_score') else 0.5),
            "risk_level": r.risk_level.value,
            "latency_ms": r.latency_ms or 0,
            "violations": [{"type": v.type if isinstance(v.type, str) else v.type.value} for v in r.violations],
            "dimensions": {k: {"passed": v.passed} for k, v in r.dimensions.items()},
        })

    # 2. 从批量审核收集
    for task in batch_tasks.values():
        for r in task.get("results", []):
            if r.get("conclusion") in ("pass", "reject", "manual_review"):
                all_results.append({
                    "conclusion": r["conclusion"],
                    "confidence": r.get("confidence", 0.5),
                    "risk_level": r.get("risk_level", "medium"),
                    "latency_ms": r.get("latency_ms", 0),
                    "violations": r.get("violations", []),
                    "dimensions": {k: {"passed": v.get("passed", False)} for k, v in r.get("dimensions", {}).items()},
                })

    # 3. 从工作流收集
    for r in _load_workflow_results():
        if r.get("conclusion") in ("pass", "reject", "manual_review"):
            all_results.append({
                "conclusion": r["conclusion"],
                "confidence": r.get("confidence", 0.5),
                "risk_level": r.get("risk_level", "medium"),
                "latency_ms": 0,
                "violations": r.get("violations", []),
                "dimensions": {},
            })

    if not all_results:
        return {
            "total_reviews": 0,
            "pass_rate": 0,
            "reject_rate": 0,
            "manual_review_rate": 0,
            "avg_latency_ms": 0,
            "avg_confidence": 0,
            "violation_distribution": {},
            "risk_distribution": {},
            "dimension_stats": {}
        }

    total = len(all_results)

    # 统计审核结论
    pass_count = sum(1 for r in all_results if r["conclusion"] == "pass")
    reject_count = sum(1 for r in all_results if r["conclusion"] == "reject")
    manual_count = sum(1 for r in all_results if r["conclusion"] == "manual_review")

    # 统计风险等级
    risk_dist = {}
    for r in all_results:
        level = r["risk_level"]
        risk_dist[level] = risk_dist.get(level, 0) + 1

    # 统计违规类型
    violation_dist = {}
    for r in all_results:
        for v in r.get("violations", []):
            v_type = v.get("type", "其他")
            violation_dist[v_type] = violation_dist.get(v_type, 0) + 1

    # 统计各维度通过率
    dim_stats = {}
    for r in all_results:
        for dim_name, dim_data in r.get("dimensions", {}).items():
            if dim_name not in dim_stats:
                dim_stats[dim_name] = {"passed": 0, "total": 0}
            dim_stats[dim_name]["total"] += 1
            if dim_data.get("passed"):
                dim_stats[dim_name]["passed"] += 1

    for dim_name in dim_stats:
        t = dim_stats[dim_name]["total"]
        dim_stats[dim_name]["pass_rate"] = dim_stats[dim_name]["passed"] / t if t > 0 else 0

    # 计算平均值
    avg_latency = sum(r["latency_ms"] for r in all_results) / total
    avg_confidence = sum(r["confidence"] for r in all_results) / total

    return {
        "total_reviews": total,
        "pass_rate": pass_count / total,
        "reject_rate": reject_count / total,
        "manual_review_rate": manual_count / total,
        "avg_latency_ms": int(avg_latency),
        "avg_confidence": round(avg_confidence, 2),
        "violation_distribution": violation_dist,
        "risk_distribution": risk_dist,
        "dimension_stats": dim_stats
    }

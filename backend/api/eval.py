"""
评估 API 路由
运行评估、查看评估结果
"""

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

from backend.config import EVAL_TEST_SET_PATH

router = APIRouter()


@router.get("/eval/run")
async def run_evaluation():
    """
    运行评估

    使用测评集对审核 Agent 进行评估，返回各项指标。
    """
    # 加载测评集
    test_set_path = Path(EVAL_TEST_SET_PATH)
    if not test_set_path.exists():
        raise HTTPException(status_code=404, detail="测评集文件不存在")

    with open(test_set_path, "r", encoding="utf-8") as f:
        test_data = json.load(f)

    cases = test_data.get("cases", [])
    if not cases:
        raise HTTPException(status_code=400, detail="测评集为空")

    # 统计测评集信息
    total = len(cases)
    pass_count = sum(1 for c in cases if c.get("label") == "pass")
    reject_count = sum(1 for c in cases if c.get("label") == "reject")
    manual_count = sum(1 for c in cases if c.get("label") == "manual_review")

    # 按难度分布
    difficulty_dist = {}
    for c in cases:
        diff = c.get("difficulty", "unknown")
        difficulty_dist[diff] = difficulty_dist.get(diff, 0) + 1

    # 按违规类型分布
    violation_dist = {}
    for c in cases:
        v_type = c.get("violation_type")
        if v_type:
            violation_dist[v_type] = violation_dist.get(v_type, 0) + 1

    return {
        "status": "ready",
        "test_set_info": {
            "total_cases": total,
            "pass_cases": pass_count,
            "reject_cases": reject_count,
            "manual_review_cases": manual_count,
            "difficulty_distribution": difficulty_dist,
            "violation_distribution": violation_dist
        },
        "message": "测评集加载成功，可使用 POST /api/eval/execute 执行完整评估"
    }


@router.get("/eval/metrics")
async def get_eval_metrics():
    """
    获取评估指标定义

    返回评估体系中使用的各项指标及其计算公式。
    """
    return {
        "accuracy_metrics": {
            "accuracy": {
                "name": "准确率",
                "formula": "(TP + TN) / (TP + TN + FP + FN)",
                "target": "≥ 85%",
                "description": "整体审核正确率"
            },
            "precision": {
                "name": "精确率",
                "formula": "TP / (TP + FP)",
                "target": "≥ 90%",
                "description": "拒绝的素材中，确实应拒绝的比例"
            },
            "recall": {
                "name": "召回率",
                "formula": "TP / (TP + FN)",
                "target": "≥ 90%",
                "description": "应拒绝的素材中，被正确拒绝的比例"
            },
            "f1": {
                "name": "F1 分数",
                "formula": "2 × Precision × Recall / (Precision + Recall)",
                "target": "≥ 88%",
                "description": "精确率和召回率的调和平均"
            },
            "false_rejection_rate": {
                "name": "误拒率",
                "formula": "FP / (FP + TN)",
                "target": "≤ 10%",
                "description": "应通过但被错误拒绝的比例"
            },
            "false_acceptance_rate": {
                "name": "漏放率",
                "formula": "FN / (FN + TP)",
                "target": "≤ 10%",
                "description": "应拒绝但被错误通过的比例"
            }
        },
        "efficiency_metrics": {
            "avg_latency": {
                "name": "平均审核耗时",
                "target": "< 10 秒",
                "description": "单素材审核时间"
            },
            "manual_review_rate": {
                "name": "人工复审率",
                "target": "≤ 20%",
                "description": "需要人工复审的比例"
            }
        },
        "confusion_matrix": {
            "TP": "正确拒绝（True Positive）",
            "TN": "正确通过（True Negative）",
            "FP": "错误拒绝（False Positive）",
            "FN": "错误通过（False Negative）"
        }
    }

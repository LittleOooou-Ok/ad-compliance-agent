"""
评估指标计算模块
计算准确率、精确率、召回率、F1 等指标
"""

from dataclasses import dataclass


@dataclass
class ConfusionMatrix:
    """混淆矩阵"""
    tp: int = 0  # 正确拒绝
    tn: int = 0  # 正确通过
    fp: int = 0  # 错误拒绝（误拒）
    fn: int = 0  # 错误通过（漏放）


@dataclass
class EvalMetrics:
    """评估指标"""
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    false_rejection_rate: float = 0.0
    false_acceptance_rate: float = 0.0
    avg_latency_ms: float = 0.0
    avg_confidence: float = 0.0
    manual_review_rate: float = 0.0


def calculate_confusion_matrix(
    actual_labels: list[str],
    predicted_labels: list[str]
) -> ConfusionMatrix:
    """
    计算混淆矩阵

    将 pass 视为 Negative，reject 视为 Positive
    manual_review 按 reject 处理（保守策略）
    """
    cm = ConfusionMatrix()

    for actual, predicted in zip(actual_labels, predicted_labels):
        # 将 manual_review 转换为 reject（保守处理）
        if predicted == "manual_review":
            predicted = "reject"

        if actual == "reject" and predicted == "reject":
            cm.tp += 1
        elif actual == "pass" and predicted == "pass":
            cm.tn += 1
        elif actual == "pass" and predicted == "reject":
            cm.fp += 1
        elif actual == "reject" and predicted == "pass":
            cm.fn += 1

    return cm


def calculate_metrics(cm: ConfusionMatrix) -> EvalMetrics:
    """计算各项评估指标"""
    metrics = EvalMetrics()

    total = cm.tp + cm.tn + cm.fp + cm.fn
    if total == 0:
        return metrics

    # 准确率
    metrics.accuracy = (cm.tp + cm.tn) / total

    # 精确率
    if (cm.tp + cm.fp) > 0:
        metrics.precision = cm.tp / (cm.tp + cm.fp)

    # 召回率
    if (cm.tp + cm.fn) > 0:
        metrics.recall = cm.tp / (cm.tp + cm.fn)

    # F1 分数
    if (metrics.precision + metrics.recall) > 0:
        metrics.f1 = 2 * metrics.precision * metrics.recall / (metrics.precision + metrics.recall)

    # 误拒率
    if (cm.fp + cm.tn) > 0:
        metrics.false_rejection_rate = cm.fp / (cm.fp + cm.tn)

    # 漏放率
    if (cm.fn + cm.tp) > 0:
        metrics.false_acceptance_rate = cm.fn / (cm.fn + cm.tp)

    return metrics


def format_metrics_report(metrics: EvalMetrics, cm: ConfusionMatrix) -> str:
    """格式化指标报告"""
    report = f"""## 评估指标报告

### 核心指标
| 指标 | 目标值 | 实际值 | 状态 |
|------|--------|--------|------|
| 准确率 | ≥ 85% | {metrics.accuracy:.1%} | {'✅' if metrics.accuracy >= 0.85 else '⚠️'} |
| 精确率 | ≥ 90% | {metrics.precision:.1%} | {'✅' if metrics.precision >= 0.90 else '⚠️'} |
| 召回率 | ≥ 90% | {metrics.recall:.1%} | {'✅' if metrics.recall >= 0.90 else '⚠️'} |
| F1 分数 | ≥ 88% | {metrics.f1:.1%} | {'✅' if metrics.f1 >= 0.88 else '⚠️'} |
| 误拒率 | ≤ 10% | {metrics.false_rejection_rate:.1%} | {'✅' if metrics.false_rejection_rate <= 0.10 else '⚠️'} |
| 漏放率 | ≤ 10% | {metrics.false_acceptance_rate:.1%} | {'✅' if metrics.false_acceptance_rate <= 0.10 else '⚠️'} |

### 混淆矩阵
|  | 预测通过 | 预测拒绝 |
|--|---------|---------|
| 实际通过 | TN={cm.tn} | FP={cm.fp} |
| 实际拒绝 | FN={cm.fn} | TP={cm.tp} |
"""
    return report

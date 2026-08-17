"""
评估器模块
对审核 Agent 进行评估
"""

import json
import time
from pathlib import Path
from typing import Optional
from agents import Runner

from backend.config import EVAL_TEST_SET_PATH
from backend.evaluation.metrics import (
    ConfusionMatrix, EvalMetrics,
    calculate_confusion_matrix, calculate_metrics, format_metrics_report
)
from backend.review_agents.orchestrator import create_orchestrator


class AdComplianceEvaluator:
    """广告合规审核评估器"""

    def __init__(self, test_set_path: str = EVAL_TEST_SET_PATH):
        self.test_set_path = Path(test_set_path)
        self.test_cases = []
        self.results = []

    def load_test_set(self) -> list[dict]:
        """加载测评集"""
        if not self.test_set_path.exists():
            raise FileNotFoundError(f"测评集文件不存在: {self.test_set_path}")

        with open(self.test_set_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.test_cases = data.get("cases", [])

        return self.test_cases

    async def evaluate_single(self, case: dict) -> dict:
        """评估单个案例"""
        orchestrator = create_orchestrator()

        prompt = f"""请审核以下广告素材：

广告内容：{case['content']}
广告类型：{case.get('ad_type', '未知')}

请按照标准流程完成审核，并返回最终的审核报告。"""

        start_time = time.time()

        try:
            result = await Runner.run(orchestrator, prompt)
            latency_ms = int((time.time() - start_time) * 1000)

            # 解析输出
            output = result.final_output
            predicted = self._extract_conclusion(output)
            confidence = self._extract_confidence(output)

            return {
                "case_id": case["id"],
                "content": case["content"],
                "actual": case["label"],
                "predicted": predicted,
                "confidence": confidence,
                "latency_ms": latency_ms,
                "is_correct": self._check_correct(case["label"], predicted),
                "output": output
            }
        except Exception as e:
            return {
                "case_id": case["id"],
                "content": case["content"],
                "actual": case["label"],
                "predicted": "error",
                "confidence": 0,
                "latency_ms": int((time.time() - start_time) * 1000),
                "is_correct": False,
                "error": str(e)
            }

    async def run(self, max_cases: Optional[int] = None) -> dict:
        """运行完整评估"""
        self.load_test_set()

        cases = self.test_cases
        if max_cases:
            cases = cases[:max_cases]

        print(f"开始评估，共 {len(cases)} 个案例...")

        self.results = []
        for i, case in enumerate(cases, 1):
            print(f"  [{i}/{len(cases)}] 评估案例 {case['id']}...")
            result = await self.evaluate_single(case)
            self.results.append(result)

        return self.generate_report()

    def generate_report(self) -> dict:
        """生成评估报告"""
        if not self.results:
            return {"error": "没有评估结果"}

        actual_labels = [r["actual"] for r in self.results]
        predicted_labels = [r["predicted"] for r in self.results]

        # 计算混淆矩阵
        cm = calculate_confusion_matrix(actual_labels, predicted_labels)

        # 计算指标
        metrics = calculate_metrics(cm)

        # 计算平均延迟和置信度
        valid_results = [r for r in self.results if r["predicted"] != "error"]
        if valid_results:
            metrics.avg_latency_ms = sum(r["latency_ms"] for r in valid_results) / len(valid_results)
            metrics.avg_confidence = sum(r["confidence"] for r in valid_results) / len(valid_results)

        # 统计人工复审率
        manual_count = sum(1 for r in self.results if r["predicted"] == "manual_review")
        metrics.manual_review_rate = manual_count / len(self.results)

        # 提取错误案例
        bad_cases = [r for r in self.results if not r["is_correct"]]

        # 生成报告文本
        report_text = format_metrics_report(metrics, cm)

        return {
            "metrics": {
                "accuracy": metrics.accuracy,
                "precision": metrics.precision,
                "recall": metrics.recall,
                "f1": metrics.f1,
                "false_rejection_rate": metrics.false_rejection_rate,
                "false_acceptance_rate": metrics.false_acceptance_rate,
                "avg_latency_ms": metrics.avg_latency_ms,
                "avg_confidence": metrics.avg_confidence,
                "manual_review_rate": metrics.manual_review_rate
            },
            "confusion_matrix": {
                "tp": cm.tp,
                "tn": cm.tn,
                "fp": cm.fp,
                "fn": cm.fn
            },
            "bad_cases": bad_cases,
            "total_cases": len(self.results),
            "report_text": report_text
        }

    def _extract_conclusion(self, output: str) -> str:
        """从输出中提取审核结论"""
        output_lower = output.lower()

        if "pass" in output_lower and "reject" not in output_lower:
            return "pass"
        elif "reject" in output_lower:
            return "reject"
        elif "manual_review" in output_lower or "人工复审" in output_lower:
            return "manual_review"
        else:
            return "manual_review"

    def _extract_confidence(self, output: str) -> float:
        """从输出中提取置信度"""
        import re
        # 尝试匹配置信度数值
        patterns = [
            r'置信度[：:]\s*(\d+(?:\.\d+)?)%',
            r'confidence[：:]\s*(\d+(?:\.\d+)?)%',
            r'(\d+(?:\.\d+)?)%'
        ]

        for pattern in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                value = float(match.group(1))
                if value > 1:
                    value = value / 100
                return min(1.0, max(0.0, value))

        return 0.5  # 默认值

    def _check_correct(self, actual: str, predicted: str) -> bool:
        """检查预测是否正确"""
        if predicted == "error":
            return False

        # manual_review 视为 reject
        if predicted == "manual_review":
            predicted = "reject"
        if actual == "manual_review":
            actual = "reject"

        return actual == predicted

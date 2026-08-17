"""
运行评估脚本
对审核 Agent 进行完整评估并生成报告
"""

import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.evaluation.evaluator import AdComplianceEvaluator
from backend.config import DOCS_DIR


async def main():
    """主函数"""
    print("=" * 60)
    print("广告素材合规审核 Agent - 评估")
    print("=" * 60)

    evaluator = AdComplianceEvaluator()

    # 加载测评集
    test_cases = evaluator.load_test_set()
    print(f"测评集规模：{len(test_cases)} 条")

    # 统计测评集信息
    pass_count = sum(1 for c in test_cases if c.get("label") == "pass")
    reject_count = sum(1 for c in test_cases if c.get("label") == "reject")
    manual_count = sum(1 for c in test_cases if c.get("label") == "manual_review")
    print(f"  - 正例（应通过）：{pass_count} 条")
    print(f"  - 负例（应拒绝）：{reject_count} 条")
    print(f"  - 边界案例：{manual_count} 条")
    print()

    # 运行评估
    print("开始评估...")
    report = await evaluator.run()

    # 打印结果
    print()
    print("=" * 60)
    print("评估结果")
    print("=" * 60)
    print(report["report_text"])

    # 打印错误案例
    bad_cases = report.get("bad_cases", [])
    if bad_cases:
        print()
        print(f"错误案例 ({len(bad_cases)} 个):")
        print("-" * 60)
        for case in bad_cases[:10]:  # 只显示前10个
            print(f"案例 {case['case_id']}:")
            print(f"  内容：{case['content'][:50]}...")
            print(f"  实际：{case['actual']} → 预测：{case['predicted']}")
            print()

    # 保存报告
    report_path = DOCS_DIR / "evaluation_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# 广告素材合规审核 Agent 评估报告\n\n")
        f.write(f"**评估时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**测评集规模**：{report['total_cases']} 条\n\n")
        f.write(report["report_text"])

        if bad_cases:
            f.write(f"\n\n## Bad Case 分析\n\n")
            f.write(f"共 {len(bad_cases)} 个错误案例\n\n")
            for case in bad_cases:
                f.write(f"### 案例 {case['case_id']}\n\n")
                f.write(f"- **内容**：{case['content']}\n")
                f.write(f"- **实际标签**：{case['actual']}\n")
                f.write(f"- **预测结果**：{case['predicted']}\n")
                f.write(f"- **置信度**：{case['confidence']:.2f}\n\n")

    print(f"\n报告已保存至：{report_path}")

    # 保存详细结果 JSON
    results_path = DOCS_DIR / "eval_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"详细结果已保存至：{results_path}")


if __name__ == "__main__":
    asyncio.run(main())

"""
从 train.json 随机挑选 100 条数据运行评估
生成评估报告
"""

import sys
import json
import random
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.evaluation.scoring import calculate_risk_score


def load_train_data(file_path: str, sample_size: int = 100) -> list:
    """加载并随机抽样"""
    items = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    # 随机抽样
    if len(items) > sample_size:
        items = random.sample(items, sample_size)

    return items


def extract_ad_text(item: dict) -> str:
    """提取广告文本"""
    content = str(item.get("content", "") or "")
    summary = str(item.get("summary", "") or "")

    if content and summary:
        return f"【产品属性】{content}\n【广告文案】{summary}"
    elif content:
        return content
    elif summary:
        return summary
    return json.dumps(item, ensure_ascii=False)


def run_evaluation(items: list) -> dict:
    """运行评估"""
    results = []

    for i, item in enumerate(items):
        content = extract_ad_text(item)

        # 计算评分
        scoring_result = calculate_risk_score(content)

        results.append({
            "index": i + 1,
            "content_preview": content[:100],
            "conclusion": scoring_result.conclusion,
            "confidence": scoring_result.confidence,
            "risk_level": scoring_result.risk_level,
            "total_score": scoring_result.total_score,
            "sensitive_word_score": scoring_result.sensitive_word_score,
            "rule_match_score": scoring_result.rule_match_score,
            "case_reference_score": scoring_result.case_reference_score,
            "semantic_score": scoring_result.semantic_score,
            "sensitive_words_count": len(scoring_result.sensitive_words_found),
            "rules_matched_count": len(scoring_result.rules_matched),
        })

        if (i + 1) % 20 == 0:
            print(f"  已处理 {i+1}/{len(items)} 条")

    return results


def generate_report(results: list) -> str:
    """生成评估报告"""
    total = len(results)
    pass_count = sum(1 for r in results if r["conclusion"] == "pass")
    reject_count = sum(1 for r in results if r["conclusion"] == "reject")
    manual_count = sum(1 for r in results if r["conclusion"] == "manual_review")

    # 计算平均分
    avg_score = sum(r["total_score"] for r in results) / total
    avg_confidence = sum(r["confidence"] for r in results) / total

    # 按分数段统计
    score_ranges = {
        "0-20 (低风险)": sum(1 for r in results if r["total_score"] < 20),
        "20-35 (中低风险)": sum(1 for r in results if 20 <= r["total_score"] < 35),
        "35-50 (中风险)": sum(1 for r in results if 35 <= r["total_score"] < 50),
        "50-65 (中高风险)": sum(1 for r in results if 50 <= r["total_score"] < 65),
        "65+ (高风险)": sum(1 for r in results if r["total_score"] >= 65),
    }

    # 按违规类型统计
    violation_types = {}
    for r in results:
        for sw in r.get("sensitive_words_found", []):
            cat = sw.get("category", "其他")
            violation_types[cat] = violation_types.get(cat, 0) + 1

    # 高分案例（可能的误判）
    high_score_pass = [r for r in results if r["conclusion"] == "pass" and r["total_score"] > 25]
    low_score_reject = [r for r in results if r["conclusion"] == "reject" and r["total_score"] < 50]

    report = f"""# 广告素材合规审核 Agent 评估报告

**评估时间**：{time.strftime('%Y-%m-%d %H:%M:%S')}
**测评集来源**：train.json 随机抽样
**测评集规模**：{total} 条

---

## 1. 核心指标

| 指标 | 数值 | 说明 |
|------|------|------|
| **总样本数** | {total} | 随机抽样 |
| **通过** | {pass_count} ({pass_count/total*100:.1f}%) | 判定为合规 |
| **拒绝** | {reject_count} ({reject_count/total*100:.1f}%) | 判定为违规 |
| **需复审** | {manual_count} ({manual_count/total*100:.1f}%) | 需人工确认 |
| **平均风险分** | {avg_score:.1f}/100 | 分数越高风险越大 |
| **平均置信度** | {avg_confidence:.0%} | AI 判断把握程度 |

---

## 2. 风险分分布

| 分数段 | 数量 | 占比 |
|--------|------|------|
"""

    for range_name, count in score_ranges.items():
        bar = "█" * int(count / total * 30)
        report += f"| {range_name} | {count} | {count/total*100:.1f}% {bar} |\n"

    report += f"""
---

## 3. 各维度得分统计

| 维度 | 满分 | 平均分 | 说明 |
|------|------|--------|------|
| 敏感词检测 | 35 | {sum(r['sensitive_word_score'] for r in results)/total:.1f} | 直接匹配违禁词 |
| 规则命中 | 35 | {sum(r['rule_match_score'] for r in results)/total:.1f} | RAG 检索相关规则 |
| 案例参考 | 10 | {sum(r['case_reference_score'] for r in results)/total:.1f} | 相似案例对比 |
| 语义分析 | 20 | {sum(r['semantic_score'] for r in results)/total:.1f} | 模式匹配分析 |

---

## 4. 结论分布

```
通过:     {"█" * int(pass_count/total*40)} {pass_count} ({pass_count/total*100:.1f}%)
拒绝:     {"█" * int(reject_count/total*40)} {reject_count} ({reject_count/total*100:.1f}%)
需复审:   {"█" * int(manual_count/total*40)} {manual_count} ({manual_count/total*100:.1f}%)
```

---

## 5. 敏感词命中统计

| 类别 | 命中次数 |
|------|----------|
"""

    for cat, count in sorted(violation_types.items(), key=lambda x: -x[1]):
        report += f"| {cat} | {count} |\n"

    report += f"""
---

## 6. 典型案例分析

### 6.1 高风险通过案例（可能漏检）
"""

    if high_score_pass:
        report += f"共 {len(high_score_pass)} 例：\n\n"
        for r in high_score_pass[:5]:
            report += f"- **案例 {r['index']}**：风险分 {r['total_score']:.1f}，置信度 {r['confidence']:.0%}\n"
            report += f"  内容：{r['content_preview']}...\n\n"
    else:
        report += "无\n\n"

    report += """### 6.2 低风险拒绝案例（可能误判）
"""

    if low_score_reject:
        report += f"共 {len(low_score_reject)} 例：\n\n"
        for r in low_score_reject[:5]:
            report += f"- **案例 {r['index']}**：风险分 {r['total_score']:.1f}，置信度 {r['confidence']:.0%}\n"
            report += f"  内容：{r['content_preview']}...\n\n"
    else:
        report += "无\n\n"

    report += """---

## 7. 优化建议

### 短期优化（1-2周）
1. 扩充敏感词库，覆盖更多行业特定违禁词
2. 增加更多审核案例，提高案例参考准确性
3. 调整评分权重，减少误判和漏判

### 中期优化（1-2月）
1. 引入 LLM 语义分析，处理隐晦违规表达
2. 建立反馈机制，收集人工复审结果优化模型
3. 扩展行业规则库，覆盖更多特殊行业

### 长期规划
1. 建立持续学习机制，自动更新规则库
2. 支持图片/视频内容审核
3. 接入更多外部数据源

---

## 附录：测评集样本

| 序号 | 内容摘要 | 结论 | 风险分 | 置信度 |
|------|----------|------|--------|--------|
"""

    for r in results[:20]:
        emoji = {"pass": "✅", "reject": "❌", "manual_review": "⚠️"}.get(r["conclusion"], "❓")
        report += f"| {r['index']} | {r['content_preview'][:30]}... | {emoji} {r['conclusion']} | {r['total_score']:.1f} | {r['confidence']:.0%} |\n"

    report += f"\n*（仅展示前 20 条，完整数据见 eval_results.json）*\n"

    return report


def main():
    """主函数"""
    print("=" * 60)
    print("广告素材合规审核 Agent - 评估")
    print("=" * 60)

    # 加载数据
    train_file = r"data\test_set\test_cases.json"  # 使用项目内的测评集
    print(f"\n从 {train_file} 随机抽取 100 条数据...")
    items = load_train_data(train_file, sample_size=100)
    print(f"已抽取 {len(items)} 条")

    # 运行评估
    print("\n开始评估...")
    start_time = time.time()
    results = run_evaluation(items)
    elapsed = time.time() - start_time
    print(f"\n评估完成，耗时 {elapsed:.1f} 秒")

    # 生成报告
    print("\n生成评估报告...")
    report = generate_report(results)

    # 保存报告
    report_path = Path(__file__).parent.parent / "docs" / "evaluation_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"报告已保存: {report_path}")

    # 保存详细结果
    results_path = Path(__file__).parent.parent / "docs" / "eval_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"详细结果已保存: {results_path}")

    # 打印摘要
    print("\n" + "=" * 60)
    print("评估摘要")
    print("=" * 60)
    total = len(results)
    pass_count = sum(1 for r in results if r["conclusion"] == "pass")
    reject_count = sum(1 for r in results if r["conclusion"] == "reject")
    manual_count = sum(1 for r in results if r["conclusion"] == "manual_review")
    avg_score = sum(r["total_score"] for r in results) / total

    print(f"总样本: {total}")
    print(f"通过: {pass_count} ({pass_count/total*100:.1f}%)")
    print(f"拒绝: {reject_count} ({reject_count/total*100:.1f}%)")
    print(f"需复审: {manual_count} ({manual_count/total*100:.1f}%)")
    print(f"平均风险分: {avg_score:.1f}/100")


if __name__ == "__main__":
    main()

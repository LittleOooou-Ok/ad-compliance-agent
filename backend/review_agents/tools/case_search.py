"""
案例检索工具
供 Agent 调用的历史案例检索工具
"""

from agents import function_tool
from backend.knowledge.rule_manager import rule_manager


@function_tool
def find_similar_review_cases(ad_content: str, n_results: int = 3) -> str:
    """
    查找与当前广告内容相似的历史审核案例，用于参考判断。

    Args:
        ad_content: 当前审核的广告文案内容
        n_results: 返回的案例数量，默认3个

    Returns:
        相似案例的详细信息，包括审核结论和分析
    """
    cases = rule_manager.search_cases(ad_content, n_results)

    if not cases:
        return "未找到相似的历史审核案例。"

    result_parts = ["以下是与当前广告内容相似的历史审核案例：\n"]

    for i, case in enumerate(cases, 1):
        metadata = case.get("metadata", {})
        conclusion = metadata.get("conclusion", "未知")
        conclusion_emoji = {"pass": "✅", "reject": "❌", "manual_review": "⚠️"}.get(conclusion, "❓")

        result_parts.append(f"【案例 {i}】{conclusion_emoji}")
        result_parts.append(f"广告内容：{case['content']}")
        result_parts.append(f"审核结论：{conclusion}")
        result_parts.append(f"广告类型：{metadata.get('ad_type', '未知')}")

        if metadata.get("violation_type"):
            result_parts.append(f"违规类型：{metadata['violation_type']}")
        if metadata.get("violation_detail"):
            result_parts.append(f"违规详情：{metadata['violation_detail']}")

        result_parts.append(f"相似度：{1 - case['distance']:.2f}\n")

    return "\n".join(result_parts)

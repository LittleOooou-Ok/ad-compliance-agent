"""
RAG 检索工具
供 Agent 调用的审核规则检索工具
"""

from agents import function_tool
from backend.knowledge.rule_manager import rule_manager


@function_tool
def search_ad_rules(query: str, n_results: int = 5) -> str:
    """
    从审核规则知识库中检索与广告内容相关的审核规则。

    Args:
        query: 查询内容，通常是广告文案或关键词
        n_results: 返回结果数量，默认5条

    Returns:
        相关审核规则列表，包含规则内容和来源
    """
    rules = rule_manager.search_rules(query, n_results)

    if not rules:
        return "未找到相关审核规则。"

    result_parts = ["找到以下相关审核规则：\n"]
    for i, rule in enumerate(rules, 1):
        result_parts.append(f"【规则 {i}】")
        result_parts.append(rule["content"])
        result_parts.append(f"（相关度：{1 - rule['distance']:.2f}）\n")

    return "\n".join(result_parts)


@function_tool
def search_similar_cases(query: str, n_results: int = 3) -> str:
    """
    从案例库中检索与当前广告内容相似的历史审核案例。

    Args:
        query: 查询内容，通常是广告文案
        n_results: 返回结果数量，默认3条

    Returns:
        相似案例列表，包含案例内容和审核结论
    """
    cases = rule_manager.search_cases(query, n_results)

    if not cases:
        return "未找到相似案例。"

    result_parts = ["找到以下相似案例：\n"]
    for i, case in enumerate(cases, 1):
        metadata = case.get("metadata", {})
        result_parts.append(f"【案例 {i}】")
        result_parts.append(f"内容：{case['content']}")
        result_parts.append(f"结论：{metadata.get('conclusion', '未知')}")
        if metadata.get("violation_type"):
            result_parts.append(f"违规类型：{metadata['violation_type']}")
        result_parts.append(f"（相似度：{1 - case['distance']:.2f}）\n")

    return "\n".join(result_parts)

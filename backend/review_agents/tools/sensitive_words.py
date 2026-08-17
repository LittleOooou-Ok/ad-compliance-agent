"""
敏感词匹配工具
供 Agent 调用的敏感词检测工具
"""

from agents import function_tool
from backend.knowledge.rule_manager import rule_manager


@function_tool
def check_sensitive_words(text: str) -> str:
    """
    检测广告文本中是否包含敏感词、违禁词。

    Args:
        text: 需要检测的广告文案内容

    Returns:
        检测结果，包含匹配到的敏感词及其分类、严重程度、修改建议
    """
    matches = rule_manager.match_sensitive_words(text)

    if not matches:
        return "未检测到敏感词。该广告文案不包含已知的违禁词或限用词。"

    result_parts = [f"检测到 {len(matches)} 个敏感词/违禁词：\n"]

    # 按严重程度排序
    severity_order = {"high": 0, "medium": 1, "low": 2}
    matches.sort(key=lambda x: severity_order.get(x["severity"], 3))

    for i, match in enumerate(matches, 1):
        result_parts.append(f"【敏感词 {i}】")
        result_parts.append(f"词语：{match['word']}")
        result_parts.append(f"类别：{match['category']}")
        result_parts.append(f"严重程度：{match['severity']}")
        result_parts.append(f"法规依据：{match['rule_ref']}")
        if match.get("alternatives"):
            result_parts.append(f"建议替换为：{'、'.join(match['alternatives'])}")
        result_parts.append(f"位置：第{match['position']['start']}字符\n")

    # 统计摘要
    high_count = sum(1 for m in matches if m["severity"] == "high")
    medium_count = sum(1 for m in matches if m["severity"] == "medium")

    result_parts.append("【摘要】")
    if high_count > 0:
        result_parts.append(f"⚠️ 存在 {high_count} 个高严重程度敏感词，建议立即修改")
    if medium_count > 0:
        result_parts.append(f"⚡ 存在 {medium_count} 个中等严重程度敏感词，建议修改")

    return "\n".join(result_parts)

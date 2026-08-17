"""
基于证据的综合评分模块 V4
规则裁决 + 多维风险评分
"""

from dataclasses import dataclass, field
from backend.knowledge.rule_manager import rule_manager


@dataclass
class ScoringResult:
    """评分结果"""
    conclusion: str = "manual_review"
    risk_level: str = "medium"

    # 各维度风险分 (0-100)
    compliance_risk_score: float = 0.0
    compliance_risk_level: str = "low"
    authenticity_risk_score: float = 0.0
    authenticity_risk_level: str = "low"
    safety_risk_score: float = 0.0
    safety_risk_level: str = "low"

    # 综合风险分
    composite_risk_score: float = 0.0
    composite_risk_level: str = "low"

    # 证据详情
    sensitive_words_found: list = field(default_factory=list)
    rules_matched: list = field(default_factory=list)
    reject_cases_count: int = 0
    pass_cases_count: int = 0

    # 各维度得分（用于内部计算）
    sensitive_word_score: float = 0.0
    rule_match_score: float = 0.0
    case_reference_score: float = 0.0
    semantic_score: float = 0.0
    total_score: float = 0.0

    # 分数说明
    score_breakdown: str = ""


# 模糊匹配词表
FUZZY_PATTERNS = {
    "绝对化": ["最好", "最佳", "最优", "第一", "唯一", "顶级", "极致", "完美", "无敌", "最强", "最低", "最高", "最大", "最小"],
    "功效承诺": ["见效", "治愈", "根治", "痊愈", "康复", "好转", "瘦身", "减肥", "美白", "祛斑", "祛痘", "丰胸", "壮阳", "增高", "排毒", "抗衰", "逆龄"],
    "虚假背书": ["推荐", "认证", "指定", "专供", "同款", "首选", "领先", "第一", "冠军", "王者"],
    "诱导消费": ["错过", "仅此", "最后", "即将", "售罄", "抢购", "秒杀", "疯抢", "亏本", "跳楼"],
}


def calculate_risk_score(content: str) -> ScoringResult:
    """
    计算风险分

    Args:
        content: 广告内容

    Returns:
        ScoringResult: 评分结果
    """
    result = ScoringResult()

    # ── 1. 敏感词检测 ──
    result.sensitive_word_score, result.sensitive_words_found = _check_sensitive_words(content)

    # ── 2. 规则匹配 ──
    result.rule_match_score, result.rules_matched = _check_rules(content)

    # ── 3. 案例参考 ──
    result.case_reference_score, result.reject_cases_count, result.pass_cases_count = _check_cases(content)

    # ── 4. 语义分析 ──
    result.semantic_score = _check_semantic(content)

    # ── 计算总分 ──
    result.total_score = (
        result.sensitive_word_score +
        result.rule_match_score +
        result.case_reference_score +
        result.semantic_score
    )

    # ── 计算各维度风险分 ──

    # 合规性风险分
    result.compliance_risk_score = _calculate_compliance_risk(result)
    result.compliance_risk_level = _get_risk_level(result.compliance_risk_score)

    # 真实性风险分
    result.authenticity_risk_score = _calculate_authenticity_risk(result)
    result.authenticity_risk_level = _get_risk_level(result.authenticity_risk_score)

    # 安全性风险分
    result.safety_risk_score = _calculate_safety_risk(result)
    result.safety_risk_level = _get_risk_level(result.safety_risk_score)

    # ── 计算综合风险分 ──
    result.composite_risk_score = (
        result.compliance_risk_score * 0.5 +
        result.authenticity_risk_score * 0.3 +
        result.safety_risk_score * 0.2
    )
    result.composite_risk_level = _get_risk_level(result.composite_risk_score)

    # ── 判定结论 ──
    result.conclusion, result.risk_level = _determine_conclusion(result)

    # ── 生成分数说明 ──
    result.score_breakdown = _generate_breakdown(result)

    return result


def _calculate_compliance_risk(result: ScoringResult) -> float:
    """计算合规性风险分"""
    score = 0.0

    # 敏感词贡献
    if result.sensitive_word_score > 0:
        score += min(40, result.sensitive_word_score * 1.5)

    # 规则命中贡献
    if result.rule_match_score > 0:
        score += min(35, result.rule_match_score * 1.2)

    # 案例参考贡献
    if result.reject_cases_count > 0:
        score += min(15, result.reject_cases_count * 5)

    # 语义分析贡献
    if result.semantic_score > 0:
        score += min(10, result.semantic_score * 0.8)

    return min(100.0, score)


def _calculate_authenticity_risk(result: ScoringResult) -> float:
    """计算真实性风险分"""
    score = 0.0

    # 语义分析贡献（功效承诺、虚假宣传）
    if result.semantic_score > 0:
        score += min(50, result.semantic_score * 2.5)

    # 敏感词中的虚假宣传类
    false_ad_words = [sw for sw in result.sensitive_words_found if "虚假" in sw.get("category", "") or "夸大" in sw.get("category", "")]
    score += len(false_ad_words) * 15

    # 规则命中中的真实性相关
    truth_rules = [r for r in result.rules_matched if "虚假" in r.get("title", "") or "夸大" in r.get("title", "")]
    score += len(truth_rules) * 10

    return min(100.0, score)


def _calculate_safety_risk(result: ScoringResult) -> float:
    """计算安全性风险分"""
    score = 0.0

    # 高危敏感词贡献
    high_severity = [sw for sw in result.sensitive_words_found if sw.get("severity") == "high"]
    score += len(high_severity) * 20

    # 安全类敏感词
    safety_words = [sw for sw in result.sensitive_words_found if "安全" in sw.get("category", "") or "敏感" in sw.get("category", "")]
    score += len(safety_words) * 15

    return min(100.0, score)


def _get_risk_level(score: float) -> str:
    """根据分数获取风险等级"""
    if score < 20:
        return "low"
    elif score < 40:
        return "medium"
    elif score < 60:
        return "high"
    else:
        return "critical"


def _determine_conclusion(result: ScoringResult) -> tuple[str, str]:
    """判定结论和风险等级"""
    has_high_severity = any(sw.get("severity") == "high" for sw in result.sensitive_words_found)
    has_medium_severity = any(sw.get("severity") == "medium" for sw in result.sensitive_words_found)

    # 规则1：合规性风险分 ≥ 80 且有明确规则依据 → reject
    if result.compliance_risk_score >= 80 and result.rule_match_score > 15:
        return "reject", "high"

    # 规则2：有高危敏感词 → reject
    if has_high_severity:
        return "reject", "high"

    # 规则3：综合风险分 ≥ 80 且有违规证据 → reject
    if result.composite_risk_score >= 80 and (result.sensitive_word_score > 10 or result.rule_match_score > 10):
        return "reject", "high"

    # 规则4：综合风险分 40-79 → manual_review
    if result.composite_risk_score >= 40:
        return "manual_review", "medium"

    # 规则5：某个维度风险分 ≥ 60 → manual_review
    if result.compliance_risk_score >= 60 or result.authenticity_risk_score >= 60 or result.safety_risk_score >= 60:
        return "manual_review", "medium"

    # 规则6：有中危敏感词 → manual_review
    if has_medium_severity:
        return "manual_review", "medium"

    # 规则7：通过
    return "pass", "low"


def _check_sensitive_words(content: str) -> tuple[float, list]:
    """敏感词检测"""
    matches = rule_manager.match_sensitive_words(content)

    if not matches:
        fuzzy_matches = _fuzzy_match(content)
        if fuzzy_matches:
            score = len(fuzzy_matches) * 5
            return min(35.0, score), fuzzy_matches
        return 0.0, []

    score = 0.0
    found = []

    for match in matches:
        severity = match.get("severity", "medium")
        word = match.get("word", "")

        if severity == "high":
            score += 15
        elif severity == "medium":
            score += 7
        else:
            score += 3

        found.append({
            "word": word,
            "category": match.get("category", ""),
            "severity": severity,
            "rule_ref": match.get("rule_ref", ""),
        })

    return min(35.0, score), found


def _fuzzy_match(content: str) -> list:
    """模糊匹配"""
    found = []
    content_lower = content.lower()

    for category, keywords in FUZZY_PATTERNS.items():
        for keyword in keywords:
            if keyword in content_lower:
                found.append({
                    "word": keyword,
                    "category": f"模糊匹配-{category}",
                    "severity": "medium",
                    "rule_ref": "语义分析",
                })

    return found


def _check_rules(content: str) -> tuple[float, list]:
    """规则匹配"""
    rules = rule_manager.search_rules(content, n_results=5)

    if not rules:
        return 0.0, []

    score = 0.0
    matched = []

    for rule in rules:
        rule_content = rule.get("content", "")
        distance = rule.get("distance", 1.0)
        similarity = 1 - distance

        if similarity < 0.3:
            continue

        severity = "medium"
        if "高" in rule_content and ("严重" in rule_content or "严重程度" in rule_content):
            severity = "high"

        if severity == "high":
            score += 12 * similarity
        else:
            score += 6 * similarity

        metadata = rule.get("metadata", {})
        matched.append({
            "rule_id": metadata.get("rule_id", ""),
            "title": metadata.get("title", ""),
            "severity": severity,
            "similarity": similarity,
        })

    return min(35.0, score), matched


def _check_cases(content: str) -> tuple[float, int, int]:
    """案例参考"""
    cases = rule_manager.search_cases(content, n_results=5)

    if not cases:
        return 0.0, 0, 0

    reject_count = 0
    pass_count = 0
    score = 0.0

    for case in cases:
        metadata = case.get("metadata", {})
        conclusion = metadata.get("conclusion", "")
        distance = case.get("distance", 1.0)
        similarity = 1 - distance

        if conclusion == "reject":
            reject_count += 1
            score += 3 * similarity
        elif conclusion == "pass":
            pass_count += 1
            score -= 1 * similarity

    return max(0, min(10.0, score)), reject_count, pass_count


def _check_semantic(content: str) -> float:
    """语义分析"""
    score = 0.0
    content_lower = content.lower()

    import re

    # 模式1：数字+时间+效果
    time_effect_patterns = [
        r'\d+天.{0,2}(见效|变白|瘦身|治好|痊愈)',
        r'\d+周.{0,2}(见效|变白|瘦身)',
        r'(三天|一周|一个月).{0,4}(见效|变白|瘦身|治好)',
    ]
    for pattern in time_effect_patterns:
        if re.search(pattern, content):
            score += 8
            break

    # 模式2：绝对化表述
    absolute_patterns = [
        r'任何.{0,6}(都|均|可以)',
        r'\d+%\s*(有效|通过|成功)',
        r'(所有|全部|任何).{0,4}(适用|有效|适合)',
    ]
    for pattern in absolute_patterns:
        if re.search(pattern, content):
            score += 6
            break

    # 模式3：功效承诺
    effect_patterns = [
        r'(治疗|治愈|根治|治好).{0,4}(病|症|炎|痛)',
        r'(消除|去除|祛除|去除).{0,4}(斑|痘|皱纹|黑眼圈)',
        r'(增强|提高|提升).{0,4}(免疫|体质|体力|精力)',
    ]
    for pattern in effect_patterns:
        if re.search(pattern, content):
            score += 6
            break

    return min(20.0, score)


def _generate_breakdown(result: ScoringResult) -> str:
    """生成分数说明"""
    parts = [
        f"综合风险分: {result.composite_risk_score:.0f}/100 ({result.composite_risk_level})",
        f"",
        f"├─ 合规性风险: {result.compliance_risk_score:.0f}/100 ({result.compliance_risk_level})",
        f"│  敏感词得分: {result.sensitive_word_score:.1f}/35",
        f"│  规则命中得分: {result.rule_match_score:.1f}/35",
        f"│",
        f"├─ 真实性风险: {result.authenticity_risk_score:.0f}/100 ({result.authenticity_risk_level})",
        f"│  语义分析得分: {result.semantic_score:.1f}/20",
        f"│",
        f"├─ 安全性风险: {result.safety_risk_score:.0f}/100 ({result.safety_risk_level})",
        f"│  高危敏感词: {sum(1 for sw in result.sensitive_words_found if sw.get('severity') == 'high')} 个",
        f"",
        f"结论: {result.conclusion}",
    ]

    return "\n".join(parts)

"""
基于证据的综合评分模块 V3
优化权重、增加模糊匹配、增加语义分析
"""

from dataclasses import dataclass, field
from backend.knowledge.rule_manager import rule_manager


@dataclass
class ScoringResult:
    """评分结果"""
    total_score: float = 0.0
    conclusion: str = "manual_review"
    risk_level: str = "medium"
    confidence: float = 0.5

    # 各维度得分
    sensitive_word_score: float = 0.0
    rule_match_score: float = 0.0
    case_reference_score: float = 0.0
    semantic_score: float = 0.0

    # 证据详情
    sensitive_words_found: list = field(default_factory=list)
    rules_matched: list = field(default_factory=list)
    reject_cases_count: int = 0
    pass_cases_count: int = 0

    # 分数说明
    score_breakdown: str = ""


# ── 模糊匹配词表（同义词/变体）──
FUZZY_PATTERNS = {
    "绝对化": [
        "最好", "最佳", "最优", "第一", "唯一", "顶级", "极致",
        "完美", "无敌", "最强", "最低", "最高", "最大", "最小",
        "独一无二", "无与伦比", "绝无仅有", "史无前例",
    ],
    "功效承诺": [
        "见效", "治愈", "根治", "痊愈", "康复", "好转",
        "瘦身", "减肥", "美白", "祛斑", "祛痘", "丰胸",
        "壮阳", "增高", "排毒", "抗衰", "逆龄",
    ],
    "虚假背书": [
        "推荐", "认证", "指定", "专供", "同款", "首选",
        "领先", "第一", "冠军", "王者", "霸主",
    ],
    "诱导消费": [
        "错过", "仅此", "最后", "即将", "售罄", "抢购",
        "秒杀", "疯抢", "亏本", "跳楼", "吐血",
    ],
}


def calculate_risk_score(content: str) -> ScoringResult:
    """
    直接调用工具计算风险分

    Args:
        content: 广告内容

    Returns:
        ScoringResult: 评分结果
    """
    result = ScoringResult()

    # ── 1. 敏感词检测 (0-35分) ──
    result.sensitive_word_score, result.sensitive_words_found = _check_sensitive_words(content)

    # ── 2. 规则匹配 (0-35分) ──
    result.rule_match_score, result.rules_matched = _check_rules(content)

    # ── 3. 案例参考 (0-10分) ──
    result.case_reference_score, result.reject_cases_count, result.pass_cases_count = _check_cases(content)

    # ── 4. 模糊语义分析 (0-20分) ──
    result.semantic_score = _check_semantic(content)

    # ── 计算总分 ──
    result.total_score = (
        result.sensitive_word_score +
        result.rule_match_score +
        result.case_reference_score +
        result.semantic_score
    )

    # ── 判定结论 ──
    has_high_severity = any(sw.get("severity") == "high" for sw in result.sensitive_words_found)
    has_medium_severity = any(sw.get("severity") == "medium" for sw in result.sensitive_words_found)
    has_fuzzy_match = any("模糊匹配" in sw.get("category", "") for sw in result.sensitive_words_found)
    sensitive_word_count = len(result.sensitive_words_found)

    # 置信度计算：基于证据强度
    # 有直接敏感词命中 → 高置信度
    # 只有模糊匹配 → 低置信度
    if has_high_severity:
        evidence_strength = 0.9
    elif has_medium_severity and not has_fuzzy_match:
        evidence_strength = 0.8
    elif has_medium_severity and has_fuzzy_match:
        evidence_strength = 0.6  # 混合了模糊匹配，置信度降低
    elif has_fuzzy_match:
        evidence_strength = 0.4  # 只有模糊匹配，置信度低
    else:
        evidence_strength = 0.85  # 无违规，高置信度

    # 规则1：有高危敏感词 → 直接拒绝
    if has_high_severity:
        result.conclusion = "reject"
        result.risk_level = "high"
        result.confidence = evidence_strength

    # 规则2：有多个中危敏感词（非模糊匹配）→ 拒绝
    elif sensitive_word_count >= 3 and has_medium_severity and not has_fuzzy_match:
        result.conclusion = "reject"
        result.risk_level = "high"
        result.confidence = evidence_strength

    # 规则3：总分 >= 50 → 拒绝
    elif result.total_score >= 50:
        result.conclusion = "reject"
        result.risk_level = "high"
        result.confidence = evidence_strength

    # 规则4：只有模糊匹配且分数低 → 通过（模糊匹配不可靠）
    elif has_fuzzy_match and result.total_score < 15:
        result.conclusion = "pass"
        result.risk_level = "low"
        result.confidence = 0.75  # 模糊匹配误报可能性大，置信度中等

    # 规则5：总分 >= 25 或有中危词 → 复审
    elif result.total_score >= 25 or has_medium_severity:
        result.conclusion = "manual_review"
        result.risk_level = "medium"
        result.confidence = evidence_strength

    # 规则6：通过
    else:
        result.conclusion = "pass"
        result.risk_level = "low"
        result.confidence = 0.90  # 无违规，高置信度

    # ── 生成分数说明 ──
    result.score_breakdown = _generate_breakdown(result)

    return result


def _check_sensitive_words(content: str) -> tuple[float, list]:
    """敏感词检测 (0-35分)"""
    matches = rule_manager.match_sensitive_words(content)

    if not matches:
        # 尝试模糊匹配
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
            score += 15  # 高危词权重提高
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
    """模糊匹配（同义词/变体）"""
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
    """规则匹配 (0-35分)"""
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
        elif "严重程度：高" in rule_content:
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
    """案例参考 (0-10分)"""
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
    """语义分析 (0-20分) - 基于规则模式匹配"""
    score = 0.0
    content_lower = content.lower()

    # 模式1：数字+时间+效果（如"三天见效"、"一周变白"）
    import re
    time_effect_patterns = [
        r'\d+天.{0,2}(见效|变白|瘦身|治好|痊愈)',
        r'\d+周.{0,2}(见效|变白|瘦身)',
        r'\d+个月.{0,2}(见效|变白|瘦身)',
        r'(三天|一周|一个月).{0,4}(见效|变白|瘦身|治好)',
    ]
    for pattern in time_effect_patterns:
        if re.search(pattern, content):
            score += 8
            break

    # 模式2：绝对化表述（"任何...都..."、"...100%..."）
    absolute_patterns = [
        r'任何.{0,6}(都|均|可以)',
        r'\d+%\s*(有效|通过|成功)',
        r'(所有|全部|任何).{0,4}(适用|有效|适合)',
    ]
    for pattern in absolute_patterns:
        if re.search(pattern, content):
            score += 6
            break

    # 模式3：功效承诺（动词+效果名词）
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
        f"总风险分: {result.total_score:.1f}/100",
        f"",
        f"├─ 敏感词得分: {result.sensitive_word_score:.1f}/35",
        f"│  发现 {len(result.sensitive_words_found)} 个敏感词",
    ]

    for sw in result.sensitive_words_found[:5]:
        parts.append(f"│    - {sw['word']} ({sw['severity']})")

    parts.extend([
        f"│",
        f"├─ 规则命中得分: {result.rule_match_score:.1f}/35",
        f"│  命中 {len(result.rules_matched)} 条规则",
    ])

    for rule in result.rules_matched[:3]:
        parts.append(f"│    - {rule.get('title', '未知')} (相似度:{rule.get('similarity', 0):.0%})")

    parts.extend([
        f"│",
        f"├─ 案例参考得分: {result.case_reference_score:.1f}/10",
        f"│  拒绝案例: {result.reject_cases_count}, 通过案例: {result.pass_cases_count}",
        f"│",
        f"└─ 语义分析得分: {result.semantic_score:.1f}/20",
        f"",
        f"结论: {result.conclusion}",
        f"风险等级: {result.risk_level}",
        f"置信度: {result.confidence:.0%}",
    ])

    return "\n".join(parts)

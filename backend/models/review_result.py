"""
审核结果数据模型
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime


class ReviewConclusion(str, Enum):
    """审核结论"""
    PASS = "pass"
    REJECT = "reject"
    MANUAL_REVIEW = "manual_review"


class RiskLevel(str, Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ViolationType(str, Enum):
    """违规类型"""
    PROHIBITED_WORD = "违禁词"
    FALSE_ADVERTISING = "虚假宣传"
    EXAGGERATION = "夸大功效"
    SENSITIVE_CONTENT = "敏感内容"
    INDUSTRY_SPECIAL = "行业特殊规定"
    UNFAIR_COMPETITION = "不正当竞争"
    OTHER = "其他"


class Violation(BaseModel):
    """违规点"""
    type: str = Field(..., description="违规类型")
    content: str = Field(..., description="违规内容原文")
    rule_ref: str = Field(..., description="引用的法规条款")
    severity: str = Field(..., description="严重程度: high/medium/low")
    suggestion: str = Field(..., description="修改建议")
    position: Optional[dict] = Field(None, description="违规内容在原文中的位置 {start, end}")


class DimensionResult(BaseModel):
    """单维度审核结果"""
    passed: bool = Field(..., description="是否通过")
    details: str = Field(..., description="审核详情说明")
    confidence: float = Field(..., description="置信度 0-1")


class SimilarCase(BaseModel):
    """相似案例"""
    case_id: str = Field(..., description="案例ID")
    content: str = Field(..., description="案例内容")
    conclusion: str = Field(..., description="案例结论")
    similarity: float = Field(..., description="相似度 0-1")


class ReviewResult(BaseModel):
    """审核结果"""
    review_id: str = Field(..., description="审核记录ID")
    conclusion: ReviewConclusion = Field(..., description="审核结论")
    confidence: float = Field(..., description="整体置信度 0-1")
    risk_level: RiskLevel = Field(..., description="风险等级")
    dimensions: dict[str, DimensionResult] = Field(..., description="各维度审核结果")
    violations: list[Violation] = Field(default_factory=list, description="违规点列表")
    similar_cases: list[SimilarCase] = Field(default_factory=list, description="相似案例")
    report_markdown: str = Field(..., description="Markdown 格式的审核报告")
    created_at: datetime = Field(default_factory=datetime.now, description="审核时间")
    latency_ms: Optional[int] = Field(None, description="审核耗时(毫秒)")

    # 素材解析结果
    parsed_brand: Optional[str] = Field(None, description="解析出的品牌名")
    parsed_product: Optional[str] = Field(None, description="解析出的产品名")
    parsed_ad_type: Optional[str] = Field(None, description="解析出的广告类型")
    key_phrases: list[str] = Field(default_factory=list, description="关键短语")

"""
规则数据模型
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime


class RuleCategory(str, Enum):
    """规则类别"""
    CORE_LAW = "广告法核心条款"
    PROHIBITED_WORD = "违禁词规则"
    INDUSTRY_MEDICAL = "医疗行业规则"
    INDUSTRY_FINANCE = "金融行业规则"
    INDUSTRY_EDUCATION = "教育行业规则"
    INDUSTRY_FOOD = "食品行业规则"
    PLATFORM = "平台审核规范"
    OTHER = "其他"


class RuleSeverity(str, Enum):
    """严重程度"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Rule(BaseModel):
    """审核规则"""
    rule_id: str = Field(..., description="规则ID")
    category: RuleCategory = Field(..., description="规则类别")
    title: str = Field(..., description="规则标题")
    content: str = Field(..., description="规则内容")
    law_reference: Optional[str] = Field(None, description="法规依据")
    severity: RuleSeverity = Field(RuleSeverity.MEDIUM, description="严重程度")
    examples: list[str] = Field(default_factory=list, description="违规示例")
    keywords: list[str] = Field(default_factory=list, description="关键词")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")


class RuleCreate(BaseModel):
    """创建规则请求"""
    category: RuleCategory
    title: str
    content: str
    law_reference: Optional[str] = None
    severity: RuleSeverity = RuleSeverity.MEDIUM
    examples: list[str] = []
    keywords: list[str] = []


class RuleUpdate(BaseModel):
    """更新规则请求"""
    category: Optional[RuleCategory] = None
    title: Optional[str] = None
    content: Optional[str] = None
    law_reference: Optional[str] = None
    severity: Optional[RuleSeverity] = None
    examples: Optional[list[str]] = None
    keywords: Optional[list[str]] = None

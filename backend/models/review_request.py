"""
审核请求数据模型
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class AdType(str, Enum):
    """广告类型枚举"""
    FEED = "信息流广告"
    SEARCH = "搜索广告"
    ECOMMERCE = "电商广告"
    BRAND = "品牌广告"
    APP_DOWNLOAD = "应用下载广告"
    OTHER = "其他"


class ReviewRequest(BaseModel):
    """审核请求模型"""
    content: str = Field(..., description="广告文案内容", min_length=1, max_length=5000)
    ad_type: Optional[AdType] = Field(None, description="广告类型")
    brand_name: Optional[str] = Field(None, description="品牌名称")
    product_name: Optional[str] = Field(None, description="产品名称")
    callback_url: Optional[str] = Field(None, description="审核完成回调地址")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "content": "全网最低价！限时抢购，错过再等一年！",
                    "ad_type": "信息流广告",
                    "brand_name": "某品牌",
                    "product_name": "某产品"
                }
            ]
        }
    }

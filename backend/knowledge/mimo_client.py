"""
MiMo-V2.5 多模态理解客户端
用于理解图片、视频内容，提取广告文案信息
"""

import base64
import os
from pathlib import Path
from openai import OpenAI
from backend.config import MIMO_API_KEY, MIMO_BASE_URL, MIMO_MODEL


class MiMoClient:
    """MiMo-V2.5 多模态理解客户端"""

    def __init__(self):
        self.client = OpenAI(
            api_key=MIMO_API_KEY,
            base_url=MIMO_BASE_URL,
        )
        self.model = MIMO_MODEL

    def understand_image(self, image_path: str) -> str:
        """
        理解图片内容，提取广告文案信息

        Args:
            image_path: 图片文件路径

        Returns:
            图片内容描述（重点提取广告相关文字和信息）
        """
        # 读取图片并转为 base64
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # 获取 MIME 类型
        ext = Path(image_path).suffix.lower()
        mime_map = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".gif": "image/gif",
            ".webp": "image/webp", ".bmp": "image/bmp",
        }
        mime_type = mime_map.get(ext, "image/jpeg")

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_data}"
                            }
                        },
                        {
                            "type": "text",
                            "text": """请仔细分析这张图片，提取所有与广告相关的信息：

1. **广告文案**：图片中所有文字内容（标题、正文、标语、促销信息等）
2. **品牌信息**：品牌名称、LOGO描述
3. **产品信息**：产品名称、产品描述
4. **广告类型**：判断这是什么类型的广告（信息流广告/搜索广告/电商广告/品牌广告/应用下载广告）
5. **视觉元素**：图片的整体风格、色调、主要视觉元素描述

请以结构化的方式输出以上信息。"""
                        }
                    ]
                }
            ],
            max_completion_tokens=2000,
        )

        return response.choices[0].message.content or ""

    def understand_video(self, video_path: str, fps: float = 2.0) -> str:
        """
        理解视频内容，提取广告文案信息

        Args:
            video_path: 视频文件路径
            fps: 抽帧率，默认2

        Returns:
            视频内容描述（重点提取广告相关文字和信息）
        """
        # 读取视频并转为 base64
        with open(video_path, "rb") as f:
            video_data = base64.b64encode(f.read()).decode("utf-8")

        # 获取 MIME 类型
        ext = Path(video_path).suffix.lower()
        mime_map = {
            ".mp4": "video/mp4", ".mov": "video/quicktime",
            ".avi": "video/x-msvideo", ".wmv": "video/x-ms-wmv",
        }
        mime_type = mime_map.get(ext, "video/mp4")

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "video_url",
                            "video_url": {
                                "url": f"data:{mime_type};base64,{video_data}"
                            },
                            "fps": fps,
                            "media_resolution": "default"
                        },
                        {
                            "type": "text",
                            "text": """请仔细分析这个视频广告，提取所有相关信息：

1. **广告文案**：视频中出现的所有文字、字幕、旁白内容
2. **品牌信息**：品牌名称、LOGO
3. **产品信息**：产品名称、产品描述
4. **广告类型**：判断这是什么类型的广告
5. **视频内容**：视频的主要情节、场景、人物描述
6. **促销信息**：价格、优惠、活动信息

请以结构化的方式输出以上信息。"""
                        }
                    ]
                }
            ],
            max_completion_tokens=3000,
        )

        return response.choices[0].message.content or ""

    def understand_text_file(self, file_path: str) -> str:
        """
        读取文本文件内容（JSON/MD/TXT）

        Args:
            file_path: 文件路径

        Returns:
            文件内容
        """
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()


# 全局实例
mimo_client = MiMoClient()

"""
文本向量化模块
使用阿里云 DashScope qwen3.7-text-embedding 模型
"""

import dashscope
from http import HTTPStatus
from typing import List, Optional
from backend.config import DASHSCOPE_API_KEY, EMBEDDING_MODEL, EMBEDDING_DIMENSION


class DashScopeEmbedding:
    """
    基于阿里云 DashScope 的文本 Embedding 实现
    使用 qwen3.7-text-embedding 模型
    """

    def __init__(
        self,
        api_key: str = DASHSCOPE_API_KEY,
        model: str = EMBEDDING_MODEL,
        dimension: int = EMBEDDING_DIMENSION
    ):
        self.api_key = api_key
        self.model = model
        self.dimension = dimension

        # 设置 DashScope API Key
        dashscope.api_key = api_key

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        批量向量化文档

        Args:
            texts: 文本列表，最多 20 条

        Returns:
            向量列表
        """
        if not texts:
            return []

        # 分批处理（qwen3.7-text-embedding 最多支持 20 条）
        batch_size = 20
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            embeddings = self._call_embedding_api(batch, text_type="document")
            all_embeddings.extend(embeddings)

        return all_embeddings

    def embed_query(self, text: str) -> List[float]:
        """
        向量化查询文本

        Args:
            text: 查询文本

        Returns:
            向量
        """
        embeddings = self._call_embedding_api([text], text_type="query")
        return embeddings[0] if embeddings else [0.0] * self.dimension

    def _call_embedding_api(
        self,
        texts: List[str],
        text_type: str = "document"
    ) -> List[List[float]]:
        """
        调用 DashScope Embedding API

        Args:
            texts: 文本列表
            text_type: 文本类型，"query" 或 "document"

        Returns:
            向量列表
        """
        try:
            resp = dashscope.TextEmbedding.call(
                model=self.model,
                input=texts,
                dimension=self.dimension,
                text_type=text_type,
                output_type="dense"
            )

            if resp.status_code == HTTPStatus.OK:
                embeddings = []
                for item in resp.output["embeddings"]:
                    embeddings.append(item["embedding"])
                return embeddings
            else:
                print(f"Embedding API 错误: {resp.code} - {resp.message}")
                # 返回零向量作为降级处理
                return [[0.0] * self.dimension for _ in texts]

        except Exception as e:
            print(f"Embedding API 异常: {e}")
            # 返回零向量作为降级处理
            return [[0.0] * self.dimension for _ in texts]


# 全局实例
embedding_model = DashScopeEmbedding()

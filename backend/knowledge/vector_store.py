"""
Chroma 向量数据库操作封装
使用 qwen3.7-text-embedding 模型进行向量化
"""

import chromadb
from chromadb.config import Settings
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from typing import Optional, List
from backend.config import CHROMA_PERSIST_DIR, CHROMA_COLLECTION_NAME


class DashScopeEmbeddingFunction(EmbeddingFunction):
    """
    自定义 Chroma Embedding Function
    使用 DashScope qwen3.7-text-embedding 模型
    """

    def __init__(self):
        from backend.knowledge.embedding import embedding_model
        self.model = embedding_model

    def __call__(self, input: Documents) -> Embeddings:
        """将文档转换为向量"""
        return self.model.embed_documents(input)


class VectorStore:
    """Chroma 向量数据库封装"""

    def __init__(self, persist_dir: str = CHROMA_PERSIST_DIR):
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )
        self._embedding_function = None

    @property
    def embedding_function(self):
        """懒加载 embedding function"""
        if self._embedding_function is None:
            self._embedding_function = DashScopeEmbeddingFunction()
        return self._embedding_function

    def get_or_create_collection(self, name: str = CHROMA_COLLECTION_NAME):
        """获取或创建集合"""
        return self.client.get_or_create_collection(
            name=name,
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"}
        )

    def add_documents(
        self,
        collection_name: str,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str]
    ):
        """添加文档到集合"""
        collection = self.get_or_create_collection(collection_name)
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        return len(documents)

    def query(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = 5,
        where: Optional[dict] = None
    ) -> dict:
        """查询相似文档"""
        collection = self.get_or_create_collection(collection_name)
        query_params = {
            "query_texts": [query_text],
            "n_results": n_results
        }
        if where:
            query_params["where"] = where
        return collection.query(**query_params)

    def delete_collection(self, name: str):
        """删除集合"""
        try:
            self.client.delete_collection(name)
        except ValueError:
            pass

    def list_collections(self) -> list[str]:
        """列出所有集合"""
        return [c.name for c in self.client.list_collections()]

    def get_collection_count(self, name: str = CHROMA_COLLECTION_NAME) -> int:
        """获取集合中的文档数量"""
        try:
            collection = self.get_or_create_collection(name)
            return collection.count()
        except Exception:
            return 0


# 全局实例
vector_store = VectorStore()

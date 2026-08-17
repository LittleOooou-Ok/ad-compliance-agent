"""
知识库管理模块
管理审核规则、案例、敏感词的加载和检索
"""

import json
from pathlib import Path
from typing import Optional
from backend.config import KNOWLEDGE_BASE_DIR
from backend.knowledge.vector_store import vector_store


class RuleManager:
    """规则管理器"""

    def __init__(self):
        self.knowledge_base_dir = KNOWLEDGE_BASE_DIR
        self._sensitive_words_cache = None

    def load_sensitive_words(self) -> list[dict]:
        """加载敏感词库（合并多个词库文件）"""
        if self._sensitive_words_cache is not None:
            return self._sensitive_words_cache

        all_words = []
        words_dir = self.knowledge_base_dir / "sensitive_words"

        # 加载所有 words*.json 文件
        for words_file in sorted(words_dir.glob("words*.json")):
            try:
                with open(words_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    words = data.get("words", [])
                    all_words.extend(words)
            except Exception as e:
                print(f"加载词库失败 {words_file}: {e}")

        # 去重（以 word 为 key）
        seen = set()
        unique_words = []
        for w in all_words:
            if w["word"] not in seen:
                seen.add(w["word"])
                unique_words.append(w)

        self._sensitive_words_cache = unique_words
        return self._sensitive_words_cache

    def load_cases(self) -> list[dict]:
        """加载案例库"""
        cases_file = self.knowledge_base_dir / "cases" / "cases.json"
        if not cases_file.exists():
            return []

        with open(cases_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("cases", [])

    def match_sensitive_words(self, text: str) -> list[dict]:
        """匹配文本中的敏感词"""
        words = self.load_sensitive_words()
        matches = []

        for word_info in words:
            word = word_info["word"]
            if word in text:
                # 找到所有出现位置
                start = 0
                while True:
                    idx = text.find(word, start)
                    if idx == -1:
                        break
                    matches.append({
                        "word": word,
                        "category": word_info["category"],
                        "severity": word_info["severity"],
                        "rule_ref": word_info["rule_ref"],
                        "alternatives": word_info.get("alternatives", []),
                        "position": {"start": idx, "end": idx + len(word)}
                    })
                    start = idx + 1

        return matches

    def search_rules(self, query: str, n_results: int = 5) -> list[dict]:
        """从向量库中搜索相关规则"""
        try:
            results = vector_store.query(
                collection_name="ad_rules",
                query_text=query,
                n_results=n_results
            )

            rules = []
            if results and results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    rules.append({
                        "content": doc,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else 0
                    })
            return rules
        except Exception as e:
            print(f"规则检索失败: {e}")
            return []

    def search_cases(self, query: str, n_results: int = 3) -> list[dict]:
        """从向量库中搜索相似案例"""
        try:
            results = vector_store.query(
                collection_name="ad_cases",
                query_text=query,
                n_results=n_results
            )

            cases = []
            if results and results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    cases.append({
                        "content": doc,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else 0
                    })
            return cases
        except Exception as e:
            print(f"案例检索失败: {e}")
            return []


# 全局实例
rule_manager = RuleManager()

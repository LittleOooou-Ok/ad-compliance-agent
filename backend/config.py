"""
配置管理模块
从环境变量加载配置，提供全局配置访问
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv(Path(__file__).parent.parent / ".env")

# ─── 项目路径 ────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
KNOWLEDGE_BASE_DIR = DATA_DIR / "knowledge_base"
TEST_SET_DIR = DATA_DIR / "test_set"
CHROMA_DIR = DATA_DIR / "chroma_db"
DOCS_DIR = PROJECT_ROOT / "docs"

# ─── DeepSeek API 配置 ────────────────────────────────────
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# 将 DeepSeek API Key 设置为 OPENAI_API_KEY，让 OpenAI Agents SDK 能正常调用
os.environ["OPENAI_API_KEY"] = DEEPSEEK_API_KEY
os.environ["OPENAI_BASE_URL"] = DEEPSEEK_BASE_URL

# 禁用 OpenAI Agents SDK 的 tracing（国内无法访问遥测服务）
os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "1"

# ─── DashScope API 配置（用于 Embedding）────────────────────
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")

# ─── MiMo-V2.5 API 配置（用于多模态理解）────────────────────
MIMO_API_KEY = os.getenv("MIMO_API_KEY", "")
MIMO_BASE_URL = os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
MIMO_MODEL = os.getenv("MIMO_MODEL", "mimo-v2.5")

# ─── Embedding 配置 ────────────────────────────────────────
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "qwen3.7-text-embedding")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1024"))

# ─── Chroma 向量数据库配置 ────────────────────────────────
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", str(CHROMA_DIR))
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "ad_rules")

# ─── 数据库配置 ────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{DATA_DIR / 'ad_review.db'}")

# ─── 服务器配置 ────────────────────────────────────────────
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# ─── 评估配置 ────────────────────────────────────────────
EVAL_TEST_SET_PATH = os.getenv("EVAL_TEST_SET_PATH", str(TEST_SET_DIR / "test_cases.json"))

# ─── MCP 配置（可选）────────────────────────────────────
MCP_SERVER_URLS = [
    url.strip()
    for url in os.getenv("MCP_SERVER_URLS", "").split(",")
    if url.strip()
]

# ─── Agent 配置 ────────────────────────────────────────────
AGENT_CONFIG = {
    "model": DEEPSEEK_MODEL,
    "temperature": 0.1,  # 低温度，保证审核结果稳定性
    "max_tokens": 2000,
}

# ─── 审核阈值配置 ────────────────────────────────────────
REVIEW_THRESHOLDS = {
    "confidence_high": 0.85,      # 高置信度：自动通过/拒绝
    "confidence_low": 0.65,       # 低置信度：需人工复审
    "risk_level_high": 0.7,       # 高风险阈值
    "risk_level_medium": 0.4,     # 中风险阈值
}


def validate_config():
    """验证必要配置是否已设置"""
    errors = []
    if not DEEPSEEK_API_KEY:
        errors.append("DEEPSEEK_API_KEY 未设置，请在 .env 文件中配置")
    if not DASHSCOPE_API_KEY:
        errors.append("DASHSCOPE_API_KEY 未设置，请在 .env 文件中配置（用于 Embedding 向量化）")
    return errors

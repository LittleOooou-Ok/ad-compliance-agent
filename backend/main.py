"""
FastAPI 应用入口
广告素材合规审核 Agent 后端服务
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from backend.config import API_HOST, API_PORT, validate_config
from backend.api.review import router as review_router
from backend.api.batch import router as batch_router
from backend.api.rules import router as rules_router
from backend.api.stats import router as stats_router
from backend.api.eval import router as eval_router
from backend.api.settings import router as settings_router
from backend.api.workflow import router as workflow_router

# 验证配置
config_errors = validate_config()
if config_errors:
    print("⚠️  配置警告:")
    for error in config_errors:
        print(f"   - {error}")

# 创建 FastAPI 应用
app = FastAPI(
    title="广告素材合规审核 Agent",
    description="基于 OpenAI Agents SDK + DeepSeek 的智能广告素材合规审核系统",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(review_router, prefix="/api", tags=["审核"])
app.include_router(batch_router, prefix="/api", tags=["批量审核"])
app.include_router(rules_router, prefix="/api", tags=["知识库管理"])
app.include_router(stats_router, prefix="/api", tags=["数据统计"])
app.include_router(eval_router, prefix="/api", tags=["评估"])
app.include_router(settings_router, prefix="/api", tags=["设置"])
app.include_router(workflow_router, prefix="/api", tags=["工作流"])


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "广告素材合规审核 Agent",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


if __name__ == "__main__":
    print("=" * 50)
    print("广告素材合规审核 Agent")
    print(f"服务地址: http://{API_HOST}:{API_PORT}")
    print(f"API 文档: http://{API_HOST}:{API_PORT}/docs")
    print("=" * 50)
    uvicorn.run(
        "backend.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=True
    )

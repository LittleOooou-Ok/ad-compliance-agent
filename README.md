# 广告素材合规审核 Agent

基于 **OpenAI Agents SDK** + **DeepSeek** 的智能广告素材合规审核系统。

## 项目简介

本项目实现了一个多 Agent 协作的广告素材合规审核系统，能够自动完成素材解析、规则检索、多维度审核、风险评估和报告生成全流程。

### 核心能力

- **多 Agent 自主编排**：4 个专业 Agent 通过 handoff 机制自动串联
- **RAG 知识库检索**：基于《广告法》和平台规范的审核规则库
- **多维度审核**：合规性、真实性、安全性三维审核
- **结构化报告**：自动生成 Markdown 审核报告
- **评估体系**：完整的测评集和评估指标

### 技术栈

| 组件 | 技术选型 |
|------|---------|
| Agent 框架 | OpenAI Agents SDK |
| LLM | DeepSeek API |
| Embedding | qwen3.7-text-embedding (DashScope) |
| 向量数据库 | Chroma |
| Web 框架 | FastAPI |
| 存储 | SQLite |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
copy .env.example .env
# 编辑 .env，填入以下 API Key：
# - DEEPSEEK_API_KEY: DeepSeek API Key (用于 LLM)
# - DASHSCOPE_API_KEY: 阿里云 DashScope API Key (用于 Embedding)
```

### 3. 初始化知识库

```bash
python scripts/init_knowledge_base.py
```

### 4. 启动服务

```bash
python backend/main.py
```

服务启动后访问 `http://localhost:8000/docs` 查看 API 文档。

## 项目结构

```
├── backend/                # 后端代码
│   ├── api/               # API 路由
│   ├── agents/            # Agent 定义
│   │   └── tools/         # Agent 工具
│   ├── knowledge/         # 知识库管理
│   ├── models/            # 数据模型
│   ├── storage/           # 存储层
│   └── evaluation/        # 评估模块
├── data/                   # 数据目录
│   ├── knowledge_base/    # 知识库原始文件
│   ├── test_set/          # 测评集
│   └── chroma_db/         # 向量数据库
├── docs/                   # 文档
├── scripts/                # 工具脚本
└── requirements.txt        # 依赖清单
```

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/review` | POST | 提交素材审核 |
| `/api/report/{id}` | GET | 获取审核报告 |
| `/api/rules` | CRUD | 知识库管理 |
| `/api/stats` | GET | 数据统计 |
| `/api/eval/run` | GET | 运行评估 |

详细接口规范见 `docs/api_spec.md`。

## License

MIT

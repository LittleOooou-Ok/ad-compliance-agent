# 广告素材合规审核 Agent — 架构设计文档

> **版本：** v1.0
> **更新日期：** 2026-08-13

---

## 1. 系统架构总览

```
┌─────────────────────────────────────────────────────────┐
│                    用户交互层（前端）                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐│
│  │ 素材提交  │  │ 结果展示  │  │ 知识库管理│  │ 数据统计 ││
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘│
└─────────────────────────┬───────────────────────────────┘
                          │ REST API
┌─────────────────────────▼───────────────────────────────┐
│                    API 层（FastAPI）                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐│
│  │ /review  │  │ /rules   │  │ /stats   │  │ /eval   ││
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘│
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│              Agent 编排层（OpenAI Agents SDK）              │
│                                                           │
│  ┌─────────────┐                                         │
│  │ Orchestrator │ ← 主编排 Agent                          │
│  └──────┬──────┘                                         │
│         │ handoff                                         │
│  ┌──────▼──────┐  ┌──────────┐  ┌──────────┐           │
│  │   Parser    │→│ Retrieval │→│  Review   │→ Report    │
│  │   Agent     │  │  Agent   │  │  Agent   │  Agent     │
│  └─────────────┘  └──────────┘  └──────────┘           │
│                                                           │
│  工具层：                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ RAG 检索 │  │ 敏感词匹配│  │ 案例检索 │              │
│  └──────────┘  └──────────┘  └──────────┘              │
│                                                           │
│  外部 MCP 接入（可选）：                                    │
│  ┌──────────┐  ┌──────────┐                             │
│  │ MCP 工具 │  │ MCP 工具 │                             │
│  └──────────┘  └──────────┘                             │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                    数据层                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │  Chroma  │  │   JSON   │  │  SQLite  │              │
│  │ 向量数据库│  │ 知识库文件│  │ 审核记录 │              │
│  └──────────┘  └──────────┘  └──────────┘              │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Agent 架构设计

### 2.1 Agent 角色定义

| Agent | 职责 | 输入 | 输出 |
|-------|------|------|------|
| **Orchestrator** | 编排整个审核流程 | 用户审核请求 | 最终审核报告 |
| **Parser Agent** | 解析广告素材 | 广告文案 | 结构化解析结果 |
| **Retrieval Agent** | 检索审核规则 | 解析结果 | 相关规则+敏感词+案例 |
| **Review Agent** | 多维度合规审核 | 规则+素材 | 各维度审核结果 |
| **Report Agent** | 风险评估+报告生成 | 审核结果 | 结构化审核报告 |

### 2.2 Handoff 机制

```
Orchestrator
    │
    │ handoff 1: "解析这个广告素材"
    ▼
Parser Agent
    │
    │ handoff 2: "根据解析结果检索规则"
    ▼
Retrieval Agent
    │
    │ handoff 3: "根据规则进行审核"
    ▼
Review Agent
    │
    │ handoff 4: "生成审核报告"
    ▼
Report Agent
    │
    ▼
返回最终结果
```

### 2.3 工具定义

| 工具 | 功能 | 调用者 |
|------|------|--------|
| `search_ad_rules` | 从向量库检索相关规则 | Retrieval Agent |
| `check_sensitive_words` | 检测敏感词 | Retrieval Agent |
| `search_similar_cases` | 查找相似案例 | Retrieval Agent |
| `call_external_mcp_tool` | 调用外部 MCP 工具 | 任意 Agent |
| `list_available_mcp_servers` | 列出可用 MCP 服务 | 任意 Agent |

---

## 3. 数据流设计

### 3.1 审核流程数据流

```
输入: { content: "广告文案", ad_type: "...", brand_name: "...", product_name: "..." }
    │
    ▼
Step 1: Parser Agent
    输出: {
      brand_name: "...",
      product_name: "...",
      ad_type: "...",
      key_phrases: [...],
      initial_risk_flags: [...]
    }
    │
    ▼
Step 2: Retrieval Agent
    输出: {
      relevant_rules: [...],
      sensitive_words_found: [...],
      similar_cases: [...]
    }
    │
    ▼
Step 3: Review Agent
    输出: {
      dimensions: {
        compliance: { passed, confidence, details },
        authenticity: { passed, confidence, details },
        safety: { passed, confidence, details }
      },
      violations: [...]
    }
    │
    ▼
Step 4: Report Agent
    输出: {
      conclusion: "pass/reject/manual_review",
      risk_level: "low/medium/high",
      confidence: 0.85,
      report_markdown: "..."
    }
```

### 3.2 RAG 检索流程

```
查询: "全网最低价"
    │
    ▼
Chroma 向量检索
    │
    ├── 规则库: 找到 R001（绝对化用语禁止）
    ├── 案例库: 找到 C004（类似违规案例）
    │
    ▼
返回: 规则内容 + 相似案例 + 相关度分数
```

---

## 4. 技术选型详情

### 4.1 核心框架

| 组件 | 选型 | 版本 | 选择理由 |
|------|------|------|---------|
| Agent 框架 | OpenAI Agents SDK | ≥0.1.0 | 原生 handoff + MCP 支持 |
| LLM | DeepSeek API | deepseek-chat | 中文能力强，成本极低 |
| Web 框架 | FastAPI | ≥0.111.0 | 异步支持好，自动 API 文档 |
| 向量数据库 | Chroma | ≥0.5.0 | 轻量级，嵌入式 |
| 数据验证 | Pydantic | ≥2.7.0 | 类型安全，性能好 |

### 4.2 DeepSeek API 兼容性

DeepSeek 提供 OpenAI 兼容的 API 接口：

```python
from openai import OpenAI

client = OpenAI(
    api_key="your-deepseek-api-key",
    base_url="https://api.deepseek.com"
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "Hello"}]
)
```

OpenAI Agents SDK 可直接使用 DeepSeek 的 API。

---

## 5. 部署架构

### 5.1 开发环境

```
本地机器
├── Python 3.10+
├── FastAPI (uvicorn)
├── Chroma (本地持久化)
└── DeepSeek API (远程)
```

### 5.2 生产环境（建议）

```
云服务器
├── Docker 容器
│   ├── FastAPI 应用
│   └── Chroma 服务
├── Nginx 反向代理
├── SQLite / PostgreSQL
└── DeepSeek API (远程)
```

---

## 6. 扩展性设计

### 6.1 新增 Agent

要新增一个 Agent（如"品牌调性审核 Agent"）：

1. 创建 `backend/agents/brand_agent.py`
2. 定义 Agent 的 instructions 和 tools
3. 在 `orchestrator.py` 中添加 handoff

### 6.2 新增工具

要新增一个工具：

1. 在 `backend/agents/tools/` 下创建新文件
2. 使用 `@function_tool` 装饰器定义工具
3. 在需要的 Agent 中注册工具

### 6.3 接入外部 MCP 服务

在 `.env` 中配置 MCP 服务器地址：

```
MCP_SERVER_URLS=http://localhost:3001,http://localhost:3002
```

Agent 可通过 `call_external_mcp_tool` 工具调用外部 MCP 服务。

---

## 7. 性能优化建议

| 优化点 | 方案 | 预期效果 |
|--------|------|---------|
| LLM 调用 | 使用 DeepSeek 缓存机制 | 减少重复调用 |
| 向量检索 | 优化 embedding 模型 | 提高检索准确率 |
| 并发处理 | FastAPI 异步 + 限流 | 支持更多并发 |
| 结果缓存 | Redis 缓存审核结果 | 减少重复审核 |

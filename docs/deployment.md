# 广告素材合规审核 Agent — 部署说明

> **版本：** v1.0
> **更新日期：** 2026-08-13

---

## 1. 环境要求

### 1.1 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10+ / macOS 12+ / Ubuntu 20.04+ |
| Python | 3.10 或更高版本 |
| 内存 | 4GB+ |
| 磁盘空间 | 1GB+ |
| 网络 | 需要访问 DeepSeek API |

### 1.2 Python 依赖

所有依赖已列在 `requirements.txt` 中：

```
openai-agents>=0.1.0
openai>=1.30.0
fastapi>=0.111.0
uvicorn[standard]>=0.30.0
chromadb>=0.5.0
pydantic>=2.7.0
python-dotenv>=1.0.0
jieba>=0.42.0
httpx>=0.27.0
numpy>=1.26.0
tabulate>=0.9.0
```

---

## 2. 安装步骤

### 2.1 克隆项目

```bash
cd D:\AdvertingReview
```

### 2.2 创建虚拟环境（推荐）

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 2.3 安装依赖

```bash
pip install -r requirements.txt
```

### 2.4 配置环境变量

```bash
# 复制环境变量模板
copy .env.example .env

# 编辑 .env 文件，填入你的 DeepSeek API Key
```

需要配置的关键变量：

```env
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

### 2.5 初始化知识库

```bash
python scripts/init_knowledge_base.py
```

成功输出：

```
==================================================
广告素材合规审核 Agent - 知识库初始化
==================================================
正在初始化规则集合...
  加载文件: ad_law_core.md
  加载文件: prohibited_words.md
  ...
  已添加 XX 条规则到向量库

正在初始化案例集合...
  已添加 XX 条案例到向量库

==================================================
知识库初始化完成！
规则数量: XX
案例数量: XX
==================================================
```

---

## 3. 启动服务

### 3.1 直接启动

```bash
python backend/main.py
```

### 3.2 使用 uvicorn 启动

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3.3 验证服务

访问以下地址验证服务是否正常运行：

- **API 文档**：http://localhost:8000/docs
- **ReDoc 文档**：http://localhost:8000/redoc
- **健康检查**：http://localhost:8000/health

---

## 4. 使用示例

### 4.1 提交审核

```bash
curl -X POST http://localhost:8000/api/review \
  -H "Content-Type: application/json" \
  -d '{
    "content": "全网最低价！限时抢购，错过再等一年！",
    "ad_type": "信息流广告"
  }'
```

### 4.2 获取规则列表

```bash
curl http://localhost:8000/api/rules
```

### 4.3 搜索规则

```bash
curl "http://localhost:8000/api/rules/search?q=绝对化用语"
```

### 4.4 获取数据统计

```bash
curl http://localhost:8000/api/stats
```

### 4.5 运行评估

```bash
curl http://localhost:8000/api/eval/run
```

---

## 5. Docker 部署（可选）

### 5.1 创建 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python scripts/init_knowledge_base.py

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 5.2 构建和运行

```bash
# 构建镜像
docker build -t ad-review-agent .

# 运行容器
docker run -p 8000:8000 -e DEEPSEEK_API_KEY=your_key ad-review-agent
```

---

## 6. 常见问题

### 6.1 DeepSeek API 连接失败

**问题**：`openai.APIConnectionError`

**解决**：
1. 检查 `DEEPSEEK_API_KEY` 是否正确配置
2. 检查网络是否能访问 `api.deepseek.com`
3. 检查 API Key 是否有效

### 6.2 Chroma 初始化失败

**问题**：`chromadb.error.ChromaError`

**解决**：
1. 检查 `data/chroma_db` 目录是否存在
2. 检查是否有写入权限
3. 尝试删除 `data/chroma_db` 目录后重新初始化

### 6.3 中文分词问题

**问题**：`jieba` 分词不准确

**解决**：
1. 可以添加自定义词典到 `jieba`
2. 在 `backend/knowledge/rule_manager.py` 中加载自定义词典

---

## 7. 生产环境建议

### 7.1 安全性

- [ ] 配置 CORS 白名单
- [ ] 添加 API 认证（如 API Key）
- [ ] 使用 HTTPS
- [ ] 限制请求频率

### 7.2 可靠性

- [ ] 添加日志系统
- [ ] 配置监控告警
- [ ] 使用数据库持久化（PostgreSQL）
- [ ] 配置备份策略

### 7.3 性能

- [ ] 使用 Redis 缓存
- [ ] 配置负载均衡
- [ ] 优化 embedding 模型
- [ ] 使用消息队列处理异步任务

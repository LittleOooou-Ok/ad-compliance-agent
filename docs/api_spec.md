# 广告素材合规审核 Agent — 前后端对接文档

> **版本：** v1.0
> **更新日期：** 2026-08-13
> **后端地址：** http://localhost:8000

---

## 1. 接口总览

| 接口 | 方法 | 说明 | 认证 |
|------|------|------|------|
| `/api/review` | POST | 提交素材审核 | 无 |
| `/api/report/{review_id}` | GET | 获取审核报告 | 无 |
| `/api/rules` | GET | 获取规则列表 | 无 |
| `/api/rules` | POST | 创建规则 | 无 |
| `/api/rules/{rule_id}` | PUT | 更新规则 | 无 |
| `/api/rules/{rule_id}` | DELETE | 删除规则 | 无 |
| `/api/rules/search` | GET | 搜索规则 | 无 |
| `/api/stats` | GET | 数据统计 | 无 |
| `/api/eval/run` | GET | 运行评估 | 无 |
| `/api/eval/metrics` | GET | 评估指标定义 | 无 |

---

## 2. 审核接口

### 2.1 提交审核

**请求：**
```
POST /api/review
Content-Type: application/json
```

**请求体：**
```json
{
  "content": "广告文案内容（必填）",
  "ad_type": "信息流广告",  // 可选：信息流广告/搜索广告/电商广告/品牌广告/应用下载广告
  "brand_name": "品牌名称",  // 可选
  "product_name": "产品名称", // 可选
  "callback_url": "https://..." // 可选，审核完成回调地址
}
```

**响应（200）：**
```json
{
  "review_id": "uuid-string",
  "conclusion": "pass",  // pass/reject/manual_review
  "confidence": 0.92,
  "risk_level": "low",  // low/medium/high
  "dimensions": {
    "compliance": {
      "passed": true,
      "details": "未发现违规内容",
      "confidence": 0.95
    },
    "authenticity": {
      "passed": true,
      "details": "内容真实",
      "confidence": 0.90
    },
    "safety": {
      "passed": true,
      "details": "无敏感内容",
      "confidence": 0.95
    }
  },
  "violations": [
    {
      "type": "违禁词",  // 违禁词/虚假宣传/夸大功效/敏感内容/行业特殊规定/其他
      "content": "最佳",
      "rule_ref": "广告法第九条第三款",
      "severity": "high",  // high/medium/low
      "suggestion": "建议删除'最佳'一词",
      "position": {"start": 10, "end": 12}
    }
  ],
  "similar_cases": [
    {
      "case_id": "C001",
      "content": "相似案例内容",
      "conclusion": "reject",
      "similarity": 0.85
    }
  ],
  "report_markdown": "完整的 Markdown 审核报告",
  "created_at": "2026-08-13T15:30:00",
  "latency_ms": 6500
}
```

**错误响应：**
```json
{
  "detail": "错误信息"
}
```

### 2.2 获取审核报告

**请求：**
```
GET /api/report/{review_id}
```

**响应：** 同提交审核的响应格式。

---

## 3. 知识库管理接口

### 3.1 获取规则列表

**请求：**
```
GET /api/rules?category=广告法核心条款
```

**参数：**
- `category`（可选）：按类别筛选

**响应：**
```json
{
  "total": 15,
  "rules": [
    {
      "rule_id": "R001",
      "title": "绝对化用语禁止",
      "category": "广告法核心条款",
      "content": "规则内容...",
      "severity": "high",
      "keywords": ["最佳", "最好", "第一"]
    }
  ]
}
```

### 3.2 创建规则

**请求：**
```
POST /api/rules
Content-Type: application/json
```

**请求体：**
```json
{
  "category": "广告法核心条款",  // 必填
  "title": "规则标题",          // 必填
  "content": "规则内容",        // 必填
  "law_reference": "广告法第九条", // 可选
  "severity": "high",           // high/medium/low
  "examples": ["示例1", "示例2"], // 可选
  "keywords": ["关键词1", "关键词2"] // 可选
}
```

**响应：**
```json
{
  "message": "规则创建成功",
  "rule": { ... }
}
```

### 3.3 更新规则

**请求：**
```
PUT /api/rules/{rule_id}
Content-Type: application/json
```

**请求体：** 同创建规则，所有字段可选。

### 3.4 删除规则

**请求：**
```
DELETE /api/rules/{rule_id}
```

**响应：**
```json
{
  "message": "规则删除成功"
}
```

### 3.5 搜索规则

**请求：**
```
GET /api/rules/search?q=绝对化用语
```

**响应：**
```json
{
  "query": "绝对化用语",
  "total": 3,
  "results": [ ... ]
}
```

---

## 4. 数据统计接口

**请求：**
```
GET /api/stats
```

**响应：**
```json
{
  "total_reviews": 150,
  "pass_rate": 0.65,
  "reject_rate": 0.25,
  "manual_review_rate": 0.10,
  "avg_latency_ms": 6200,
  "avg_confidence": 0.88,
  "violation_distribution": {
    "违禁词": 15,
    "虚假宣传": 8,
    "夸大功效": 5,
    "敏感内容": 2
  },
  "risk_distribution": {
    "low": 98,
    "medium": 30,
    "high": 22
  },
  "dimension_stats": {
    "compliance": {"passed": 120, "total": 150, "pass_rate": 0.80},
    "authenticity": {"passed": 135, "total": 150, "pass_rate": 0.90},
    "safety": {"passed": 145, "total": 150, "pass_rate": 0.97}
  }
}
```

---

## 5. 评估接口

### 5.1 运行评估

**请求：**
```
GET /api/eval/run
```

**响应：**
```json
{
  "status": "ready",
  "test_set_info": {
    "total_cases": 100,
    "pass_cases": 50,
    "reject_cases": 30,
    "manual_review_cases": 20,
    "difficulty_distribution": {
      "easy": 40,
      "medium": 35,
      "hard": 25
    },
    "violation_distribution": {
      "违禁词": 10,
      "虚假宣传": 10,
      "夸大功效": 5,
      "敏感内容": 5
    }
  },
  "message": "测评集加载成功"
}
```

### 5.2 获取评估指标定义

**请求：**
```
GET /api/eval/metrics
```

**响应：** 返回评估体系中使用的各项指标定义。

---

## 6. 前端功能建议

### 6.1 素材提交页

**功能：**
- 文本输入框：输入广告文案（必填）
- 下拉选择：选择广告类型（可选）
- 输入框：品牌名称、产品名称（可选）
- 提交按钮：调用 `POST /api/review`
- 加载状态：显示审核进度

**交互：**
1. 用户输入广告文案
2. 点击提交，显示"审核中..."
3. 审核完成后，跳转到结果展示页

### 6.2 审核结果展示页

**功能：**
- 审核结论卡片：显示通过/拒绝/人工复审
- 风险等级标签：低/中/高
- 置信度进度条
- 各维度审核结果（合规性、真实性、安全性）
- 违规点列表：显示违规内容、法规依据、修改建议
- 相似案例参考
- 审核报告导出（Markdown）

### 6.3 知识库管理页

**功能：**
- 规则列表：分页展示所有规则
- 规则搜索：关键词搜索
- 规则编辑：新增/编辑/删除规则
- 规则分类：按类别筛选

### 6.4 数据统计页

**功能：**
- 审核总量统计
- 通过率/拒绝率饼图
- 违规类型分布柱状图
- 风险等级分布
- 平均审核耗时趋势
- 各维度通过率雷达图

### 6.5 评估页

**功能：**
- 一键运行评估
- 评估指标展示（准确率、召回率、F1 等）
- 测评集信息展示
- Bad Case 列表

---

## 7. 错误码说明

| HTTP 状态码 | 说明 |
|------------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

---

## 8. 注意事项

1. **审核响应时间**：审核接口平均响应时间 5-10 秒，前端需做好加载状态展示
2. **并发限制**：Demo 阶段建议限制并发数，避免 API 过载
3. **数据持久化**：当前使用内存存储，重启后数据丢失。生产环境应接入数据库
4. **CORS**：已配置允许所有来源，生产环境应限制

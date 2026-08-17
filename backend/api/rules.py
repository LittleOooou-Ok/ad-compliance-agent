"""
知识库管理 API 路由
管理审核规则、案例、敏感词
"""

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from typing import Optional

from backend.models.rule import Rule, RuleCreate, RuleUpdate, RuleCategory, RuleSeverity
from backend.config import KNOWLEDGE_BASE_DIR

router = APIRouter()


@router.get("/rules")
async def list_rules(category: Optional[str] = None):
    """
    获取规则列表

    Args:
        category: 可选，按类别筛选
    """
    rules = _load_all_rules()

    if category:
        rules = [r for r in rules if r.get("category") == category]

    return {
        "total": len(rules),
        "rules": rules
    }


@router.get("/rules/search")
async def search_rules(q: str):
    """搜索规则"""
    rules = _load_all_rules()
    results = []

    q_lower = q.lower()
    for rule in rules:
        if (q_lower in rule.get("title", "").lower() or
            q_lower in rule.get("content", "").lower() or
            any(q_lower in kw.lower() for kw in rule.get("keywords", []))):
            results.append(rule)

    return {
        "query": q,
        "total": len(results),
        "results": results
    }


@router.get("/rules/{rule_id}")
async def get_rule(rule_id: str):
    """获取单条规则详情"""
    rules = _load_all_rules()
    for rule in rules:
        if rule.get("rule_id") == rule_id:
            return rule
    raise HTTPException(status_code=404, detail="规则不存在")


@router.post("/rules")
async def create_rule(rule: RuleCreate):
    """创建新规则"""
    rules = _load_all_rules()

    # 生成规则 ID
    rule_id = f"R{len(rules) + 1:03d}"

    new_rule = {
        "rule_id": rule_id,
        "category": rule.category.value,
        "title": rule.title,
        "content": rule.content,
        "law_reference": rule.law_reference,
        "severity": rule.severity.value,
        "examples": rule.examples,
        "keywords": rule.keywords,
    }

    rules.append(new_rule)
    _save_rules(rules)

    return {"message": "规则创建成功", "rule": new_rule}


@router.put("/rules/{rule_id}")
async def update_rule(rule_id: str, rule_update: RuleUpdate):
    """更新规则"""
    rules = _load_all_rules()

    for i, rule in enumerate(rules):
        if rule.get("rule_id") == rule_id:
            update_data = rule_update.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                if hasattr(value, 'value'):
                    rules[i][key] = value.value
                else:
                    rules[i][key] = value
            _save_rules(rules)
            return {"message": "规则更新成功", "rule": rules[i]}

    raise HTTPException(status_code=404, detail="规则不存在")


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str):
    """删除规则"""
    rules = _load_all_rules()
    original_count = len(rules)
    rules = [r for r in rules if r.get("rule_id") != rule_id]

    if len(rules) == original_count:
        raise HTTPException(status_code=404, detail="规则不存在")

    _save_rules(rules)
    return {"message": "规则删除成功"}


def _load_all_rules() -> list[dict]:
    """加载所有规则"""
    rules = []
    rules_dir = KNOWLEDGE_BASE_DIR / "rules"

    for md_file in rules_dir.rglob("*.md"):
        rules.extend(_parse_markdown_rules(md_file))

    return rules


def _parse_markdown_rules(file_path: Path) -> list[dict]:
    """从 Markdown 文件解析规则"""
    rules = []
    current_rule = None
    current_content = []

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip()

            if line.startswith("## 规则 "):
                if current_rule:
                    current_rule["content"] = "\n".join(current_content)
                    rules.append(current_rule)

                parts = line.split("：")
                rule_id = parts[0].replace("## 规则 ", "").strip()
                title = parts[1].strip() if len(parts) > 1 else line

                current_rule = {
                    "rule_id": rule_id,
                    "title": title,
                    "category": file_path.stem,
                    "severity": "high",
                    "keywords": []
                }
                current_content = [line]
            elif current_rule:
                current_content.append(line)

        if current_rule:
            current_rule["content"] = "\n".join(current_content)
            rules.append(current_rule)

    return rules


def _save_rules(rules: list[dict]):
    """保存规则（追加到自定义规则文件）"""
    custom_rules_file = KNOWLEDGE_BASE_DIR / "rules" / "custom_rules.json"
    with open(custom_rules_file, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)

"""
初始化知识库脚本
将知识库文件加载到 Chroma 向量数据库
"""

import sys
import json
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.knowledge.vector_store import vector_store
from backend.config import KNOWLEDGE_BASE_DIR


def load_rules_from_markdown(file_path: Path) -> list[dict]:
    """从 Markdown 文件加载规则"""
    rules = []
    current_rule = None
    current_content = []

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip()

            # 检测规则标题
            if line.startswith("## 规则 "):
                # 保存上一条规则
                if current_rule:
                    current_rule["content"] = "\n".join(current_content)
                    rules.append(current_rule)

                # 开始新规则
                rule_id = line.split("：")[0].replace("## 规则 ", "").strip()
                title = line.split("：")[1].strip() if "：" in line else line
                current_rule = {
                    "rule_id": rule_id,
                    "title": title,
                    "category": file_path.stem,
                    "source_file": str(file_path.name)
                }
                current_content = [line]
            elif current_rule:
                current_content.append(line)

        # 保存最后一条规则
        if current_rule:
            current_rule["content"] = "\n".join(current_content)
            rules.append(current_rule)

    return rules


def init_rules_collection():
    """初始化规则集合"""
    print("正在初始化规则集合...")

    # 清空旧数据（如果存在）
    try:
        vector_store.delete_collection("ad_rules")
    except Exception:
        pass

    rules_dir = KNOWLEDGE_BASE_DIR / "rules"
    all_rules = []

    # 加载所有 Markdown 规则文件
    for md_file in rules_dir.rglob("*.md"):
        print(f"  加载文件: {md_file.name}")
        rules = load_rules_from_markdown(md_file)
        all_rules.extend(rules)

    if not all_rules:
        print("  未找到规则文件")
        return

    # 准备数据
    documents = [rule["content"] for rule in all_rules]
    metadatas = [{
        "rule_id": rule["rule_id"],
        "title": rule["title"],
        "category": rule["category"],
        "source_file": rule["source_file"]
    } for rule in all_rules]
    ids = [f"rule_{rule['rule_id']}" for rule in all_rules]

    # 添加到向量库
    count = vector_store.add_documents(
        collection_name="ad_rules",
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    print(f"  已添加 {count} 条规则到向量库")


def init_cases_collection():
    """初始化案例集合"""
    print("正在初始化案例集合...")

    # 清空旧数据（如果存在）
    try:
        vector_store.delete_collection("ad_cases")
    except Exception:
        pass

    cases_file = KNOWLEDGE_BASE_DIR / "cases" / "cases.json"
    if not cases_file.exists():
        print("  未找到案例文件")
        return

    with open(cases_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        cases = data.get("cases", [])

    if not cases:
        print("  案例文件为空")
        return

    # 准备数据
    documents = [case["content"] for case in cases]
    metadatas = [{
        "case_id": str(case["case_id"]),
        "conclusion": str(case["conclusion"]),
        "violation_type": str(case.get("violation_type") or ""),
        "ad_type": str(case.get("ad_type") or "")
    } for case in cases]
    ids = [f"case_{case['case_id']}" for case in cases]

    # 添加到向量库
    count = vector_store.add_documents(
        collection_name="ad_cases",
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    print(f"  已添加 {count} 条案例到向量库")


def main():
    """主函数"""
    print("=" * 50)
    print("广告素材合规审核 Agent - 知识库初始化")
    print("=" * 50)

    init_rules_collection()
    print()
    init_cases_collection()

    print()
    print("=" * 50)
    print("知识库初始化完成！")
    print(f"规则数量: {vector_store.get_collection_count('ad_rules')}")
    print(f"案例数量: {vector_store.get_collection_count('ad_cases')}")
    print("=" * 50)


if __name__ == "__main__":
    main()

"""
审核 API 路由
支持文本输入和文件上传（图片、视频、JSON、MD）
"""

import json
import time
import uuid
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional, List
from agents import Runner

from backend.models.review_result import ReviewResult, ReviewConclusion, RiskLevel, Violation, DimensionResult, SimilarCase
from backend.review_agents.orchestrator import create_orchestrator
from backend.knowledge.mimo_client import mimo_client

router = APIRouter()

# 内存存储（Demo 阶段）
review_store: dict[str, ReviewResult] = {}

# 上传文件临时目录
UPLOAD_DIR = Path(tempfile.gettempdir()) / "ad_review_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# 文件类型分类
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".wmv"}
TEXT_EXTS = {".json", ".md", ".txt"}


@router.post("/review", response_model=ReviewResult)
async def submit_review(
    content: Optional[str] = Form(None, description="广告文案文本（可选）"),
    files: Optional[List[UploadFile]] = File(None, description="上传文件（图片/视频/JSON/MD，可多选）"),
):
    """
    提交广告素材审核

    支持两种输入方式（可同时使用）：
    1. 直接输入文本
    2. 上传文件（图片、视频、JSON、MD）
    """
    review_id = str(uuid.uuid4())
    start_time = time.time()

    try:
        extracted_contents = []

        # 处理文本输入
        if content and content.strip():
            extracted_contents.append(f"【用户输入文本】\n{content}")

        # 处理上传的文件
        uploaded_file_paths = []
        if files:
            for file in files:
                file_content, temp_path = await _process_uploaded_file(file)
                if file_content:
                    extracted_contents.append(file_content)
                if temp_path:
                    uploaded_file_paths.append(temp_path)

        if not extracted_contents:
            raise HTTPException(status_code=400, detail="请提供广告文案文本或上传文件")

        # 合并所有内容
        full_content = "\n\n---\n\n".join(extracted_contents)

        # 调用 Agent 审核
        orchestrator = create_orchestrator()
        prompt = f"""请审核以下广告素材：

{full_content}

请按照标准流程完成审核：先调用敏感词检测工具，再调用规则检索工具，然后调用案例检索工具，最后给出结构化的审核结果。"""

        result = await Runner.run(orchestrator, prompt)
        latency_ms = int((time.time() - start_time) * 1000)

        final_output = result.final_output
        review_result = _parse_agent_output(review_id, final_output, latency_ms)
        review_store[review_id] = review_result

        # 保存到配置的文件夹
        try:
            from backend.api.settings import save_review_result
            # 使用第一个上传的文件路径作为源文件
            source_path = uploaded_file_paths[0] if uploaded_file_paths else None
            save_review_result(
                conclusion=review_result.conclusion.value,
                file_name=files[0].filename if files else f"review_{review_id[:8]}",
                content=full_content,
                report=review_result.report_markdown,
                source_path=source_path
            )
        except:
            pass

        return review_result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"审核失败: {str(e)}")


@router.get("/report/{review_id}", response_model=ReviewResult)
async def get_report(review_id: str):
    """获取审核报告"""
    if review_id not in review_store:
        raise HTTPException(status_code=404, detail="审核记录不存在")
    return review_store[review_id]


async def _process_uploaded_file(file: UploadFile) -> tuple:
    """处理上传的文件，返回 (内容, 临时文件路径)"""
    filename = file.filename or "unknown"
    ext = Path(filename).suffix.lower()

    # 保存临时文件
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}{ext}"
    with open(temp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 文件大小限制
    MAX_IMAGE_SIZE = 20 * 1024 * 1024
    MAX_VIDEO_SIZE = 40 * 1024 * 1024
    MAX_TEXT_SIZE = 100 * 1024 * 1024
    MAX_JSON_ITEMS = 20

    try:
        file_size = temp_path.stat().st_size

        if ext in IMAGE_EXTS:
            if file_size > MAX_IMAGE_SIZE:
                return f"【图片文件过大：{filename}】{file_size/1024/1024:.1f}MB，限制20MB", None
            description = mimo_client.understand_image(str(temp_path))
            return f"【图片文件：{filename}】\n{description}", str(temp_path)

        elif ext in VIDEO_EXTS:
            if file_size > MAX_VIDEO_SIZE:
                return f"【视频文件过大：{filename}】{file_size/1024/1024:.1f}MB，限制40MB", None
            description = mimo_client.understand_video(str(temp_path))
            return f"【视频文件：{filename}】\n{description}", str(temp_path)

        elif ext in TEXT_EXTS:
            if file_size > MAX_TEXT_SIZE:
                return f"【文本文件过大：{filename}】{file_size/1024/1024:.1f}MB", None
            content = mimo_client.understand_text_file(str(temp_path))

            if ext == ".json":
                try:
                    data = json.loads(content)
                    if isinstance(data, list):
                        items = data[:MAX_JSON_ITEMS] if len(data) > MAX_JSON_ITEMS else data
                        parts = []
                        for i, item in enumerate(items):
                            if isinstance(item, dict):
                                text = item.get("content", "") or item.get("text", "") or item.get("ad", "") or json.dumps(item, ensure_ascii=False)
                            else:
                                text = str(item)
                            parts.append(f"【广告素材 {i+1}】\n{text}")
                        suffix = f"\n\n（共 {len(data)} 条，仅处理前 {len(items)} 条）" if len(data) > MAX_JSON_ITEMS else ""
                        return "\n\n---\n\n".join(parts) + suffix, None
                except json.JSONDecodeError:
                    pass

            return f"【文本文件：{filename}】\n{content}", None

        else:
            return f"【不支持的文件格式：{filename}】", None

    except Exception as e:
        return f"【文件处理失败：{filename}】错误：{str(e)}", None
    finally:
        # 不删除临时文件，因为可能需要保存
        pass


def _parse_agent_output(review_id: str, output: str, latency_ms: int) -> ReviewResult:
    """解析 Agent 输出为结构化结果"""
    import re

    # 尝试多种方式提取 JSON
    data = {}
    json_str = ""

    # 方式1：提取 ```json ... ``` 块
    json_start = output.find("```json")
    json_end = output.find("```", json_start + 7)
    if json_start != -1 and json_end != -1:
        json_str = output[json_start + 7:json_end].strip()

    # 方式2：提取 { ... } 块
    if not json_str:
        brace_start = output.find("{")
        brace_end = output.rfind("}")
        if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
            json_str = output[brace_start:brace_end + 1]

    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        data = {}

    # 提取结论
    conclusion_str = data.get("conclusion", "manual_review")
    if conclusion_str not in ("pass", "reject", "manual_review"):
        # 从文本推断
        output_lower = output.lower()
        if "reject" in output_lower or "拒绝" in output_lower:
            conclusion_str = "reject"
        elif "pass" in output_lower or "通过" in output_lower:
            conclusion_str = "pass"
        else:
            conclusion_str = "manual_review"

    # 提取并验证置信度
    confidence = data.get("confidence", 0.65)
    if isinstance(confidence, str):
        try:
            confidence = float(confidence.replace("%", ""))
            if confidence > 1:
                confidence = confidence / 100
        except:
            confidence = 0.65
    confidence = max(0.40, min(0.95, float(confidence)))

    # 强制执行置信度规则
    if conclusion_str == "reject" and confidence < 0.75:
        conclusion_str = "manual_review"  # 置信度不足，改为复审
    elif conclusion_str == "pass" and confidence < 0.60:
        conclusion_str = "manual_review"  # 置信度不足，改为复审

    try:
        conclusion = ReviewConclusion(conclusion_str)
    except ValueError:
        conclusion = ReviewConclusion.MANUAL_REVIEW

    # 提取风险等级
    risk_str = data.get("risk_level", "medium")
    if risk_str not in ("low", "medium", "high"):
        risk_str = "medium"

    # 根据结论调整风险等级
    if conclusion_str == "pass":
        risk_str = "low"
    elif conclusion_str == "reject":
        risk_str = "high"
    elif conclusion_str == "manual_review":
        risk_str = "medium"

    try:
        risk_level = RiskLevel(risk_str)
    except ValueError:
        risk_level = RiskLevel.MEDIUM

    # 提取维度结果（保证三个维度都存在）
    default_dims = {"compliance", "authenticity", "safety"}
    dimensions = {}
    dims_data = data.get("dimensions", {})
    for dim_name in default_dims:
        dim_data = dims_data.get(dim_name, {})
        if isinstance(dim_data, dict):
            dim_confidence = dim_data.get("confidence", confidence)
            dim_confidence = max(0.40, min(0.95, float(dim_confidence)))
            dimensions[dim_name] = DimensionResult(
                passed=dim_data.get("passed", False),
                details=dim_data.get("details", "待审核"),
                confidence=dim_confidence
            )
        else:
            dimensions[dim_name] = DimensionResult(
                passed=False, details="待审核", confidence=confidence
            )

    # 提取违规点
    violations = []
    for v in data.get("violations", []):
        if isinstance(v, dict):
            violations.append(Violation(
                type=str(v.get("type", "其他")),
                content=str(v.get("content", "")),
                rule_ref=str(v.get("rule_ref", "")),
                severity=str(v.get("severity", "medium")),
                suggestion=str(v.get("suggestion", ""))
            ))

    # 提取相似案例
    similar_cases = []
    for c in data.get("similar_cases", []):
        if isinstance(c, dict):
            similar_cases.append(SimilarCase(
                case_id=str(c.get("case_id", "")),
                content=str(c.get("content", "")),
                conclusion=str(c.get("conclusion", "")),
                similarity=float(c.get("similarity", 0.0))
            ))

    # 构建报告
    report_markdown = data.get("report_markdown", "")
    if not report_markdown:
        # 使用原始输出作为报告
        if output and len(output) > 100:
            report_markdown = output
        else:
            report_markdown = _generate_default_report(
                conclusion, risk_level, confidence, violations
            )

    return ReviewResult(
        review_id=review_id,
        conclusion=conclusion,
        confidence=confidence,
        risk_level=risk_level,
        dimensions=dimensions,
        violations=violations,
        similar_cases=similar_cases,
        report_markdown=report_markdown,
        latency_ms=latency_ms,
    )


def _generate_default_report(
    conclusion: ReviewConclusion,
    risk_level: RiskLevel,
    confidence: float,
    violations: list[Violation]
) -> str:
    """生成默认的 Markdown 报告"""
    emoji_map = {
        ReviewConclusion.PASS: "✅",
        ReviewConclusion.REJECT: "❌",
        ReviewConclusion.MANUAL_REVIEW: "⚠️"
    }
    conclusion_text = {
        ReviewConclusion.PASS: "审核通过",
        ReviewConclusion.REJECT: "审核拒绝",
        ReviewConclusion.MANUAL_REVIEW: "需人工复审"
    }

    report = f"""{emoji_map[conclusion]} {conclusion_text[conclusion]}

**风险等级**：{risk_level.value}
**置信度**：{confidence:.0%}
"""

    if violations:
        report += "\n**违规点**：\n"
        for v in violations:
            report += f"- [{v.severity}] {v.type}：{v.content}\n"
            report += f"  - 法规依据：{v.rule_ref}\n"
            report += f"  - 修改建议：{v.suggestion}\n"

    report += f"\n---\n*审核时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"

    return report

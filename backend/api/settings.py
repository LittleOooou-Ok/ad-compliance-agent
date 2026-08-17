"""
设置 API 路由
管理处理参数和保存文件夹
"""

import json
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from backend.config import DATA_DIR

router = APIRouter()

SETTINGS_FILE = DATA_DIR / "settings.json"

# 默认设置
DEFAULT_SETTINGS = {
    "concurrent_workers": 5,
    "max_items_per_file": 20,
    "save_folders": {
        "pass": "",
        "manual_review": "",
        "reject": ""
    }
}


class SaveFolders(BaseModel):
    pass_folder: str = ""
    manual_review: str = ""
    reject: str = ""


class AppSettings(BaseModel):
    concurrent_workers: int = 5
    max_items_per_file: int = 20
    save_folders: SaveFolders = SaveFolders()


def load_settings() -> dict:
    """加载设置"""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict):
    """保存设置"""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


@router.get("/settings")
async def get_settings():
    """获取当前设置"""
    return load_settings()


@router.post("/settings")
async def update_settings(settings: dict):
    """更新设置"""
    current = load_settings()

    # 合并设置
    if "concurrent_workers" in settings:
        current["concurrent_workers"] = settings["concurrent_workers"]
    if "max_items_per_file" in settings:
        current["max_items_per_file"] = settings["max_items_per_file"]
    if "save_folders" in settings:
        current["save_folders"] = settings["save_folders"]

    save_settings(current)
    return current


def get_save_folder(conclusion: str) -> Optional[str]:
    """获取指定结论的保存文件夹路径"""
    settings = load_settings()
    folders = settings.get("save_folders", {})

    folder_map = {
        "pass": folders.get("pass", ""),
        "manual_review": folders.get("manual_review", ""),
        "reject": folders.get("reject", ""),
    }

    folder = folder_map.get(conclusion, "")
    return folder if folder else None


def save_review_result(conclusion: str, file_name: str, content: str, report: str, source_path: str = None):
    """
    保存审核结果到指定文件夹

    Args:
        conclusion: 审核结论 (pass/reject/manual_review)
        file_name: 文件名
        content: 原始内容
        report: 审核报告
        source_path: 源文件路径（图片/视频时使用）
    """
    folder = get_save_folder(conclusion)
    if not folder:
        return

    folder_path = Path(folder)
    folder_path.mkdir(parents=True, exist_ok=True)

    # 判断是否为图片/视频文件
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
    video_exts = {".mp4", ".mov", ".avi", ".wmv"}

    safe_name = file_name.replace("/", "_").replace("\\", "_").replace(":", "_")

    # 如果有源文件且是图片/视频，直接复制源文件
    if source_path and Path(source_path).exists():
        ext = Path(source_path).suffix.lower()

        if ext in image_exts or ext in video_exts:
            # 复制源文件到目标文件夹
            import shutil
            target_file = folder_path / safe_name
            # 避免覆盖同名文件
            if target_file.exists():
                stem = target_file.stem
                suffix = target_file.suffix
                counter = 1
                while target_file.exists():
                    target_file = folder_path / f"{stem}_{counter}{suffix}"
                    counter += 1
            shutil.copy2(source_path, target_file)

            # 同时保存审核报告为同名txt
            report_file = folder_path / f"{target_file.stem}_审核报告.txt"
            with open(report_file, "w", encoding="utf-8") as f:
                f.write(f"文件名: {file_name}\n")
                f.write(f"审核结论: {conclusion}\n")
                f.write(f"{'='*50}\n\n")
                f.write(f"审核报告:\n{report}\n")

            return

    # 文本/JSON文件：保存为txt
    output_file = folder_path / f"{safe_name}_审核结果.txt"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"文件名: {file_name}\n")
        f.write(f"审核结论: {conclusion}\n")
        f.write(f"{'='*50}\n\n")
        f.write(f"原始内容:\n{content}\n\n")
        f.write(f"{'='*50}\n\n")
        f.write(f"审核报告:\n{report}\n")

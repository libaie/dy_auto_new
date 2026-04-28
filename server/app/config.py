import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()

# 项目根目录 (server/)
SERVER_DIR = Path(__file__).parent.parent
CONFIG_DIR = SERVER_DIR / "config"
DATA_DIR = SERVER_DIR / "app" / "data"

# 环境变量
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
DEVICE_SECRET = os.getenv("DEVICE_SECRET", "change-me-to-a-random-string")


def _load_yaml(filename: str) -> dict[str, Any]:
    """加载 YAML 配置文件"""
    filepath = CONFIG_DIR / filename
    if not filepath.exists():
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_accounts_config() -> list[dict[str, Any]]:
    """加载账号配置"""
    data = _load_yaml("accounts.yaml")
    return data.get("accounts", [])


def load_selectors_config() -> tuple[int, list[dict[str, Any]]]:
    """加载选择器配置，返回 (version, selectors)"""
    data = _load_yaml("selectors.yaml")
    version = data.get("version", 1)
    selectors = data.get("selectors", [])
    return version, selectors


def load_task_templates() -> list[dict[str, Any]]:
    """加载任务模板"""
    data = _load_yaml("tasks.yaml")
    return data.get("task_templates", [])


def save_tasks_to_file(tasks: list[dict[str, Any]]) -> None:
    """持久化任务列表到文件（MVP 简单存储）"""
    filepath = DATA_DIR / "tasks.json"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    import json
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2, default=str)


def load_tasks_from_file() -> list[dict[str, Any]]:
    """从文件加载任务列表"""
    filepath = DATA_DIR / "tasks.json"
    if not filepath.exists():
        return []
    import json
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


# 反检测默认配置（可通过环境变量覆盖）
ANTI_DETECT_CONFIG_VERSION = 1  # 修改配置时递增此版本号

ANTI_DETECT_CONFIG = {
    "delay_min": 1000,
    "delay_max": 5000,
    "rhythm_variation": 0.3,
    "pause_probability": 0.1,
    "pause_min": 5000,
    "pause_max": 15000,
    "active_hours": {
        "start": 7,
        "end": 23,
        "peaks": [
            {"start": 7, "end": 9, "weight": 20},
            {"start": 11, "end": 13, "weight": 25},
            {"start": 17, "end": 20, "weight": 30},
            {"start": 20, "end": 23, "weight": 25},
        ],
    },
}

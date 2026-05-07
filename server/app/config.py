import os
import sys
import warnings
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

# Admin 认证
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-jwt-secret-key")
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))


def _check_default_credentials():
    """Check if default credentials are being used and warn."""
    defaults_used = []
    if DEVICE_SECRET == "change-me-to-a-random-string":
        defaults_used.append("DEVICE_SECRET")
    if ADMIN_PASSWORD == "admin123":
        defaults_used.append("ADMIN_PASSWORD")
    if JWT_SECRET == "change-me-jwt-secret-key":
        defaults_used.append("JWT_SECRET")

    if not defaults_used:
        return

    msg = (
        f"WARNING: Using default credentials for: {', '.join(defaults_used)}. "
        f"Set these environment variables before deploying to production."
    )

    print(f"WARNING: {msg}", file=sys.stderr)


_check_default_credentials()


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

# 设备端配置（通过 register/poll 下发给设备）
DEVICE_CONFIG = {
    "poll_interval": int(os.getenv("DEVICE_POLL_INTERVAL", "10000")),
    "heartbeat_interval": int(os.getenv("DEVICE_HEARTBEAT_INTERVAL", "60000")),
    "log_level": os.getenv("DEVICE_LOG_LEVEL", "info"),
}

# AI Content Generation (DeepSeek / OpenAI 兼容格式)
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.deepseek.com")
AI_MODEL = os.getenv("AI_MODEL", "deepseek-chat")
AI_PROVIDER = os.getenv("AI_PROVIDER", "deepseek")  # deepseek / openai / anthropic
AI_MAX_RETRIES = int(os.getenv("AI_MAX_RETRIES", "3"))
AI_THINKING = os.getenv("AI_THINKING", "max")  # disabled / low / medium / high / xhigh / max

# Thinking level → budget_tokens mapping
AI_THINKING_LEVELS = {
    "disabled": 0,
    "low": 1024,
    "medium": 2048,
    "high": 4096,
    "xhigh": 8192,
    "max": 16384,
}


def _resolve_ai_config(db=None):
    """从 DB 读取 AI 配置，fallback 到环境变量。内部使用，含 API Key。"""
    api_key = AI_API_KEY
    base_url = AI_BASE_URL
    model = AI_MODEL

    thinking = AI_THINKING

    if db:
        try:
            from app.db_models import SystemSetting
            settings = {s.key: s.value for s in db.query(SystemSetting).all()}
            api_key = settings.get("ai_api_key") or api_key
            base_url = settings.get("ai_base_url") or base_url
            model = settings.get("ai_model") or model
            thinking = settings.get("ai_thinking", thinking)
        except Exception:
            pass

    level = thinking if thinking in AI_THINKING_LEVELS else "max"
    budget = AI_THINKING_LEVELS[level]

    return {
        "api_key": api_key,
        "api_url": f"{base_url}/v1/chat/completions",
        "model": model,
        "thinking_enabled": level != "disabled",
        "thinking_budget": budget,
        "thinking_level": level,
    }


def get_ai_config(db=None):
    """返回给设备端的 AI 配置（不含 API Key）。"""
    cfg = _resolve_ai_config(db)
    if not cfg["api_key"]:
        return None
    return {
        "api_key": "",  # 不暴露 API Key 给设备端，设备通过服务端代理调用 AI
        "api_url": cfg["api_url"],
        "model": cfg["model"],
    }


def get_ai_config_with_key(db=None):
    """服务端内部使用，含 API Key（仅供 ai-proxy 等服务端端点使用）。"""
    cfg = _resolve_ai_config(db)
    if not cfg["api_key"]:
        return None
    return cfg

# Server — Complete Source
Total files: 49

---
## app/config.py

```python
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
    """Check if default credentials are being used and warn/error."""
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

    if not DEBUG:
        print(f"FATAL: {msg}", file=sys.stderr)
        sys.exit(1)

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
    "low": 2048,
    "medium": 4096,
    "high": 8192,
    "xhigh": 16384,
    "max": 49152,
}


def _resolve_ai_config(db=None):
    """从 DB 读取 AI 配置，fallback 到环境变量。内部使用，含 API Key。
    Key 命名：llm_* 优先（新），ai_* 作为 fallback（旧，兼容期保留）。
    """
    api_key = os.getenv("AI_API_KEY", "")
    base_url = os.getenv("AI_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("AI_MODEL", "deepseek-chat")
    thinking = os.getenv("AI_THINKING", "max")

    if db:
        try:
            from app.db_models import SystemSetting
            settings = {s.key: s.value for s in db.query(SystemSetting).all()}
            # llm_* keys take priority (new naming), ai_* fallback (legacy)
            api_key = settings.get("llm_api_key") or settings.get("ai_api_key") or api_key
            base_url = settings.get("llm_base_url") or settings.get("ai_base_url") or base_url
            model = settings.get("llm_model") or settings.get("ai_model") or model
            db_thinking = settings.get("llm_thinking") or settings.get("ai_thinking")
            if db_thinking:
                thinking = db_thinking
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


from datetime import datetime, timezone, timedelta

_BJ_TZ = timezone(timedelta(hours=8))


def bj_now() -> datetime:
    """返回北京时间（UTC+8）的 naive datetime，用于数据库存储。"""
    return datetime.now(_BJ_TZ).replace(tzinfo=None)


# --- Pixelle-Video 集成 ---
PIXELLE_VIDEO_URL = os.getenv("PIXELLE_VIDEO_URL", "http://localhost:8500")
PIXELLE_VIDEO_TIMEOUT = 600       # 代理请求超时（秒）
PIXELLE_CONFIG_PATH = os.getenv("PIXELLE_CONFIG_PATH", str(SERVER_DIR.parent.parent.parent / "Pixelle-Video" / "config.yaml"))

# --- Seedance 2.0 (火山方舟 Ark API) ---
SEEDANCE_API_KEY = os.getenv("SEEDANCE_API_KEY", "")


def _resolve_pixelle_config(db=None):
    """从 DB 读取 Pixelle-Video 配置，fallback 到环境变量/默认值。"""
    url = PIXELLE_VIDEO_URL
    timeout = PIXELLE_VIDEO_TIMEOUT

    if db:
        try:
            from app.db_models import SystemSetting
            import logging
            _log = logging.getLogger(__name__)
            settings = {s.key: s.value for s in db.query(SystemSetting).all()}
            url = settings.get("pixelle_video_url") or url
            try:
                timeout = int(settings.get("pixelle_video_timeout", timeout))
            except (TypeError, ValueError):
                _log.warning("Invalid pixelle timeout in DB, using default")
        except Exception:
            _log.warning("Failed to resolve pixelle config from DB, using defaults", exc_info=True)

    return {"url": url, "timeout": timeout}
```

## app/db_models.py

```python
"""SQLAlchemy ORM models — database persistence layer."""
import uuid
from datetime import datetime, timezone
from app.config import bj_now

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text, Boolean,
    JSON, ForeignKey, UniqueConstraint, Index, Table,
)
from sqlalchemy.orm import DeclarativeBase, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"

    id = Column(String(36), primary_key=True, default=_uuid)
    nickname = Column(String(100), nullable=False)
    douyin_id = Column(String(100), nullable=False, default="")
    group = Column(String(50), nullable=False, default="default")
    status = Column(String(20), nullable=False, default="active")  # active, risk_controlled, banned
    cookie = Column(Text, nullable=True)  # encrypted cookie, nullable for MVP
    daily_limits = Column(JSON, nullable=False, default=lambda: {
        "likes": 50, "comments": 20, "follows": 20, "dms": 10, "replies": 15, "nurture_likes": 200,
    })
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    tasks = relationship("Task", back_populates="account")


class Device(Base):
    __tablename__ = "devices"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    ip = Column(String(50), nullable=True)
    status = Column(String(20), nullable=False, default="offline")  # online, offline, maintenance
    device_secret = Column(String(64), nullable=True, unique=True)  # per-device secret from pairing
    bound_account_id = Column(String(36), ForeignKey("accounts.id"), nullable=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    proxy_config = Column(JSON, nullable=True)  # {"type":"http","host":"...","port":8080,"username":"...","password":"..."}
    os_version = Column(String(50), nullable=True)
    app_version = Column(String(20), nullable=True)
    screen_resolution = Column(String(30), nullable=True)  # e.g. "1080x2400"
    sdk_version = Column(String(20), nullable=True)  # Android SDK version
    total_memory = Column(Integer, nullable=True)  # total RAM in bytes
    manufacturer = Column(String(50), nullable=True)  # e.g. "samsung"
    product = Column(String(50), nullable=True)
    device_model = Column(String(50), nullable=True)  # raw model string
    hardware = Column(String(50), nullable=True)
    display = Column(String(100), nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    tasks = relationship("Task", back_populates="device")


class DevicePairRequest(Base):
    __tablename__ = "device_pair_requests"

    id = Column(String(36), primary_key=True, default=_uuid)
    pairing_token = Column(String(64), nullable=False, unique=True, index=True)
    device_id = Column(String(36), nullable=False)        # device-generated ID
    device_name = Column(String(100), nullable=False)     # device model name
    os_version = Column(String(50), nullable=True)
    app_version = Column(String(20), nullable=True)
    screen_resolution = Column(String(30), nullable=True)
    sdk_version = Column(String(20), nullable=True)
    total_memory = Column(Integer, nullable=True)
    manufacturer = Column(String(50), nullable=True)
    product = Column(String(50), nullable=True)
    device_model = Column(String(50), nullable=True)
    hardware = Column(String(50), nullable=True)
    display = Column(String(100), nullable=True)
    status = Column(String(20), nullable=False, default="pending")  # pending, approved, rejected
    device_secret = Column(String(64), nullable=True)     # generated on approval
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=_uuid)
    type = Column(String(30), nullable=False)  # nurture, search_comment, search_like, search_dm, reply_comment
    account_id = Column(String(36), ForeignKey("accounts.id"), nullable=False)
    device_id = Column(String(36), ForeignKey("devices.id"), nullable=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    params = Column(JSON, nullable=False, default=dict)
    status = Column(String(20), nullable=False, default="pending")  # pending, running, completed, failed, cancelled
    result = Column(JSON, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    scheduled_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    chain_instance_id = Column(String(36), ForeignKey("chain_instances.id"), nullable=True)
    step_order = Column(Integer, nullable=True)

    account = relationship("Account", back_populates="tasks")
    device = relationship("Device", back_populates="tasks")
    chain_instance = relationship("ChainInstance", back_populates="tasks")


class UISelector(Base):
    __tablename__ = "ui_selectors"

    id = Column(String(36), primary_key=True, default=_uuid)
    action_name = Column(String(100), nullable=False, index=True)
    description = Column(String(200), nullable=False, default="")
    platform_version = Column(String(50), nullable=False, default="default")
    resolution_profile = Column(String(50), nullable=False, default="default")
    strategies = Column(JSON, nullable=False)  # list of {type, value, x_percent, y_percent, priority}
    version = Column(Integer, nullable=False, default=1)
    enabled = Column(Boolean, nullable=False, default=True)
    category = Column(String(50), nullable=True, default=None, index=True)
    purpose = Column(String(20), nullable=False, default="locate")  # locate | extract
    strategy_logic = Column(String(10), nullable=False, default="and")  # and | or — inter-strategy logic for page_detect
    extract_field = Column(String(20), nullable=True)  # text | desc | id | className
    clean_mode = Column(String(20), nullable=True)     # raw | regex | ai
    clean_pattern = Column(Text, nullable=True)         # regex pattern
    clean_prompt = Column(Text, nullable=True)          # AI clean prompt
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class DailyStats(Base):
    __tablename__ = "daily_stats"
    __table_args__ = (
        UniqueConstraint("account_id", "date", name="uq_daily_stats_account_date"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    account_id = Column(String(36), ForeignKey("accounts.id"), nullable=False, index=True)
    date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    likes = Column(Integer, nullable=False, default=0)
    nurture_likes = Column(Integer, nullable=False, default=0)
    comments = Column(Integer, nullable=False, default=0)
    follows = Column(Integer, nullable=False, default=0)
    dms = Column(Integer, nullable=False, default=0)
    replies = Column(Integer, nullable=False, default=0)
    collected = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    account = relationship("Account")


class ContentTemplate(Base):
    __tablename__ = "content_templates"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False, default="comment")  # comment, dm, reply
    body = Column(Text, nullable=False)
    variables = Column(JSON, nullable=False, default=list)  # ["keyword", "username", "video_title"]
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class SensitiveWord(Base):
    __tablename__ = "sensitive_words"

    id = Column(String(36), primary_key=True, default=_uuid)
    word = Column(String(100), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())


class AccountGroup(Base):
    __tablename__ = "account_groups"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(500), nullable=True, default="")
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    members = relationship("AccountGroupMember", back_populates="group", cascade="all, delete-orphan")


class AccountGroupMember(Base):
    __tablename__ = "account_group_members"
    __table_args__ = (
        UniqueConstraint("group_id", "account_id", name="uq_group_account"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    group_id = Column(String(36), ForeignKey("account_groups.id", ondelete="CASCADE"), nullable=False)
    account_id = Column(String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    group = relationship("AccountGroup", back_populates="members")
    account = relationship("Account")


class ChainTemplate(Base):
    __tablename__ = "chain_templates"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True, default="")
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    steps = Column(JSON, nullable=False)  # [{step_order, type, label, params}, ...]
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    instances = relationship("ChainInstance", back_populates="template")


class ChainInstance(Base):
    __tablename__ = "chain_instances"

    id = Column(String(36), primary_key=True, default=_uuid)
    template_id = Column(String(36), ForeignKey("chain_templates.id", ondelete="RESTRICT"), nullable=False)
    account_id = Column(String(36), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False)
    device_id = Column(String(36), ForeignKey("devices.id"), nullable=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    current_step = Column(Integer, nullable=False, default=1)
    total_steps = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending, running, completed, failed, cancelled
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    template = relationship("ChainTemplate", back_populates="instances")
    account = relationship("Account")
    device = relationship("Device")
    tasks = relationship("Task", back_populates="chain_instance")


class RepliedComment(Base):
    """已回复的评论去重表 — 基于作者+内容哈希全局去重"""
    __tablename__ = "replied_comments"

    content_hash = Column(String(64), primary_key=True)  # SHA256 of author+text
    author = Column(String(200), nullable=False)
    text = Column(Text, nullable=False)
    replied_by_device = Column(String(36), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False, default="")
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class Channel(Base):
    __tablename__ = "channels"

    id = Column(String(36), primary_key=True, default=_uuid)
    group_id = Column(String(36), ForeignKey("account_groups.id", ondelete="RESTRICT"), nullable=False)
    task_type = Column(String(30), nullable=False)  # search_comment, search_like, search_dm, reply_comment
    status = Column(String(20), nullable=False, default="active")  # active, paused, completed, cancelled
    account_mode = Column(String(20), nullable=False, default="round_robin")  # single_account, round_robin
    account_id = Column(String(36), ForeignKey("accounts.id"), nullable=True)  # single_account mode
    params_template = Column(JSON, nullable=False, default=dict)
    cooldown_seconds = Column(Integer, nullable=False, default=300)
    delay_range = Column(JSON, nullable=False, default=lambda: [3000, 8000])
    max_keywords = Column(Integer, nullable=False, default=500)
    current_account_index = Column(Integer, nullable=False, default=0)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    completed_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    group = relationship("AccountGroup")
    account = relationship("Account")
    items = relationship("ChannelItem", back_populates="channel", cascade="all, delete-orphan")


class ChannelItem(Base):
    __tablename__ = "channel_items"
    __table_args__ = (
        Index("ix_channel_items_channel_status", "channel_id", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    channel_id = Column(String(36), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    keyword = Column(String(200), nullable=False)
    account_id = Column(String(36), ForeignKey("accounts.id"), nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending, assigned, completed, failed, skipped
    assigned_device_id = Column(String(36), ForeignKey("devices.id"), nullable=True)
    assigned_at = Column(DateTime, nullable=True)  # for stale recovery
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=True)
    queue_position = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    completed_at = Column(DateTime, nullable=True)

    channel = relationship("Channel", back_populates="items")
    account = relationship("Account")
    device = relationship("Device")
    task = relationship("Task")


class PromptTemplate(Base):
    """AI 提示词模板 — 按行业可配置，设备端同步后按 template_id 加载"""
    __tablename__ = "prompt_templates"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False, unique=True, index=True)
    industry = Column(String(50), nullable=False, default="health", index=True)
    description = Column(String(200), nullable=False, default="")
    content = Column(JSON, nullable=False)  # 完整提示词结构: { identity, semanticGuide, analysis, ... }
    version = Column(Integer, nullable=False, default=1)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class DMSequence(Base):
    """DM 私信序列模板 — 预设有序多条私信内容，前端全量自定义传入"""
    __tablename__ = "dm_sequences"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    messages = Column(JSON, nullable=False)             # [{order, content, delay_ms}, ...]
    variants = Column(JSON, nullable=True)
    industry = Column(String(50), nullable=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class CollectedComment(Base):
    """采集的评论数据"""
    __tablename__ = "collected_comments"

    id = Column(String(36), primary_key=True, default=_uuid)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=True, index=True)
    device_id = Column(String(36), ForeignKey("devices.id"), nullable=True)
    keyword = Column(String(200), nullable=False)
    nickname = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    time_str = Column(String(50), nullable=True)        # 评论发布时间（原始字符串）
    reply_count = Column(String(20), nullable=True)      # 回复数
    like_count = Column(String(20), nullable=True)       # 点赞数
    dislike_count = Column(String(20), nullable=True)    # 踩数
    location = Column(String(100), nullable=True)        # IP属地
    is_author = Column(Boolean, nullable=False, default=False)
    data_source_type = Column(Integer, nullable=False, default=0)  # 0=普通视频, 1=带货视频
    ai_reply = Column(Text, nullable=True)              # AI 生成的回复内容
    ai_replied_at = Column(DateTime, nullable=True)     # AI 回复时间
    intended_province = Column(String(50), nullable=True)  # 意向省份
    intended_city = Column(String(100), nullable=True)      # 意向城市
    intended_attraction = Column(String(200), nullable=True)  # 意向景点
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())


class CollectedUser(Base):
    """采集的用户数据 — 按 douyin_id 去重"""
    __tablename__ = "collected_users"

    id = Column(String(36), primary_key=True, default=_uuid)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=True, index=True)
    device_id = Column(String(36), ForeignKey("devices.id"), nullable=True)
    nickname = Column(String(100), nullable=False)
    douyin_id = Column(String(100), nullable=False, unique=True, index=True)  # 抖音数字ID，去重键
    keyword = Column(String(200), nullable=True, index=True)  # 采集关键词/行业
    likes_count = Column(String(20), nullable=True)     # 获赞数
    follow_count = Column(String(20), nullable=True)    # 关注数
    fans_count = Column(String(20), nullable=True)      # 粉丝数
    works_count = Column(String(20), nullable=True)     # 作品数
    gender = Column(String(10), nullable=True)          # 性别
    age = Column(String(10), nullable=True)             # 年龄
    ip_location = Column(String(100), nullable=True)    # IP属地
    is_private = Column(String(10), nullable=True)      # 是否私密账号
    data_source_type = Column(Integer, nullable=False, default=0)  # 0=普通视频, 1=带货视频
    avatar_url = Column(Text, nullable=True)             # 头像本地路径
    intended_province = Column(String(50), nullable=True)  # 意向省份
    intended_city = Column(String(100), nullable=True)     # 意向城市
    intended_attraction = Column(String(200), nullable=True)  # 意向景点
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    role = Column(String(20), nullable=False, default="operator")  # admin | operator
    nickname = Column(String(100), nullable=True)
    status = Column(String(20), nullable=False, default="active")  # active | disabled
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class Conversation(Base):
    """AI 发送的私信会话 — 按 (account_id, recipient_douyin_id) 全局去重"""
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("account_id", "recipient_douyin_id", name="uq_conversation_account_recipient"),
        Index("ix_conversations_task_id", "task_id"),
        Index("ix_conversations_account_id", "account_id"),
        Index("ix_conversations_stage", "current_stage"),
        Index("ix_conversations_status", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=True)
    account_id = Column(String(36), ForeignKey("accounts.id"), nullable=False)
    device_id = Column(String(36), ForeignKey("devices.id"), nullable=True)
    keyword = Column(String(200), nullable=True)

    recipient_nickname = Column(String(100), nullable=False)
    recipient_douyin_id = Column(String(100), nullable=False)

    current_stage = Column(String(20), nullable=False, default="qualifying")
    intent = Column(String(30), nullable=True)
    last_dm_content = Column(Text, nullable=True)
    last_dm_at = Column(DateTime, nullable=True)

    claimed_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="active")

    total_dm_count = Column(Integer, nullable=False, default=0)
    reply_received_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    account = relationship("Account")
    device = relationship("Device")
    task = relationship("Task")


class GeneratedVideo(Base):
    """AI 生成的短视频"""
    __tablename__ = "generated_videos"

    id = Column(String(36), primary_key=True, default=_uuid)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=True)
    keyword = Column(String(200), nullable=False)
    title = Column(String(500), nullable=True)
    video_path = Column(String(500), nullable=True)
    duration = Column(Float, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    pixelle_task_id = Column(String(100), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    task = relationship("Task")


# ==== 多模型系列生成系统 ====

class Character(Base):
    __tablename__ = "characters"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    role_type = Column(String(20), nullable=False, default="protagonist")
    gender = Column(String(10), nullable=False, default="male")
    age_range = Column(String(20), nullable=True)
    personality = Column(Text, nullable=True)
    appearance_desc = Column(Text, nullable=True)
    outfit_desc = Column(Text, nullable=True)
    avatar_front_url = Column(Text, nullable=True)
    avatar_side_url = Column(Text, nullable=True)
    avatar_threequarter_url = Column(Text, nullable=True)
    avatar_fullbody_url = Column(Text, nullable=True)
    default_voice_id = Column(String(100), nullable=True)
    meta_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class Scene(Base):
    __tablename__ = "scenes"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    scene_type = Column(String(20), nullable=False, default="indoor")
    location_desc = Column(Text, nullable=True)
    lighting = Column(String(50), nullable=True)
    mood = Column(String(50), nullable=True)
    reference_wideshot_url = Column(Text, nullable=True)
    reference_midshot_url = Column(Text, nullable=True)
    reference_aerial_url = Column(Text, nullable=True)
    meta_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class Series(Base):
    __tablename__ = "series"

    id = Column(String(36), primary_key=True, default=_uuid)
    title = Column(String(200), nullable=False)
    logline = Column(Text, nullable=True)
    genre = Column(String(50), nullable=False, default="drama")
    total_episodes = Column(Integer, nullable=False, default=30)
    target_duration = Column(Integer, nullable=False, default=90)
    mode = Column(String(20), nullable=False, default="step_by_step")
    pilot_first = Column(Boolean, nullable=False, default=True)
    story_bible_json = Column(JSON, nullable=True, default=dict)
    status = Column(String(20), nullable=False, default="draft")
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    episodes = relationship("Episode", back_populates="series")
    characters = relationship("Character", secondary="series_characters", back_populates="series_list")
    scenes = relationship("Scene", secondary="series_scenes", back_populates="series_list")


# M2M: reverse relationships (lazy only, back_populates resolved at mapper configure time)
Character.series_list = relationship("Series", secondary="series_characters", back_populates="characters", lazy="noload")
Scene.series_list = relationship("Series", secondary="series_scenes", back_populates="scenes", lazy="noload")

series_characters = Table("series_characters", Base.metadata,
    Column("series_id", String(36), ForeignKey("series.id"), primary_key=True),
    Column("character_id", String(36), ForeignKey("characters.id"), primary_key=True),
)

series_scenes = Table("series_scenes", Base.metadata,
    Column("series_id", String(36), ForeignKey("series.id"), primary_key=True),
    Column("scene_id", String(36), ForeignKey("scenes.id"), primary_key=True),
)


class Episode(Base):
    __tablename__ = "episodes"

    id = Column(String(36), primary_key=True, default=_uuid)
    series_id = Column(String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    episode_number = Column(Integer, nullable=False)
    title = Column(String(200), nullable=True)
    script_json = Column(JSON, nullable=True, default=dict)
    storyboard_json = Column(JSON, nullable=True, default=dict)
    video_url = Column(Text, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    cost_so_far = Column(Float, nullable=True, default=0.0)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    series = relationship("Series", back_populates="episodes")
    __table_args__ = (
        UniqueConstraint("series_id", "episode_number"),
        Index("idx_episodes_series_id", "series_id"),
    )


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(String(36), primary_key=True, default=_uuid)
    series_id = Column(String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True)
    mode = Column(String(20), nullable=False, default="step_by_step")
    model_ids = Column(JSON, nullable=True, default=dict)
    layers_json = Column(JSON, nullable=True, default=dict)
    current_layer = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="pending")
    error_log = Column(Text, nullable=True)
    actual_cost_so_far = Column(Float, nullable=True, default=0.0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    __table_args__ = (Index("idx_pipeline_runs_series_id", "series_id"),)


class AuditReport(Base):
    __tablename__ = "audit_reports"

    id = Column(String(36), primary_key=True, default=_uuid)
    target_type = Column(String(20), nullable=False)
    target_id = Column(String(36), nullable=False)
    image_url = Column(Text, nullable=False)
    auditor_model = Column(String(50), nullable=False)
    score = Column(Float, nullable=False, default=0.0)
    pass_fail = Column(Boolean, nullable=False, default=False)
    issues_json = Column(JSON, nullable=True, default=list)
    raw_response = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())


class ReferenceData(Base):
    """系统字典 — 管理所有下拉选项 (系列类型/角色类型/场景属性/模型配置)."""
    __tablename__ = "reference_data"

    id = Column(String(36), primary_key=True, default=_uuid)
    category = Column(String(50), nullable=False, index=True)
    value = Column(String(100), nullable=False)
    label = Column(String(100), nullable=False)
    description = Column(String(200), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    __table_args__ = (UniqueConstraint("category", "value"),)


class ReferenceCategory(Base):
    """字典分类 — category 不再硬编码，可通过前端 CRUD 管理."""
    __tablename__ = "reference_categories"

    id = Column(String(36), primary_key=True, default=_uuid)
    key = Column(String(50), nullable=False, unique=True, index=True)
    label = Column(String(100), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())


class AIModel(Base):
    """AI model config — independent management of API connection parameters per model type."""
    __tablename__ = "ai_models"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    model_type = Column(String(20), nullable=False, index=True)
    provider = Column(String(30), nullable=False)
    base_url = Column(String(300), nullable=True)
    api_key = Column(String(500), nullable=True)   # encrypted
    api_secret = Column(String(500), nullable=True) # encrypted
    model_name = Column(String(100), nullable=True)
    config_json = Column(JSON, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    __table_args__ = (UniqueConstraint("model_type", "provider", "model_name",
                                        name="uq_ai_models_type_provider_name"),)
```

## app/models.py

```python
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, model_validator
import uuid


class TaskType(str, Enum):
    NURTURE = "nurture"
    SEARCH_COMMENT = "search_comment"
    SEARCH_LIKE = "search_like"
    SEARCH_DM = "search_dm"
    REPLY_COMMENT = "reply_comment"
    COLLECT = "collect"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: TaskType
    account_id: str
    device_id: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    created_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[dict[str, Any]] = None
    retry_count: int = 0
    chain_instance_id: Optional[str] = None
    step_order: Optional[int] = None


class AccountConfig(BaseModel):
    id: str
    nickname: str
    douyin_id: str
    status: str = "active"
    daily_limits: dict[str, int] = Field(default_factory=lambda: {
        "likes": 50,
        "comments": 20,
        "follows": 20,
        "dms": 10,
        "replies": 15,
    })


class SelectorStrategy(BaseModel):
    type: str  # text, id, desc, className, package, coordinate, image
    value: Optional[str] = None
    x_percent: Optional[float] = None
    y_percent: Optional[float] = None
    priority: int
    # image 类型专用字段
    template: Optional[str] = None  # 模板图片文件名
    threshold: Optional[float] = None  # 匹配阈值


class SelectorConfig(BaseModel):
    action_name: str
    platform_version: str = "default"
    strategies: list[SelectorStrategy]
    version: int = 1
    purpose: str = "locate"  # locate | extract | page_detect


class TaskCreateRequest(BaseModel):
    type: TaskType
    account_id: str
    device_id: Optional[str] = None
    params: dict[str, Any] = Field(default_factory=dict)
    scheduled_at: Optional[datetime] = None


class BatchTaskCreateRequest(BaseModel):
    type: TaskType
    account_ids: Optional[list[str]] = None
    group_ids: Optional[list[str]] = None
    device_id: Optional[str] = None
    params: dict[str, Any] = Field(default_factory=dict)
    scheduled_at: Optional[datetime] = None

    @model_validator(mode="after")
    def check_at_least_one(self):
        if not self.account_ids and not self.group_ids:
            raise ValueError("account_ids 和 group_ids 至少提供一个")
        return self


# --- 任务参数校验模型 ---

class ActionWeight(BaseModel):
    type: str = Field(..., pattern="^(browse_feed|like|comment|follow)$")
    weight: int = Field(..., ge=0, le=100)


class NurtureParams(BaseModel):
    duration: int = Field(default=30, ge=1, le=120, description="养号时长(分钟)")
    actions: list[ActionWeight] = Field(default_factory=lambda: [
        ActionWeight(type="browse_feed", weight=70),
        ActionWeight(type="like", weight=20),
        ActionWeight(type="follow", weight=10),
    ])


class SearchCommentParams(BaseModel):
    keyword: str = Field("", min_length=0, max_length=200, description="搜索关键词（分享链接模式时可为空）")
    keywords: Optional[list[str]] = Field(None, description="批量关键词（通道模式）")
    share_links: Optional[list[str]] = Field(None, description="分享链接列表，每个链接对应一个视频")
    content: Optional[str] = Field(None, max_length=200, description="评论内容")
    content_template_id: Optional[str] = Field(None, description="内容模板ID")
    prompt_template_id: Optional[str] = Field(None, description="提示词模板ID")
    count: int = Field(default=5, ge=-1, description="每视频处理数量, -1=全量")
    video_count: int = Field(default=5, ge=-1, description="处理视频数, -1=全量")
    sort_by: Optional[str] = Field(None, pattern="^(latest|most_liked)$")
    max_age_days: int = Field(default=30, ge=-1, description="评论最大天数, -1=不限")


class SearchLikeParams(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=50, description="搜索关键词")
    keywords: Optional[list[str]] = Field(None, description="批量关键词（通道模式）")
    prompt_template_id: Optional[str] = Field(None, description="提示词模板ID")
    count: int = Field(default=5, ge=1, le=30, description="点赞数量")
    sort_by: Optional[str] = Field(None, pattern="^(latest|most_liked)$")


class SearchDMParams(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=50, description="搜索关键词")
    keywords: Optional[list[str]] = Field(None, description="批量关键词（通道模式）")
    content: Optional[str] = Field(None, max_length=500, description="私信内容")
    content_template_id: Optional[str] = Field(None, description="内容模板ID")
    dm_sequence_id: Optional[str] = Field(None, description="DM序列模板ID")
    prompt_template_id: Optional[str] = Field(None, description="提示词模板ID")
    count: int = Field(default=5, ge=1, le=50, description="私信数量")
    sort_by: Optional[str] = Field(None, pattern="^(latest|most_liked)$")


class ReplyCommentParams(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=50, description="搜索关键词")
    keywords: Optional[list[str]] = Field(None, description="批量关键词（通道模式）")
    content: Optional[str] = Field(None, max_length=500, description="私信内容")
    content_template_id: Optional[str] = Field(None, description="内容模板ID")
    dm_sequence_id: Optional[str] = Field(None, description="DM序列模板ID")
    prompt_template_id: Optional[str] = Field(None, description="提示词模板ID")
    count: int = Field(default=5, ge=-1, description="每个视频处理评论数, -1=全量")
    video_count: int = Field(default=3, ge=-1, description="处理视频数, -1=全量")
    sort_by: Optional[str] = Field(None, pattern="^(latest|most_liked)$")
    max_age_days: int = Field(default=5, ge=-1, description="评论最大天数, -1=不限")
    max_follows: int = Field(default=20, ge=1, le=50, description="每日关注上限")
    max_dms: int = Field(default=10, ge=1, le=30, description="每日私信上限")


def _validate_nurture_params(params: dict) -> dict:
    """Accept both legacy (duration only) and V2 (sub_tasks) formats."""
    if "sub_tasks" in params:
        validated = NurtureParamsV2(**params)
        return validated.model_dump(exclude_none=True)
    else:
        validated = NurtureParams(**params)
        return validated.model_dump(exclude_none=True)


# 任务类型 -> 参数模型映射
TASK_PARAMS_VALIDATORS = {
    "nurture": _validate_nurture_params,
    "search_comment": SearchCommentParams,
    "search_like": SearchLikeParams,
    "search_dm": SearchDMParams,
    "reply_comment": ReplyCommentParams,
    "collect": SearchCommentParams,  # collect 复用和 search_comment 相同的参数
}


class TaskProgressReport(BaseModel):
    task_id: str
    step: str = ""          # 当前步骤描述，如 "处理视频 2/3"
    detail: str = ""        # 详情，如 "已回复 5/15 条评论"
    progress: float = 0.0   # 0.0-1.0 进度


class TaskResultReport(BaseModel):
    task_id: str
    status: TaskStatus
    result: Optional[dict[str, Any]] = None
    ui_snapshot: Optional[dict[str, Any]] = None


class PollResponse(BaseModel):
    task: Optional[Task] = None
    selectors_version: int = 1
    prompt_templates_version: int = 1
    proxy: Optional[dict[str, Any]] = None
    cancelled_task_id: Optional[str] = None
    anti_detect_config: Optional[dict[str, Any]] = None
    anti_detect_config_version: int = 1
    ai_config: Optional[dict[str, Any]] = None
    device_config: Optional[dict[str, Any]] = None
    dm_sequences: Optional[list[dict[str, Any]]] = None
    server_date: Optional[str] = None


class DeviceRegisterRequest(BaseModel):
    device_id: str
    name: str
    os_version: str = ""
    app_version: str = ""
    screen_resolution: str = ""
    sdk_version: str = ""
    total_memory: Optional[int] = None
    manufacturer: str = ""
    product: str = ""
    device_model: str = ""
    hardware: str = ""
    display: str = ""


class DeviceRegisterResponse(BaseModel):
    device_id: str
    name: str
    status: str
    config: dict[str, Any]


class RiskReport(BaseModel):
    account_id: str
    risk_type: str  # captcha, rate_limit, account_risk, security_check
    detail: dict[str, Any] = Field(default_factory=dict)
    device_id: str = ""
    timestamp: str = ""


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    expires_in: int  # seconds
    role: str = "admin"
    user_id: str = ""


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)
    role: Optional[str] = "operator"
    nickname: Optional[str] = None


class AdminUser(BaseModel):
    username: str


class ContentTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    category: str = Field(default="comment", pattern="^(comment|dm|reply)$")
    body: str = Field(..., min_length=1)
    variables: list[str] = Field(default_factory=list)


class ContentTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = Field(None, pattern="^(comment|dm|reply)$")
    body: Optional[str] = Field(None, min_length=1)
    variables: Optional[list[str]] = None
    is_active: Optional[bool] = None


class ContentTemplateResponse(BaseModel):
    id: str
    name: str
    category: str
    body: str
    variables: list[str]
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SensitiveWordCreate(BaseModel):
    word: str = Field(..., min_length=1, max_length=100)


class SensitiveWordResponse(BaseModel):
    id: str
    word: str
    created_at: Optional[datetime] = None


class GenerateRequest(BaseModel):
    template_id: str
    context: dict[str, Any] = Field(default_factory=dict)  # {"keyword": "...", "username": "...", "video_title": "..."}


class GenerateResponse(BaseModel):
    content: str
    template_id: str


class DeviceGenerateRequest(BaseModel):
    template_id: str
    context: dict[str, str] = Field(default_factory=dict)


class DeviceGenerateResponse(BaseModel):
    content: str
    template_id: str


class DeviceAIProxyRequest(BaseModel):
    prompt: str
    max_tokens: int = 4096
    temperature: float = 0.7


class DeviceAIProxyResponse(BaseModel):
    content: str


class PairRequestCreate(BaseModel):
    device_id: str
    device_name: str
    os_version: str = ""
    app_version: str = ""
    screen_resolution: str = ""
    sdk_version: str = ""
    total_memory: Optional[int] = None
    manufacturer: str = ""
    product: str = ""
    device_model: str = ""
    hardware: str = ""
    display: str = ""


class PairRequestResponse(BaseModel):
    pairing_token: str
    status: str = "pending"


class PairStatusResponse(BaseModel):
    status: str  # pending, approved, rejected
    pairing_token: Optional[str] = None  # only for pending (from pair-request)
    secret: Optional[str] = None
    config: Optional[dict[str, Any]] = None


# --- 账号分组 ---

class AccountGroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)


class AccountGroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class AccountGroupResponse(BaseModel):
    id: str
    name: str
    description: str
    member_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AccountGroupMemberRequest(BaseModel):
    account_ids: list[str] = Field(..., min_length=1)


# --- 任务链 ---

class ChainStep(BaseModel):
    step_order: int = Field(..., ge=1)
    type: TaskType
    label: str = Field(default="", max_length=100)
    params: dict[str, Any] = Field(default_factory=dict)


class ChainTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    steps: list[ChainStep] = Field(..., min_length=1)


class ChainTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    steps: Optional[list[ChainStep]] = None


class ChainTemplateResponse(BaseModel):
    id: str
    name: str
    description: str
    steps: list[dict[str, Any]]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ChainInstanceCreateRequest(BaseModel):
    template_id: str
    account_ids: Optional[list[str]] = None
    group_ids: Optional[list[str]] = None
    device_id: Optional[str] = None

    @model_validator(mode="after")
    def check_at_least_one(self):
        if not self.account_ids and not self.group_ids:
            raise ValueError("account_ids 和 group_ids 至少提供一个")
        return self


class ChainInstanceResponse(BaseModel):
    id: str
    template_id: str
    template_name: str = ""
    account_id: str
    account_nickname: str = ""
    device_id: str = ""
    current_step: int
    total_steps: int
    status: str
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# --- 养号 V2 ---

class NurtureSubTask(BaseModel):
    type: str = Field(..., pattern="^(browse|watch|like|comment|follow)$")
    count: int = Field(default=1, ge=1, le=100)
    content_template_id: Optional[str] = None


class NurtureParamsV2(BaseModel):
    sub_tasks: list[NurtureSubTask] = Field(..., min_length=1)
    completion_mode: str = Field(default="all", pattern="^(all|any)$")
    duration: int = Field(default=60, ge=1, le=240, description="最大时长(分钟)")
    keywords: Optional[list[str]] = Field(default=None, description="种子关键词，AI 扩展为关键词矩阵")
    keyword_matrix: Optional[list[str]] = Field(default=None, description="AI 扩展后的关键词矩阵（自动生成）")


# --- 关键词矩阵 ---

class KeywordMatrixRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=50)
    count: int = Field(default=10, ge=1, le=30)


class GenerateRegexRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=5000)


class GenerateCleanPromptRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=5000)


# --- 系统设置 ---

class SettingUpdate(BaseModel):
    settings: dict[str, str]


# --- 通道 (Channel) ---

class ChannelCreate(BaseModel):
    group_id: str
    task_type: TaskType
    account_mode: str = Field(default="round_robin", pattern="^(single_account|round_robin)$")
    account_id: Optional[str] = None
    keywords: list[str] = Field(..., min_length=1, max_length=500)
    params_template: dict[str, Any] = Field(default_factory=dict)
    cooldown_seconds: int = Field(default=300, ge=30, le=3600)
    delay_range: list[int] = Field(default=[3000, 8000])

    @model_validator(mode="after")
    def validate_single_account(self):
        if self.account_mode == "single_account" and not self.account_id:
            raise ValueError("single_account 模式下 account_id 必填")
        if len(self.delay_range) != 2 or self.delay_range[0] >= self.delay_range[1]:
            raise ValueError("delay_range 必须为 [min, max] 且 min < max")
        return self


class ChannelUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(paused|active|cancelled)$")


class ChannelItemUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(skipped|pending)$")


class ChannelAppendItems(BaseModel):
    keywords: list[str] = Field(..., min_length=1, max_length=500)


class ChannelEditRequest(BaseModel):
    """PUT /api/channels/{id} — edit channel metadata (all fields optional)"""
    group_id: Optional[str] = None
    account_mode: Optional[str] = Field(None, pattern="^(single_account|round_robin)$")
    account_id: Optional[str] = None
    params_template: Optional[dict[str, Any]] = None
    cooldown_seconds: Optional[int] = Field(None, ge=30, le=3600)
    sync_to_items: bool = False


class ChannelItemEditRequest(BaseModel):
    """PUT /api/channel-items/{item_id} — edit a single pending/assigned item"""
    account_id: Optional[str] = None
    assigned_device_id: Optional[str] = None
    keyword: Optional[str] = Field(None, min_length=1, max_length=200)


class BatchEditRequest(BaseModel):
    """PUT /api/channel-items/batch — batch edit pending/assigned items"""
    item_ids: list[str] = Field(..., min_length=1, max_length=500)
    account_id: Optional[str] = None
    assigned_device_id: Optional[str] = None


class ChannelItemResponse(BaseModel):
    id: str
    keyword: str
    account_id: str
    account_nickname: str = ""
    status: str
    assigned_device_id: str = ""
    device_name: str = ""
    task_id: str = ""
    queue_position: int
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ChannelResponse(BaseModel):
    id: str
    group_id: str
    group_name: str = ""
    task_type: str
    status: str
    account_mode: str
    account_id: str = ""
    params_template: dict[str, Any] = Field(default_factory=dict)
    cooldown_seconds: int = 300
    delay_range: list[int] = Field(default=[3000, 8000])
    total: int = 0
    pending: int = 0
    assigned: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ChannelDetailResponse(ChannelResponse):
    items: list[ChannelItemResponse] = []

# --- 采集上报 ---

class CollectCommentData(BaseModel):
    nickname: str
    content: str
    time_str: str = ""
    reply_count: str = ""
    like_count: str = ""
    dislike_count: str = ""
    location: str = ""
    is_author: bool = False
    ai_reply: str | None = None
    intended_province: str | None = None
    intended_city: str | None = None
    intended_attraction: str | None = None


class CollectUserData(BaseModel):
    nickname: str
    douyin_id: str = ""
    likes_count: str = ""
    follow_count: str = ""
    fans_count: str = ""
    works_count: str = ""
    gender: str = ""
    age: str = ""
    ip_location: str = ""
    is_private: str = ""


class CollectReportRequest(BaseModel):
    task_id: str
    keyword: str
    comment: CollectCommentData
    user: CollectUserData | None = None
    data_source_type: int = 0  # 0=普通视频, 1=带货视频


class StatsIncrementRequest(BaseModel):
    """设备端增量统计上报——每个子操作完成后调用，保证中途崩溃不丢数据"""
    account_id: str
    task_type: str                          # search_like / search_comment / reply_comment / follow / search_dm / nurture / collect
    count: int = 1                          # 操作次数（通常 1）


# --- DM / Conversation models ---

class DMClaimRecipientRequest(BaseModel):
    account_id: str
    recipient_douyin_id: str
    recipient_nickname: str


class DMClaimRecipientResponse(BaseModel):
    claimed: bool
    conversation_id: str | None = None


class DMSendReportRequest(BaseModel):
    conversation_id: str
    stage: str = "qualifying"
    intent: str | None = None
    keyword: str | None = None
    content: str


class DMReleaseRecipientRequest(BaseModel):
    conversation_id: str


class DMReleaseRecipientResponse(BaseModel):
    released: bool
```

## app/deps.py

```python
"""Shared FastAPI dependencies — auth, common utilities."""
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Header, Depends
from sqlalchemy.orm import Session

from app.config import DEVICE_SECRET, JWT_SECRET, JWT_EXPIRE_HOURS
from app.database import get_db


def verify_device_secret(
    x_device_secret: Optional[str] = Header(None, alias="X-Device-Secret"),
    db: Session = Depends(get_db),
) -> Optional[str]:
    """FastAPI dependency — verifies X-Device-Secret header. Returns device_id or None.

    Accepts either the global DEVICE_SECRET (master key) or a per-device secret.
    Returns the device_id for per-device secrets, None for master secret.
    """
    if not x_device_secret:
        raise HTTPException(status_code=401, detail="Missing device secret")

    # Master secret — backward compatible, returns None (can access any device)
    if x_device_secret == DEVICE_SECRET:
        return None

    # Per-device secret — returns device_id for ownership verification
    from app.db_models import Device
    device = db.query(Device).filter(Device.device_secret == x_device_secret).first()
    if device:
        return device.id

    raise HTTPException(status_code=401, detail="Invalid device secret")


def create_access_token(user_id: str, username: str, role: str) -> str:
    """Create a JWT access token with user identity and role."""
    payload = {
        "sub": username,
        "user_id": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


# Backward compat wrapper
def create_admin_token(username: str) -> str:
    return create_access_token("", username, "admin")


def verify_admin_token(authorization: Optional[str] = Header(None)) -> tuple:
    """FastAPI dependency — verifies JWT Bearer token. Returns (user_id, role)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    token = authorization[7:]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("user_id", "")
        role = payload.get("role", "admin")
        return (user_id, role)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_role(*roles: str):
    """Factory — returns a dependency that checks the user has one of the given roles."""
    async def checker(user: tuple = Depends(verify_admin_token)):
        _, role = user
        if role not in roles:
            raise HTTPException(status_code=403, detail="权限不足")
        return user
    return checker


def get_current_user_id(user: tuple = Depends(verify_admin_token)) -> str:
    """Extract user_id from token for data scoping."""
    return user[0]


def verify_ws_admin_token(token: str) -> tuple:
    """Verify JWT token from WebSocket query parameter. Returns (user_id, role) or (None, None)."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return (payload.get("user_id", ""), payload.get("role", "admin"))
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return (None, None)
```

## app/main.py

```python
"""FastAPI application entry point."""
import sys
from pathlib import Path

# Allow running as `python app/main.py` from server/ directory
_server_dir = str(Path(__file__).resolve().parent.parent)
if _server_dir not in sys.path:
    sys.path.insert(0, _server_dir)

import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import bj_now
from app.database import get_db, init_db, SessionLocal
from app.seed import seed_all
from app.routers import device, tasks, accounts, devices, auth, selectors, stats, content, account_groups, chains, settings, channels, prompt_templates, data, videos, pixelle, seedance, ai_config, characters, scenes, series, pipeline, audit, director, reference_data, dm_sequences
from app.services.ai_generator import ai_generator


async def _offline_checker():
    """Background task: mark devices offline based on heartbeat staleness only.
    Uses in-memory cache from WS pings + DB from HTTP polls. Flushes
    in-memory heartbeats to DB each cycle so both sources are current.
    """
    from app.db_models import Device
    from app.ws_manager import pair_ws_manager
    from datetime import timedelta

    while True:
        await asyncio.sleep(30)
        db = SessionLocal()
        try:
            now = bj_now()

            # 1. Flush in-memory heartbeats to DB
            mem_heartbeats = pair_ws_manager.drain_heartbeats()
            if mem_heartbeats:
                try:
                    for device_id, seen_at in mem_heartbeats.items():
                        dev = db.query(Device).filter(Device.id == device_id).first()
                        if dev:
                            dev.last_seen_at = seen_at
                            dev.status = "online"
                    db.commit()
                except Exception:
                    # Re-merge on failure so next cycle retries
                    import logging
                    _hb_log = logging.getLogger("app.heartbeat")
                    _hb_log.warning("heartbeat flush failed, re-queuing %d", len(mem_heartbeats), exc_info=True)
                    for device_id, seen_at in mem_heartbeats.items():
                        if device_id not in pair_ws_manager._device_last_seen:
                            pair_ws_manager._device_last_seen[device_id] = seen_at

            # 2. Check liveness: both in-memory (already drained, checked above)
            #    and DB last_seen_at. Stale if >2 min without heartbeat.
            online_devices = db.query(Device).filter(Device.status == "online").all()
            cutoff_dt = now - timedelta(seconds=120)
            stale_ids = [
                d.id for d in online_devices
                if d.last_seen_at is None or d.last_seen_at < cutoff_dt
            ]

            if stale_ids:
                db.query(Device).filter(Device.id.in_(stale_ids)).update(
                    {"status": "offline"}, synchronize_session=False
                )
                db.commit()

                for device_id in stale_ids:
                    await pair_ws_manager.broadcast_to_admins({
                        "event": "device_status_changed",
                        "device_id": device_id,
                        "status": "offline",
                    })

            # 3. Stuck task detection: tasks running >10 min on ONLINE devices → reset
            #    Device is online (heartbeat active) but task thread stuck/dead.
            #    Offline-device tasks are handled by get_pending_task() stale recovery.
            import os
            stuck_minutes = int(os.getenv("TASK_STALE_MINUTES", "10"))
            stuck_cutoff = now - timedelta(seconds=stuck_minutes * 60)
            from app.db_models import Task as DBTask, ChannelItem as DBChannelItem
            online_ids = [d.id for d in online_devices]  # reuse from liveness check above
            stuck_tasks = db.query(DBTask).filter(
                DBTask.status == "running",
                DBTask.started_at.isnot(None),
                DBTask.started_at < stuck_cutoff,
                DBTask.device_id.in_(online_ids),  # only online devices — offline handled by get_pending_task
            ).all()
            if stuck_tasks:
                from app.services.task_service import MAX_RETRIES
                for t in stuck_tasks:
                    t.retry_count += 1
                    if t.retry_count >= MAX_RETRIES:
                        t.status = "failed"
                        t.completed_at = now
                    else:
                        t.status = "pending"
                        t.device_id = None
                        t.started_at = None
                    # Reset linked channel item (any non-terminal status)
                    db.query(DBChannelItem).filter(
                        DBChannelItem.task_id == t.id,
                        DBChannelItem.status.in_(["assigned", "completed", "failed"]),
                    ).update({"status": "pending", "assigned_device_id": None, "assigned_at": None, "task_id": None}, synchronize_session=False)
                db.commit()
        except Exception:
            import logging
            logging.getLogger("app.offline_checker").warning("checker cycle failed", exc_info=True)
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB and seed. Shutdown: stop checker."""
    if get_db not in app.dependency_overrides:
        seed_all()
        # Seed reference data at startup (idempotent)
        db = SessionLocal()
        try:
            from app.routers.reference_data import seed_reference_data
            seed_reference_data(db)
            from app.routers.ai_config import seed_ai_models
            seed_ai_models(db)
        finally:
            db.close()
    task = asyncio.create_task(_offline_checker())
    yield
    task.cancel()
    await ai_generator.aclose()
    from app.services import pixelle_client
    await pixelle_client.close_client()


app = FastAPI(
    title="抖音自动化助手",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception log middleware — catches unhandled 500s with full traceback
from fastapi import Request
from fastapi.responses import JSONResponse
import traceback as _traceback
import logging
_logger = logging.getLogger("app")

@app.middleware("http")
async def _catch_unhandled_errors(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        _logger.error("UNHANDLED 500: %s %s\n%s", request.method, request.url.path, _traceback.format_exc())
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


app.include_router(device.router)
app.include_router(tasks.router)
app.include_router(accounts.router)
app.include_router(devices.router)
app.include_router(auth.router)
app.include_router(selectors.router)
app.include_router(stats.router)
app.include_router(content.router)
app.include_router(account_groups.router)
app.include_router(chains.router)
app.include_router(settings.router)
app.include_router(channels.router)
app.include_router(prompt_templates.router)
app.include_router(data.router)
app.include_router(videos.router)
app.include_router(pixelle.router)
app.include_router(pixelle.proxy_router)
app.include_router(seedance.api_router)
app.include_router(seedance.proxy_router)
app.include_router(ai_config.router)
app.include_router(characters.router)
app.include_router(scenes.router)
app.include_router(series.router)
app.include_router(pipeline.router)
app.include_router(audit.router)
app.include_router(director.router)
app.include_router(reference_data.router)
app.include_router(dm_sequences.router)


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "0.3.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## app/routers/accounts.py

```python
"""Account management CRUD API."""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.db_models import Account
from app.deps import verify_admin_token, require_role
from app.config import bj_now
from app.ws_manager import pair_ws_manager

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


class AccountCreateRequest(BaseModel):
    nickname: str
    douyin_id: str = ""
    group: str = "default"
    status: str = "active"
    daily_limits: Optional[dict[str, int]] = None


class AccountUpdateRequest(BaseModel):
    nickname: Optional[str] = None
    douyin_id: Optional[str] = None
    group: Optional[str] = None
    status: Optional[str] = None
    daily_limits: Optional[dict[str, int]] = None
    cookie: Optional[str] = None


def _account_to_dict(acc: Account) -> dict:
    return {
        "id": acc.id,
        "nickname": acc.nickname,
        "douyin_id": acc.douyin_id,
        "group": acc.group,
        "status": acc.status,
        "daily_limits": acc.daily_limits,
        "created_at": str(acc.created_at) if acc.created_at else None,
        "updated_at": str(acc.updated_at) if acc.updated_at else None,
    }


@router.post("")
async def create_account(
    request: AccountCreateRequest,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    user_id, _ = user
    acc = Account(
        nickname=request.nickname,
        douyin_id=request.douyin_id,
        group=request.group,
        status=request.status,
        daily_limits=request.daily_limits,
        user_id=user_id,
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    await pair_ws_manager.broadcast_to_admins({"event": "accounts_changed"})
    return _account_to_dict(acc)


@router.get("")
def list_accounts(
    skip: int = 0,
    limit: int = 50,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    user_id, role = user
    query = db.query(Account)
    if not include_deleted:
        query = query.filter(Account.status != "deleted")
    if role != "admin":
        query = query.filter(Account.user_id == user_id)
    total = query.count()
    accounts = query.order_by(Account.created_at.desc()).offset(skip).limit(limit).all()
    return {"accounts": [_account_to_dict(a) for a in accounts], "total": total}


@router.get("/{account_id}")
def get_account(
    account_id: str,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    query = db.query(Account).filter(Account.id == account_id)
    if not include_deleted:
        query = query.filter(Account.status != "deleted")
    if role != "admin":
        query = query.filter(Account.user_id == user_id)
    acc = query.first()
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    return _account_to_dict(acc)


@router.put("/{account_id}")
async def update_account(
    account_id: str,
    request: AccountUpdateRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    query = db.query(Account).filter(Account.id == account_id)
    if role != "admin":
        query = query.filter(Account.user_id == user_id)
    acc = query.first()
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")

    if request.nickname is not None:
        acc.nickname = request.nickname
    if request.douyin_id is not None:
        acc.douyin_id = request.douyin_id
    if request.group is not None:
        acc.group = request.group
    if request.status is not None:
        acc.status = request.status
    if request.daily_limits is not None:
        acc.daily_limits = request.daily_limits
    if request.cookie is not None:
        acc.cookie = request.cookie

    db.commit()
    db.refresh(acc)
    await pair_ws_manager.broadcast_to_admins({"event": "accounts_changed"})
    return _account_to_dict(acc)


@router.delete("/{account_id}")
async def delete_account(
    account_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    query = db.query(Account).filter(Account.id == account_id)
    if role != "admin":
        query = query.filter(Account.user_id == user_id)
    acc = query.first()
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")

    from app.db_models import Device, Task as DBTask
    # 1. 解绑关联设备
    db.query(Device).filter(Device.bound_account_id == account_id).update(
        {"bound_account_id": None}, synchronize_session=False
    )
    # 2. 取消该账号的 pending/running 任务（标记为 cancelled 而非 failed）
    db.query(DBTask).filter(
        DBTask.account_id == account_id,
        DBTask.status.in_(["pending", "running"]),
    ).update({"status": "cancelled", "result": {"error": "account deleted"}, "completed_at": bj_now()},
             synchronize_session=False)

    # 3. 软删除 — 保留数据可审计，可恢复
    acc.status = "deleted"

    db.commit()
    await pair_ws_manager.broadcast_to_admins({"event": "accounts_changed"})
    return {"deleted": True, "id": account_id}
```

## app/routers/account_groups.py

```python
"""Account groups CRUD API."""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.db_models import AccountGroup, AccountGroupMember, Account
from app.deps import verify_admin_token, require_role
from app.models import AccountGroupCreate, AccountGroupUpdate, AccountGroupMemberRequest
from app.ws_manager import pair_ws_manager

router = APIRouter(prefix="/api/account-groups", tags=["account-groups"])


def _group_to_dict(group: AccountGroup, member_count: int = 0) -> dict:
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description or "",
        "member_count": member_count,
        "created_at": str(group.created_at) if group.created_at else None,
        "updated_at": str(group.updated_at) if group.updated_at else None,
    }


@router.post("")
async def create_group(
    request: AccountGroupCreate,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    user_id, _ = user
    existing = db.query(AccountGroup).filter(AccountGroup.name == request.name, AccountGroup.user_id == user_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="分组名称已存在")
    group = AccountGroup(name=request.name, description=request.description, user_id=user_id)
    db.add(group)
    db.commit()
    db.refresh(group)
    await pair_ws_manager.broadcast_to_admins({"event": "account_groups_changed"})
    return _group_to_dict(group, 0)


@router.get("")
def list_groups(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    user_id, role = user
    member_counts = (
        db.query(
            AccountGroupMember.group_id,
            func.count(AccountGroupMember.id).label("cnt"),
        )
        .group_by(AccountGroupMember.group_id)
        .subquery()
    )
    base = db.query(AccountGroup)
    if role != "admin":
        base = base.filter(AccountGroup.user_id == user_id)
    query = (
        base.outerjoin(member_counts, AccountGroup.id == member_counts.c.group_id)
        .add_columns(func.coalesce(member_counts.c.cnt, 0).label("member_count"))
        .order_by(AccountGroup.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    results = query.all()
    total = base.count()
    return {
        "groups": [_group_to_dict(g, mc) for g, mc in results],
        "total": total,
    }


@router.get("/{group_id}")
def get_group(
    group_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    query = db.query(AccountGroup).filter(AccountGroup.id == group_id)
    if role != "admin":
        query = query.filter(AccountGroup.user_id == user_id)
    group = query.first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    member_count = db.query(AccountGroupMember).filter(AccountGroupMember.group_id == group_id).count()
    return _group_to_dict(group, member_count)


@router.put("/{group_id}")
async def update_group(
    group_id: str,
    request: AccountGroupUpdate,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    query = db.query(AccountGroup).filter(AccountGroup.id == group_id)
    if role != "admin":
        query = query.filter(AccountGroup.user_id == user_id)
    group = query.first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    if request.name is not None:
        dup = db.query(AccountGroup).filter(AccountGroup.name == request.name, AccountGroup.id != group_id, AccountGroup.user_id == group.user_id).first()
        if dup:
            raise HTTPException(status_code=409, detail="分组名称已存在")
        group.name = request.name
    if request.description is not None:
        group.description = request.description
    db.commit()
    db.refresh(group)
    member_count = db.query(AccountGroupMember).filter(AccountGroupMember.group_id == group_id).count()
    await pair_ws_manager.broadcast_to_admins({"event": "account_groups_changed"})
    return _group_to_dict(group, member_count)


@router.delete("/{group_id}")
async def delete_group(
    group_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    query = db.query(AccountGroup).filter(AccountGroup.id == group_id)
    if role != "admin":
        query = query.filter(AccountGroup.user_id == user_id)
    group = query.first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    db.delete(group)
    db.commit()
    await pair_ws_manager.broadcast_to_admins({"event": "account_groups_changed"})
    return {"deleted": True, "id": group_id}


@router.get("/{group_id}/members")
def list_members(
    group_id: str,
    status: str = Query(None),
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    group_query = db.query(AccountGroup).filter(AccountGroup.id == group_id)
    if role != "admin":
        group_query = group_query.filter(AccountGroup.user_id == user_id)
    group = group_query.first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    query = (
        db.query(Account)
        .join(AccountGroupMember, AccountGroupMember.account_id == Account.id)
        .filter(AccountGroupMember.group_id == group_id)
    )
    if role != "admin":
        query = query.filter(Account.user_id == user_id)
    if status:
        query = query.filter(Account.status == status)
    accounts = query.order_by(Account.created_at.desc()).all()
    return {
        "members": [
            {
                "id": a.id,
                "nickname": a.nickname,
                "douyin_id": a.douyin_id,
                "status": a.status,
            }
            for a in accounts
        ],
        "total": len(accounts),
    }


@router.post("/{group_id}/members")
async def add_members(
    group_id: str,
    request: AccountGroupMemberRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    group_query = db.query(AccountGroup).filter(AccountGroup.id == group_id)
    if role != "admin":
        group_query = group_query.filter(AccountGroup.user_id == user_id)
    group = group_query.first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    # Validate all account_ids exist and belong to the user
    acc_query = db.query(Account.id).filter(Account.id.in_(request.account_ids))
    if role != "admin":
        acc_query = acc_query.filter(Account.user_id == user_id)
    existing_accounts = {a.id for a in acc_query.all()}
    invalid_ids = [aid for aid in request.account_ids if aid not in existing_accounts]
    if invalid_ids:
        raise HTTPException(status_code=400, detail=f"以下账号不存在: {', '.join(invalid_ids)}")
    added = []
    for account_id in request.account_ids:
        exists = db.query(AccountGroupMember).filter(
            AccountGroupMember.group_id == group_id,
            AccountGroupMember.account_id == account_id,
        ).first()
        if not exists:
            db.add(AccountGroupMember(group_id=group_id, account_id=account_id))
            added.append(account_id)
    db.commit()
    await pair_ws_manager.broadcast_to_admins({"event": "account_groups_changed"})
    return {"added": added, "count": len(added)}


@router.delete("/{group_id}/members")
async def remove_members(
    group_id: str,
    request: AccountGroupMemberRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    group_query = db.query(AccountGroup).filter(AccountGroup.id == group_id)
    if role != "admin":
        group_query = group_query.filter(AccountGroup.user_id == user_id)
    group = group_query.first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    count = (
        db.query(AccountGroupMember)
        .filter(
            AccountGroupMember.group_id == group_id,
            AccountGroupMember.account_id.in_(request.account_ids),
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    await pair_ws_manager.broadcast_to_admins({"event": "account_groups_changed"})
    return {"removed": count}
```

## app/routers/ai_config.py

```python
"""AI Model Config Center — CRUD with encrypted api_key storage."""
import logging
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import httpx
from app.database import get_db
from app.deps import verify_admin_token, require_role
from app.db_models import AIModel
from app.services.crypto import encrypt, decrypt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai-models", tags=["ai-models"])


class ModelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    model_type: Literal["llm", "image", "video", "tts", "audit"]
    provider: str = Field(..., min_length=1, max_length=30)
    base_url: str = ""
    api_key: str = ""
    api_secret: str = ""
    model_name: str = Field(default="", max_length=100)
    config_json: dict | None = None


class ModelUpdate(BaseModel):
    name: str | None = None
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    api_secret: str | None = None
    model_name: str | None = None
    config_json: dict | None = None
    enabled: bool | None = None
    sort_order: int | None = None


def _model_dict(m: AIModel, reveal: bool = False) -> dict:
    ak = ""; asc = ""
    if reveal:
        if m.api_key:
            try: ak = decrypt(m.api_key)
            except Exception:
                logger.warning("decrypt api_key failed for model %s", m.id)
        if m.api_secret:
            try: asc = decrypt(m.api_secret)
            except Exception:
                logger.warning("decrypt api_secret failed for model %s", m.id)
    return {
        "id": m.id, "name": m.name, "model_type": m.model_type,
        "provider": m.provider, "base_url": m.base_url or "",
        "api_key": ak or ("****" if m.api_key and reveal else ""),
        "api_secret": asc,
        "model_name": m.model_name or "",
        "config_json": m.config_json or {},
        "enabled": m.enabled, "sort_order": m.sort_order,
        "api_key_configured": bool(m.api_key) if reveal else False,
    }


# ==== CRUD ====

@router.get("")
def list_models(
    model_type: str | None = Query(None),
    enabled: bool | None = Query(None),
    db: Session = Depends(get_db),
    _ = Depends(verify_admin_token),
):
    q = db.query(AIModel)
    if model_type:
        q = q.filter(AIModel.model_type == model_type)
    if enabled is not None:
        q = q.filter(AIModel.enabled == enabled)
    models = q.order_by(AIModel.sort_order, AIModel.created_at).all()
    return {"ok": True, "models": [_model_dict(m) for m in models]}


@router.get("/options")
def get_options(model_type: str | None = Query(None), db: Session = Depends(get_db),
                _ = Depends(verify_admin_token)):
    q = db.query(AIModel).filter(AIModel.enabled == True)
    if model_type:
        q = q.filter(AIModel.model_type == model_type)
    models = q.order_by(AIModel.sort_order, AIModel.created_at).all()
    return {"ok": True, "options": [
        {"id": m.id, "name": m.name, "model_type": m.model_type, "provider": m.provider}
        for m in models
    ]}


@router.get("/{model_id}")
def get_model(model_id: str, db: Session = Depends(get_db),
              _ = Depends(require_role("admin"))):
    m = db.query(AIModel).filter(AIModel.id == model_id).first()
    if not m:
        raise HTTPException(404, "模型不存在")
    return {"ok": True, "model": _model_dict(m, reveal=True)}


@router.post("")
def create_model(body: ModelCreate, db: Session = Depends(get_db),
                 _ = Depends(require_role("admin"))):
    m = AIModel(
        name=body.name, model_type=body.model_type, provider=body.provider,
        base_url=body.base_url or None,
        api_key=encrypt(body.api_key) if body.api_key else None,
        api_secret=encrypt(body.api_secret) if body.api_secret else None,
        model_name=body.model_name or None,
        config_json=body.config_json or {},
    )
    db.add(m)
    try:
        db.commit(); db.refresh(m)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "同类型同 provider 同 model_name 的模型已存在")
    return {"ok": True, "model": _model_dict(m, reveal=True)}


@router.put("/{model_id}")
def update_model(model_id: str, body: ModelUpdate, db: Session = Depends(get_db),
                 _ = Depends(require_role("admin"))):
    m = db.query(AIModel).filter(AIModel.id == model_id).first()
    if not m:
        raise HTTPException(404, "模型不存在")
    updates = body.model_dump(exclude_unset=True)
    if "api_key" in updates:
        updates["api_key"] = encrypt(updates["api_key"]) if updates["api_key"] else None
    if "api_secret" in updates:
        updates["api_secret"] = encrypt(updates["api_secret"]) if updates["api_secret"] else None
    for k, v in updates.items():
        setattr(m, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "同类型同 provider 同 model_name 的模型已存在")
    return {"ok": True, "model": _model_dict(m, reveal=True)}


@router.delete("/{model_id}")
def delete_model(model_id: str, db: Session = Depends(get_db),
                 _ = Depends(require_role("admin"))):
    m = db.query(AIModel).filter(AIModel.id == model_id).first()
    if not m:
        raise HTTPException(404, "模型不存在")
    db.delete(m); db.commit()
    return {"ok": True}


# ==== Test connection ====

@router.post("/{model_id}/test")
def test_connection(model_id: str, db: Session = Depends(get_db),
                     _ = Depends(require_role("admin"))):
    m = db.query(AIModel).filter(AIModel.id == model_id).first()
    if not m:
        raise HTTPException(404, "模型不存在")
    if not m.base_url:
        return {"ok": False, "error": "未配置 Base URL"}
    ak = decrypt(m.api_key) if m.api_key else ""
    if not ak and m.provider not in ("edge-tts", "none", "custom"):
        return {"ok": False, "error": "未配置 API Key"}

    headers = {}
    if m.provider == "anthropic":
        headers["x-api-key"] = ak
        headers["anthropic-version"] = "2023-06-01"
    else:
        headers["Authorization"] = f"Bearer {ak}"

    test_url = m.base_url.rstrip("/") + "/models"
    if m.provider == "anthropic":
        test_url = m.base_url.rstrip("/").rsplit("/v1/messages", 1)[0] + "/v1/models"

    try:
        resp = httpx.get(test_url, headers=headers, timeout=httpx.Timeout(10, connect=5))
        if resp.is_success:
            return {"ok": True, "status_code": resp.status_code}
        return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except httpx.ConnectError:
        return {"ok": False, "error": "连接失败 — 检查 Base URL"}
    except httpx.TimeoutException:
        return {"ok": False, "error": "连接超时"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ==== Seed ====

DEFAULT_MODELS = [
    {"name":"DeepSeek V3","model_type":"llm","provider":"deepseek","base_url":"https://api.deepseek.com/v1","model_name":"deepseek-chat","config_json":{"thinking_enabled":False,"thinking_budget":8192,"max_tokens":4096,"temperature":0.7}},
    {"name":"GPT-4o","model_type":"llm","provider":"openai","base_url":"https://api.openai.com/v1","model_name":"gpt-4o","config_json":{"thinking_enabled":False,"thinking_budget":8192,"max_tokens":4096,"temperature":0.7}},
    {"name":"Qwen Max","model_type":"llm","provider":"openai","base_url":"https://dashscope.aliyuncs.com/compatible-mode/v1","model_name":"qwen-max","config_json":{"thinking_enabled":False,"thinking_budget":8192,"max_tokens":4096,"temperature":0.7}},
    {"name":"Claude Opus","model_type":"llm","provider":"anthropic","base_url":"https://api.anthropic.com/v1/messages","model_name":"claude-opus-4-7","config_json":{"thinking_enabled":True,"thinking_budget":8192,"max_tokens":4096,"temperature":0.7}},
    {"name":"Seedance Image","model_type":"image","provider":"seedance","base_url":"https://ark.cn-beijing.volces.com/api/v3","model_name":"seedance-image","config_json":{"default_size":"1024x1024","default_quality":"hd"}},
    {"name":"DALL-E 3","model_type":"image","provider":"openai","base_url":"https://api.openai.com/v1","model_name":"dall-e-3","config_json":{"default_size":"1024x1024","default_quality":"hd"}},
    {"name":"FLUX","model_type":"image","provider":"comfyui","base_url":"","model_name":"flux","config_json":{"default_size":"1024x1024","default_quality":"hd"}},
    {"name":"Seedance 2.0","model_type":"video","provider":"seedance","base_url":"https://ark.cn-beijing.volces.com/api/v3","model_name":"doubao-seedance-2.0-260128","config_json":{"default_resolution":"720p","default_duration":5,"default_aspect_ratio":"9:16"}},
    {"name":"Kling 3.0","model_type":"video","provider":"kling","base_url":"","model_name":"kling-v1-6","config_json":{"default_resolution":"1080p","default_duration":5,"default_aspect_ratio":"9:16"}},
    {"name":"Wan 2.7","model_type":"video","provider":"wan","base_url":"","model_name":"wan-2.7","config_json":{"default_resolution":"1080p","default_duration":5,"default_aspect_ratio":"9:16"}},
    {"name":"Edge-TTS","model_type":"tts","provider":"edge-tts","base_url":"","model_name":"edge-tts","config_json":{"default_voice":"zh-CN-XiaoxiaoNeural","default_language":"zh-CN","default_speed":1.0}},
    {"name":"Index-TTS","model_type":"tts","provider":"index-tts","base_url":"","model_name":"index-tts","config_json":{"default_voice":"","default_language":"zh-CN","default_speed":1.0}},
    {"name":"Spark-TTS","model_type":"tts","provider":"spark-tts","base_url":"","model_name":"spark-tts","config_json":{"default_voice":"","default_language":"zh-CN","default_speed":1.0}},
    {"name":"GPT-4o Audit","model_type":"audit","provider":"openai","base_url":"https://api.openai.com/v1","model_name":"gpt-4o","config_json":{"audit_mode":"single"}},
    {"name":"Gemini Audit","model_type":"audit","provider":"gemini","base_url":"","model_name":"gemini-2.5-pro","config_json":{"audit_mode":"single"}},
    {"name":"Skip Audit","model_type":"audit","provider":"none","base_url":"","model_name":"","config_json":{"audit_mode":"skip"}},
]

def seed_ai_models(db: Session):
    """Seed default model configs. Idempotent."""
    for entry in DEFAULT_MODELS:
        exists = db.query(AIModel).filter(
            AIModel.model_type == entry["model_type"],
            AIModel.provider == entry["provider"],
            AIModel.model_name == entry["model_name"],
        ).first()
        if not exists:
            db.add(AIModel(**entry))
    db.commit()
```

## app/routers/audit.py

```python
"""AI 审图 API — 使用 AIModel 配置直接调用 GPT-4o/Gemini Vision 进行多模态审计."""
import logging
import json as _json
import re
import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import AuditReport, AIModel
from app.services.crypto import decrypt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/audit", tags=["audit"])


class AuditImageRequest(BaseModel):
    image_url: str
    target_type: str = "frame"
    target_id: str = ""
    audit_model_id: str | None = None
    audit_criteria: list[str] | None = None


def _get_audit_model(db: Session, model_id: str | None) -> dict:
    if model_id:
        m = db.query(AIModel).filter(AIModel.id == model_id).first()
    else:
        m = db.query(AIModel).filter(
            AIModel.model_type == "audit", AIModel.enabled == True
        ).order_by(AIModel.sort_order).first()
    if not m:
        return {}
    ak = ""
    if m.api_key:
        try: ak = decrypt(m.api_key)
        except Exception: logger.warning("decrypt api_key failed for audit model %s", m.id)
    return {
        "id": m.id, "name": m.name, "provider": m.provider,
        "base_url": m.base_url or "", "api_key": ak,
        "model_name": m.model_name or "",
        "config_json": m.config_json or {},
    }


def _do_audit(model: dict, image_url: str, criteria: list[str] | None) -> dict:
    provider = model.get("provider", "")
    if provider == "none":
        return {"score": 1.0, "pass_fail": True, "issues": [], "raw": "skipped"}
    if not model.get("api_key"):
        return {"score": 1.0, "pass_fail": True, "issues": ["审计模型未配置 API Key"], "raw": ""}

    criteria_text = "\n".join(f"- {c}" for c in (criteria or [
        "画面质量：无模糊、无噪点、分辨率达标",
        "构图合理性：主体清晰、画面平衡",
        "内容安全：无不适宜内容、无违规元素",
        "色彩和谐：无过度曝光、无色彩失真",
    ]))

    system_prompt = (
        "你是专业的视频画面质量审计专家。根据审计标准评分。"
        "返回 JSON：{\"score\": 0.0-1.0, \"pass\": true/false, \"issues\": [\"问题\"]}。只返回 JSON。"
    )

    if provider == "gemini":
        return _audit_gemini(model, image_url, criteria_text, system_prompt)
    return _audit_openai_compatible(model, image_url, criteria_text, system_prompt)


def _audit_openai_compatible(model: dict, image_url: str, criteria_text: str, system_prompt: str) -> dict:
    base = model.get("base_url", "https://api.openai.com/v1")
    resp = httpx.post(
        f"{base.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {model['api_key']}"},
        json={
            "model": model.get("model_name", "gpt-4o"),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": f"审计标准：\n{criteria_text}\n\n请审计这张图片。"},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ]},
            ],
            "max_tokens": 500, "temperature": 0.1,
        },
        timeout=httpx.Timeout(60, connect=10),
    )
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"]
    return _parse_audit_json(raw)


def _audit_gemini(model: dict, image_url: str, criteria_text: str, system_prompt: str) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model['model_name']}:generateContent?key={model['api_key']}"
    resp = httpx.post(
        url,
        json={
            "contents": [{"parts": [
                {"text": f"{system_prompt}\n\n审计标准：\n{criteria_text}"},
                {"inline_data": {"mime_type": "image/jpeg", "data": image_url}},
            ]}],
            "generationConfig": {"maxOutputTokens": 500, "temperature": 0.1},
        },
        timeout=httpx.Timeout(60, connect=10),
    )
    resp.raise_for_status()
    data = resp.json()
    raw = data["candidates"][0]["content"]["parts"][0]["text"]
    return _parse_audit_json(raw)


def _parse_audit_json(raw: str) -> dict:
    m = re.search(r'\{[\s\S]*\}', raw)
    if m:
        try:
            p = _json.loads(m.group(0))
            return {
                "score": float(p.get("score", 0.5)),
                "pass_fail": bool(p.get("pass", True)),
                "issues": p.get("issues", []),
                "raw": raw[:200],
            }
        except Exception:
            pass
    return {"score": 0.5, "pass_fail": True, "issues": [], "raw": raw[:200]}


@router.post("/image")
def audit_image(
    body: AuditImageRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    model_config = _get_audit_model(db, body.audit_model_id)
    try:
        result = _do_audit(model_config, body.image_url, body.audit_criteria)
    except Exception as e:
        logger.exception("Audit API call failed")
        result = {"score": 0.0, "pass_fail": False, "issues": [str(e)], "raw": ""}

    report = AuditReport(
        target_type=body.target_type,
        target_id=body.target_id,
        image_url=body.image_url,
        auditor_model=f"{model_config.get('provider', 'unknown')}:{model_config.get('model_name', 'unknown')}",
        score=result["score"],
        pass_fail=result["pass_fail"],
        issues_json=result.get("issues", []),
        raw_response=result.get("raw", ""),
    )
    db.add(report); db.commit(); db.refresh(report)
    return {"ok": True, "report": {
        "id": report.id, "score": report.score, "pass_fail": report.pass_fail,
        "issues": report.issues_json, "auditor_model": report.auditor_model,
    }}


@router.get("/reports/{target_type}/{target_id}")
def list_reports(target_type: str, target_id: str,
                 db: Session = Depends(get_db)):
    reports = db.query(AuditReport).filter(
        AuditReport.target_type == target_type,
        AuditReport.target_id == target_id,
    ).order_by(AuditReport.created_at.desc()).all()
    return {"ok": True, "reports": [
        {col.name: getattr(r, col.name) for col in AuditReport.__table__.columns}
        for r in reports
    ]}
```

## app/routers/auth.py

```python
"""Authentication — login, device-login, user registration with brute-force protection."""
import time
from collections import defaultdict
from threading import Lock

from fastapi import APIRouter, HTTPException, Request, Depends
from sqlalchemy.orm import Session

from app.models import LoginRequest, RegisterRequest
from app.config import JWT_EXPIRE_HOURS
from app.deps import create_access_token, require_role
from app.database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Rate limiting: max 5 failed attempts per IP within 5 minutes
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW_SECONDS = 300
_failed_attempts: dict[str, list[float]] = defaultdict(list)
_rate_limit_lock = Lock()
_MAX_TRACKED_IPS = 10000


def _get_client_ip(http_request: Request) -> str:
    """获取真实客户端 IP。
    当直连 IP 为本地/私有地址时，说明前面有反向代理，信任 X-Forwarded-For 最左端 IP。
    否则使用 request.client.host（TCP 层真实 IP）。
    """
    import os
    host = http_request.client.host if http_request.client else ""
    is_local = host in ("127.0.0.1", "::1", "localhost") or host.startswith(("10.", "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.", "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.", "192.168."))

    if is_local:
        forwarded = http_request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

    # If behind a configured trusted proxy, use the rightmost untrusted IP
    trusted_proxy = os.getenv("TRUSTED_PROXY_COUNT", "0")
    try:
        proxy_count = int(trusted_proxy)
    except ValueError:
        proxy_count = 0

    if proxy_count > 0:
        forwarded = http_request.headers.get("x-forwarded-for")
        if forwarded:
            ips = [ip.strip() for ip in forwarded.split(",")]
            if len(ips) >= proxy_count + 1:
                return ips[-(proxy_count + 1)]
            return ips[0]

    return host or "unknown"


def _check_rate_limit(client_ip: str) -> None:
    """Raise 429 if too many failed attempts from this IP."""
    now = time.monotonic()
    with _rate_limit_lock:
        # 防止内存无限增长
        if len(_failed_attempts) > _MAX_TRACKED_IPS:
            _failed_attempts.clear()
        attempts = _failed_attempts[client_ip]
        _failed_attempts[client_ip] = [
            t for t in attempts if now - t < _LOGIN_WINDOW_SECONDS
        ]
        if len(_failed_attempts[client_ip]) >= _LOGIN_MAX_ATTEMPTS:
            raise HTTPException(
                status_code=429,
                detail="Too many failed login attempts. Try again later.",
            )


def _record_failure(client_ip: str) -> None:
    """Record a failed login attempt."""
    with _rate_limit_lock:
        _failed_attempts[client_ip].append(time.monotonic())


def _clear_failures(client_ip: str) -> None:
    """Clear failed attempts after successful login."""
    with _rate_limit_lock:
        _failed_attempts.pop(client_ip, None)


@router.post("/login")
def login(request: LoginRequest, http_request: Request, db: Session = Depends(get_db)):
    """User login — queries DB, verifies bcrypt hash, returns JWT with user_id + role."""
    client_ip = _get_client_ip(http_request)
    _check_rate_limit(client_ip)

    from app.db_models import User
    import bcrypt

    user = db.query(User).filter(User.username == request.username, User.status == "active").first()
    if not user:
        _record_failure(client_ip)
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    try:
        pw_ok = bcrypt.checkpw(request.password.encode(), user.password_hash.encode())
    except Exception:
        pw_ok = False
    if not pw_ok:
        _record_failure(client_ip)
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    _clear_failures(client_ip)
    token = create_access_token(user.id, user.username, user.role)
    return {"token": token, "expires_in": JWT_EXPIRE_HOURS * 3600, "role": user.role, "user_id": user.id}


@router.post("/device-login")
def device_login(request: LoginRequest, http_request: Request, db: Session = Depends(get_db)):
    """Device login with account credentials — returns device_secret for binding."""
    client_ip = _get_client_ip(http_request)
    _check_rate_limit(client_ip)

    from app.db_models import User, Device
    import bcrypt, uuid as _uuid

    user = db.query(User).filter(User.username == request.username, User.status == "active").first()
    if not user:
        _record_failure(client_ip)
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    try:
        pw_ok = bcrypt.checkpw(request.password.encode(), user.password_hash.encode())
    except Exception:
        pw_ok = False
    if not pw_ok:
        _record_failure(client_ip)
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    _clear_failures(client_ip)

    device = db.query(Device).filter(Device.name == request.username, Device.user_id == user.id).first()
    if device:
        if not device.device_secret:
            device.device_secret = _uuid.uuid4().hex
    else:
        device = Device(id=str(_uuid.uuid4()), name=request.username, user_id=user.id,
                        device_secret=_uuid.uuid4().hex, status="online")
        db.add(device)
    db.commit()
    return {"device_secret": device.device_secret, "user_id": user.id, "device_id": device.id}


@router.post("/register")
def register_user(request: RegisterRequest, user=Depends(require_role("admin")), db: Session = Depends(get_db)):
    """Create a new user (admin only)."""
    from app.db_models import User
    import bcrypt

    existing = db.query(User).filter(User.username == request.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")
    pw_hash = bcrypt.hashpw(request.password.encode(), bcrypt.gensalt()).decode()
    new_user = User(
        username=request.username,
        password_hash=pw_hash,
        role=request.role or "operator",
        nickname=request.nickname or request.username,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"id": new_user.id, "username": new_user.username, "role": new_user.role}


@router.get("/users")
def list_users(user=Depends(require_role("admin")), db: Session = Depends(get_db)):
    """List all users (admin only)."""
    from app.db_models import User
    users = db.query(User).order_by(User.created_at.desc()).all()
    return {"users": [{"id": u.id, "username": u.username, "nickname": u.nickname,
                       "role": u.role, "status": u.status, "created_at": str(u.created_at)} for u in users]}
```

## app/routers/chains.py

```python
"""Chain templates and instances API."""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.config import bj_now

from app.database import get_db
from app.db_models import ChainTemplate, ChainInstance, Task as DBTask, Account, Device, AccountGroupMember
from app.deps import verify_admin_token, require_role
from app.models import ChainTemplateCreate, ChainTemplateUpdate, ChainInstanceCreateRequest
from app.ws_manager import pair_ws_manager

router = APIRouter(prefix="/api/chains", tags=["chains"])


def _template_to_dict(t: ChainTemplate) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description or "",
        "steps": t.steps or [],
        "created_at": str(t.created_at) if t.created_at else None,
        "updated_at": str(t.updated_at) if t.updated_at else None,
    }


def _instance_to_dict(inst: ChainInstance, template_name: str = "", account_nickname: str = "", device_name: str = "") -> dict:
    return {
        "id": inst.id,
        "template_id": inst.template_id,
        "template_name": template_name,
        "account_id": inst.account_id,
        "account_nickname": account_nickname,
        "device_id": inst.device_id or "",
        "device_name": device_name,
        "current_step": inst.current_step,
        "total_steps": inst.total_steps,
        "status": inst.status,
        "created_at": str(inst.created_at) if inst.created_at else None,
        "started_at": str(inst.started_at) if inst.started_at else None,
        "completed_at": str(inst.completed_at) if inst.completed_at else None,
    }


# --- Chain Template CRUD ---

@router.post("/templates")
async def create_template(
    request: ChainTemplateCreate,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    user_id, _ = user
    orders = sorted(s.step_order for s in request.steps)
    if orders != list(range(1, len(request.steps) + 1)):
        raise HTTPException(status_code=422, detail="步骤序号必须从 1 连续递增")

    steps_data = [s.model_dump() for s in request.steps]
    tpl = ChainTemplate(name=request.name, description=request.description, steps=steps_data, user_id=user_id)
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    await pair_ws_manager.broadcast_to_admins({"event": "chains_changed"})
    return _template_to_dict(tpl)


@router.get("/templates")
def list_templates(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    user_id, role = user
    query = db.query(ChainTemplate)
    if role != "admin":
        query = query.filter(ChainTemplate.user_id == user_id)
    total = query.count()
    templates = query.order_by(ChainTemplate.created_at.desc()).offset(skip).limit(limit).all()
    return {"templates": [_template_to_dict(t) for t in templates], "total": total}


@router.get("/templates/{template_id}")
def get_template(
    template_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    query = db.query(ChainTemplate).filter(ChainTemplate.id == template_id)
    if role != "admin":
        query = query.filter(ChainTemplate.user_id == user_id)
    tpl = query.first()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    return _template_to_dict(tpl)


@router.put("/templates/{template_id}")
async def update_template(
    template_id: str,
    request: ChainTemplateUpdate,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    query = db.query(ChainTemplate).filter(ChainTemplate.id == template_id)
    if role != "admin":
        query = query.filter(ChainTemplate.user_id == user_id)
    tpl = query.first()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    if request.name is not None:
        tpl.name = request.name
    if request.description is not None:
        tpl.description = request.description
    if request.steps is not None:
        # Prevent modifying steps when active instances exist (template hot-update risk)
        active = db.query(ChainInstance).filter(
            ChainInstance.template_id == template_id,
            ChainInstance.status.in_(["pending", "running"]),
        ).count()
        if active > 0:
            raise HTTPException(
                status_code=400,
                detail=f"该模板有 {active} 个活跃实例，无法修改步骤。请等待实例完成或取消后再修改。",
            )
        orders = sorted(s.step_order for s in request.steps)
        if orders != list(range(1, len(request.steps) + 1)):
            raise HTTPException(status_code=422, detail="步骤序号必须从 1 连续递增")
        tpl.steps = [s.model_dump() for s in request.steps]
    db.commit()
    db.refresh(tpl)
    await pair_ws_manager.broadcast_to_admins({"event": "chains_changed"})
    return _template_to_dict(tpl)


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    query = db.query(ChainTemplate).filter(ChainTemplate.id == template_id)
    if role != "admin":
        query = query.filter(ChainTemplate.user_id == user_id)
    tpl = query.first()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    active = db.query(ChainInstance).filter(
        ChainInstance.template_id == template_id,
        ChainInstance.status.in_(["pending", "running"]),
    ).count()
    if active > 0:
        raise HTTPException(status_code=400, detail=f"该模板有 {active} 个活跃实例，无法删除")
    db.delete(tpl)
    db.commit()
    await pair_ws_manager.broadcast_to_admins({"event": "chains_changed"})
    return {"deleted": True, "id": template_id}


# --- Chain Instance Management ---

@router.post("/instances")
async def create_instances(
    request: ChainInstanceCreateRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    from app.services.chain_service import chain_service

    user_id, role = user
    account_ids = list(request.account_ids or [])
    if request.group_ids:
        group_accounts = chain_service.resolve_accounts_from_groups(db, request.group_ids, user_id=None if role == "admin" else user_id)
        account_ids = list(set(account_ids + group_accounts))

    if not account_ids:
        raise HTTPException(status_code=422, detail="未指定任何账号")

    try:
        results = chain_service.create_chain_instances(db, request.template_id, account_ids, device_id=request.device_id, user_id=user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    await pair_ws_manager.broadcast_to_admins({"event": "chains_changed"})
    return {
        "created_count": len(results["created"]),
        "skipped_busy_count": len(results["skipped_busy"]),
        "skipped_error_count": len(results["skipped_error"]),
        "created": results["created"],
        "skipped_busy": results["skipped_busy"],
        "skipped_error": results["skipped_error"],
    }


@router.get("/instances")
def list_instances(
    template_id: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    query = db.query(ChainInstance)
    if template_id:
        query = query.filter(ChainInstance.template_id == template_id)
    if account_id:
        query = query.filter(ChainInstance.account_id == account_id)
    if status:
        query = query.filter(ChainInstance.status == status)
    user_id, role = user
    if role != "admin":
        query = query.filter(ChainInstance.user_id == user_id)
    total = query.count()
    instances = query.order_by(ChainInstance.created_at.desc()).offset(skip).limit(limit).all()

    template_ids = list(set(i.template_id for i in instances))
    account_ids = list(set(i.account_id for i in instances))
    device_ids = list(set(i.device_id for i in instances if i.device_id))
    templates = {t.id: t.name for t in db.query(ChainTemplate).filter(ChainTemplate.id.in_(template_ids)).all()}
    accounts = {a.id: a.nickname for a in db.query(Account).filter(Account.id.in_(account_ids)).all()}
    devices_map = {d.id: d.name for d in db.query(Device).filter(Device.id.in_(device_ids)).all()} if device_ids else {}

    return {
        "instances": [
            _instance_to_dict(i, templates.get(i.template_id, ""), accounts.get(i.account_id, ""), devices_map.get(i.device_id, ""))
            for i in instances
        ],
        "total": total,
    }


@router.get("/instances/{instance_id}")
def get_instance(
    instance_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    query = db.query(ChainInstance).filter(ChainInstance.id == instance_id)
    if role != "admin":
        query = query.filter(ChainInstance.user_id == user_id)
    inst = query.first()
    if not inst:
        raise HTTPException(status_code=404, detail="链实例不存在")
    template = db.query(ChainTemplate).filter(ChainTemplate.id == inst.template_id).first()
    account = db.query(Account).filter(Account.id == inst.account_id).first()
    device = db.query(Device).filter(Device.id == inst.device_id).first() if inst.device_id else None

    tasks = (
        db.query(DBTask)
        .filter(DBTask.chain_instance_id == instance_id)
        .order_by(DBTask.step_order)
        .all()
    )

    result = _instance_to_dict(inst, template.name if template else "", account.nickname if account else "", device.name if device else "")
    result["tasks"] = [
        {
            "id": t.id,
            "step_order": t.step_order,
            "type": t.type,
            "status": t.status,
            "params": t.params,
            "result": t.result,
            "started_at": str(t.started_at) if t.started_at else None,
            "completed_at": str(t.completed_at) if t.completed_at else None,
        }
        for t in tasks
    ]
    return result


@router.post("/instances/{instance_id}/cancel")
async def cancel_instance(
    instance_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    query = db.query(ChainInstance).filter(ChainInstance.id == instance_id)
    if role != "admin":
        query = query.filter(ChainInstance.user_id == user_id)
    inst = query.first()
    if not inst:
        raise HTTPException(status_code=404, detail="链实例不存在")
    if inst.status in ("completed", "cancelled"):
        raise HTTPException(status_code=400, detail=f"链实例已处于 {inst.status} 状态")

    # Cancel ALL pending/running tasks for this chain instance
    active_tasks = (
        db.query(DBTask)
        .filter(
            DBTask.chain_instance_id == instance_id,
            DBTask.status.in_(["pending", "running"]),
        )
        .all()
    )
    for task in active_tasks:
        task.status = "cancelled"
        task.completed_at = bj_now()

        if task.device_id:
            await pair_ws_manager.send_to_device(task.device_id, {
                "event": "cancel_task",
                "task_id": task.id,
            })

    inst.status = "cancelled"
    inst.completed_at = bj_now()
    db.commit()

    await pair_ws_manager.broadcast_to_admins({"event": "chains_changed"})
    return {"status": "cancelled", "id": instance_id}


@router.post("/instances/{instance_id}/retry")
async def retry_instance(
    instance_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    from app.services.chain_service import chain_service

    user_id, role = user
    query = db.query(ChainInstance).filter(ChainInstance.id == instance_id)
    if role != "admin":
        query = query.filter(ChainInstance.user_id == user_id)
    inst = query.first()
    if not inst:
        raise HTTPException(status_code=404, detail="链实例不存在")
    if inst.status != "failed":
        raise HTTPException(status_code=400, detail="只能重试失败的链实例")

    if chain_service.is_account_busy(db, inst.account_id):
        raise HTTPException(status_code=400, detail="该账号当前有其他任务在执行")

    failed_task = (
        db.query(DBTask)
        .filter(DBTask.chain_instance_id == instance_id, DBTask.status == "failed")
        .order_by(DBTask.step_order)
        .first()
    )
    if not failed_task:
        raise HTTPException(status_code=400, detail="未找到失败的步骤")

    failed_task.status = "pending"
    failed_task.device_id = None
    failed_task.started_at = None
    failed_task.completed_at = None
    failed_task.result = None

    inst.status = "running"
    inst.current_step = failed_task.step_order
    inst.completed_at = None
    db.commit()

    chain_service._safe_push_step_task(db, inst)

    await pair_ws_manager.broadcast_to_admins({"event": "chains_changed"})
    return {"status": "retrying", "id": instance_id, "step": failed_task.step_order}
```

## app/routers/channels.py

```python
"""Channel management API -- admin endpoints."""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_admin_token, require_role
from app.models import (
    ChannelCreate, ChannelUpdate, ChannelAppendItems,
    ChannelItemUpdate, ChannelEditRequest, ChannelItemEditRequest, BatchEditRequest,
)
from app.services.channel_service import channel_service
from app.ws_manager import pair_ws_manager
from app.db_models import Account, AccountGroup, ChannelItem, Device

router = APIRouter(prefix="/api/channels", tags=["channels"])


def _channel_to_response(ch, stats: dict, group_name: str = "") -> dict:
    return {
        "id": ch.id,
        "group_id": ch.group_id,
        "group_name": group_name,
        "task_type": ch.task_type,
        "status": ch.status,
        "account_mode": ch.account_mode,
        "account_id": ch.account_id or "",
        "params_template": ch.params_template or {},
        "cooldown_seconds": ch.cooldown_seconds,
        "delay_range": ch.delay_range or [3000, 8000],
        "total": stats["total"],
        "pending": stats["pending"],
        "assigned": stats["assigned"],
        "completed": stats["completed"],
        "failed": stats["failed"],
        "skipped": stats["skipped"],
        "created_at": str(ch.created_at) if ch.created_at else None,
        "completed_at": str(ch.completed_at) if ch.completed_at else None,
    }


def _item_to_response(item, account_nickname: str = "", device_name: str = "") -> dict:
    return {
        "id": item.id,
        "keyword": item.keyword,
        "account_id": item.account_id,
        "account_nickname": account_nickname,
        "status": item.status,
        "assigned_device_id": item.assigned_device_id or "",
        "device_name": device_name,
        "task_id": item.task_id or "",
        "queue_position": item.queue_position,
        "created_at": str(item.created_at) if item.created_at else None,
        "completed_at": str(item.completed_at) if item.completed_at else None,
    }


@router.post("")
async def create_channel(
    request: ChannelCreate,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    try:
        user_id, _ = user
        ch = channel_service.create_channel(
            db,
            group_id=request.group_id,
            task_type=request.task_type.value,
            account_mode=request.account_mode,
            keywords=request.keywords,
            params_template=request.params_template,
            account_id=request.account_id,
            cooldown_seconds=request.cooldown_seconds,
            delay_range=request.delay_range,
            user_id=user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await pair_ws_manager.broadcast_to_admins({"event": "channels_changed"})
    group = db.query(AccountGroup).filter(AccountGroup.id == ch.group_id).first()
    stats = channel_service.get_channel_stats(db, ch.id)
    return _channel_to_response(ch, stats, group.name if group else "")


@router.get("")
def list_channels(
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    channels = channel_service.list_channels(db, user_id=scope_user_id)
    group_ids = list(set(ch.group_id for ch in channels))
    groups = {
        g.id: g.name
        for g in db.query(AccountGroup).filter(AccountGroup.id.in_(group_ids)).all()
    } if group_ids else {}

    channel_ids = [ch.id for ch in channels]
    stats_map = channel_service.get_channels_stats_batch(db, channel_ids)

    result = []
    for ch in channels:
        stats = stats_map.get(ch.id, {"total": 0, "pending": 0, "assigned": 0, "completed": 0, "failed": 0, "skipped": 0})
        result.append(_channel_to_response(ch, stats, groups.get(ch.group_id, "")))
    return {"channels": result, "total": len(result)}


@router.get("/{channel_id}")
def get_channel(
    channel_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    ch = channel_service.get_channel(db, channel_id, user_id=scope_user_id)
    if not ch:
        raise HTTPException(status_code=404, detail="通道不存在")

    group = db.query(AccountGroup).filter(AccountGroup.id == ch.group_id).first()
    stats = channel_service.get_channel_stats(db, ch.id)
    resp = _channel_to_response(ch, stats, group.name if group else "")

    items = db.query(ChannelItem).filter(ChannelItem.channel_id == channel_id).order_by(ChannelItem.queue_position).all()
    account_ids = list(set(i.account_id for i in items))
    device_ids = list(set(i.assigned_device_id for i in items if i.assigned_device_id))
    accounts = {a.id: a.nickname for a in db.query(Account).filter(Account.id.in_(account_ids)).all()} if account_ids else {}
    devices_map = {d.id: d.name for d in db.query(Device).filter(Device.id.in_(device_ids)).all()} if device_ids else {}

    resp["items"] = [
        _item_to_response(i, accounts.get(i.account_id, ""), devices_map.get(i.assigned_device_id, ""))
        for i in items
    ]
    return resp


@router.patch("/{channel_id}")
async def update_channel(
    channel_id: str,
    request: ChannelUpdate,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    if not request.status:
        raise HTTPException(status_code=400, detail="需要提供 status 字段")
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    try:
        channel_service.update_channel_status(db, channel_id, request.status, user_id=scope_user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 通道恢复后广播 new_task_available，让在线设备立即领取
    if request.status == "active":
        await pair_ws_manager.broadcast_to_devices({"event": "new_task_available"})

    await pair_ws_manager.broadcast_to_admins({"event": "channels_changed"})
    return {"status": "updated", "id": channel_id}


@router.delete("/{channel_id}")
async def delete_channel(
    channel_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    try:
        channel_service.soft_delete_channel(db, channel_id, user_id=scope_user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    await pair_ws_manager.broadcast_to_admins({"event": "channels_changed"})
    return {"deleted": True, "id": channel_id}


@router.post("/{channel_id}/items")
async def append_items(
    channel_id: str,
    request: ChannelAppendItems,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    try:
        channel_service.append_items(db, channel_id, request.keywords, user_id=scope_user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await pair_ws_manager.broadcast_to_admins({"event": "channels_changed"})
    return {"appended": len(request.keywords), "channel_id": channel_id}


@router.patch("/{channel_id}/items/{item_id}")
async def update_item(
    channel_id: str,
    item_id: str,
    request: ChannelItemUpdate,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    if not request.status:
        raise HTTPException(status_code=400, detail="需要提供 status 字段")
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    try:
        channel_service.update_item_status(db, item_id, request.status, user_id=scope_user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await pair_ws_manager.broadcast_to_admins({"event": "channels_changed"})
    return {"status": "updated", "item_id": item_id}


# ── Channel edit endpoints ──
# NOTE: /items/* routes must be registered before /{channel_id} to avoid
# "items" being captured as a channel_id parameter.


@router.put("/items/batch")
async def batch_edit_items(
    request: BatchEditRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    result = channel_service.batch_edit_items(
        db,
        request.item_ids,
        account_id=request.account_id,
        assigned_device_id=request.assigned_device_id,
        user_id=scope_user_id,
    )
    await pair_ws_manager.broadcast_to_admins({"event": "channels_changed"})
    return result


@router.put("/items/{item_id}")
async def edit_channel_item(
    item_id: str,
    request: ChannelItemEditRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    try:
        item = channel_service.edit_item(
            db,
            item_id,
            account_id=request.account_id,
            assigned_device_id=request.assigned_device_id,
            keyword=request.keyword,
            user_id=scope_user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await pair_ws_manager.broadcast_to_admins({"event": "channels_changed"})

    account_nickname = ""
    device_name = ""
    if item.account_id:
        acc = db.query(Account).filter(Account.id == item.account_id).first()
        account_nickname = acc.nickname if acc else ""
    if item.assigned_device_id:
        dev = db.query(Device).filter(Device.id == item.assigned_device_id).first()
        device_name = dev.name if dev else ""

    return _item_to_response(item, account_nickname, device_name)


@router.put("/{channel_id}")
async def edit_channel(
    channel_id: str,
    request: ChannelEditRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    try:
        ch = channel_service.edit_channel(
            db,
            channel_id,
            group_id=request.group_id,
            account_mode=request.account_mode,
            account_id=request.account_id,
            params_template=request.params_template,
            cooldown_seconds=request.cooldown_seconds,
            sync_to_items=request.sync_to_items,
            user_id=scope_user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await pair_ws_manager.broadcast_to_admins({"event": "channels_changed"})
    await pair_ws_manager.broadcast_to_devices({"event": "new_task_available"})
    group = db.query(AccountGroup).filter(AccountGroup.id == ch.group_id).first()
    stats = channel_service.get_channel_stats(db, ch.id)
    return _channel_to_response(ch, stats, group.name if group else "")
```

## app/routers/characters.py

```python
"""角色管理 API."""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import Character
from app.services.ai_generator import ai_generator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/characters", tags=["characters"])


class CharacterCreate(BaseModel):
    name: str
    role_type: str = "protagonist"
    gender: str = "male"
    age_range: Optional[str] = None
    personality: Optional[str] = None
    appearance_desc: Optional[str] = None
    outfit_desc: Optional[str] = None
    default_voice_id: Optional[str] = None


class AutoGenerateInput(BaseModel):
    text: str = Field(..., min_length=10, max_length=5000)
    genre: str = "drama"
    count: int = Field(default=4, ge=1, le=10)

CHARACTER_GEN_SYSTEM = """你是一位资深的编剧和角色设计师。根据用户提供的故事概要，生成详细的角色档案。

输出要求：
1. 必须是合法的 JSON，不要包含 markdown 代码块标记
2. 角色数量与用户要求一致
3. 每个角色必须包含所有字段
4. appearance_desc 要足够详细（50-100字），用于 AI 生成角色参考图
5. 角色之间要有区分度（不同性格、不同功能）"""


@router.get("")
def list_characters(db: Session = Depends(get_db),
                    _: str = Depends(verify_admin_token)):
    return {"ok": True, "characters": [_to_dict(c) for c in db.query(Character).all()]}


@router.post("")
def create_character(body: CharacterCreate, db: Session = Depends(get_db),
                     user = Depends(verify_admin_token)):
    c = Character(**body.model_dump())
    db.add(c); db.commit(); db.refresh(c)
    return {"ok": True, "character": _to_dict(c)}


@router.put("/{character_id}")
def update_character(character_id: str, body: dict, db: Session = Depends(get_db),
                     user = Depends(verify_admin_token)):
    c = db.query(Character).filter(Character.id == character_id).first()
    if not c:
        raise HTTPException(404, "Character not found")
    for k, v in body.items():
        if hasattr(c, k):
            setattr(c, k, v)
    db.commit()
    return {"ok": True}


@router.delete("/{character_id}")
def delete_character(character_id: str, db: Session = Depends(get_db),
                     user = Depends(verify_admin_token)):
    db.query(Character).filter(Character.id == character_id).delete()
    db.commit()
    return {"ok": True}


@router.post("/auto-generate")
async def auto_generate_characters(body: AutoGenerateInput, db: Session = Depends(get_db),
                                   user = Depends(verify_admin_token)):
    """AI 根据故事文本自动生成角色档案。返回角色列表（不持久化），前端确认后逐个创建。"""
    user_prompt = f"""故事概要：{body.text}
类型：{body.genre}
需要生成的角色数量：{body.count}

为每个角色生成以下字段的 JSON：
- name: 角色姓名
- role_type: protagonist(主角) / antagonist(反派) / supporting(配角) / cameo(客串)
- gender: male / female
- age_range: 年龄段，如 "25-30"
- personality: 性格描述（2-3句）
- appearance_desc: 详细外貌描述（50-100字，用于 AI 图像生成）
- outfit_desc: 典型着装描述（30-50字，用于 AI 图像生成）

严格输出 JSON 数组，格式：{{"characters": [{{"name":"...","role_type":"...",...}}]}}"""
    try:
        raw = await ai_generator.generate_custom(
            db, CHARACTER_GEN_SYSTEM, user_prompt, max_tokens=4096, temperature=0.8
        )
        parsed = _parse_characters_json(raw)
        return {"ok": True, "characters": parsed["characters"]}
    except Exception as e:
        logger.warning("Character auto-generation failed: %s", e)
        raise HTTPException(500, f"AI 角色生成失败: {e}")


def _parse_characters_json(raw: str) -> dict:
    """Parse LLM JSON output with fallback strategies."""
    # Strategy 1: direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Strategy 2: extract from ```json ... ``` block
    import re
    m = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Strategy 3: find first { ... } with "characters" key
    m = re.search(r'\{[^{}]*"characters"\s*:\s*\[[\s\S]*?\][^{}]*\}', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"无法解析 LLM 返回的角色 JSON: {raw[:300]}")


def _to_dict(c: Character) -> dict:
    return {col.name: getattr(c, col.name) for col in Character.__table__.columns}
```

## app/routers/content.py

```python
"""Content management API — templates, sensitive words, AI generation."""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
from sqlalchemy.orm import Session

from app.models import (
    ContentTemplateCreate, ContentTemplateUpdate, ContentTemplateResponse,
    SensitiveWordCreate, SensitiveWordResponse,
    GenerateRequest, GenerateResponse,
    KeywordMatrixRequest,
    GenerateRegexRequest, GenerateCleanPromptRequest,
)
from app.database import get_db
from app.deps import verify_admin_token
from app.services.content_service import content_service
from app.ws_manager import pair_ws_manager

router = APIRouter(prefix="/api/content", tags=["content"])


# --- Template CRUD ---

@router.post("/templates", response_model=ContentTemplateResponse)
async def create_template(
    request: ContentTemplateCreate,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    result = content_service.create_template(
        db, name=request.name, category=request.category,
        body=request.body, variables=request.variables,
    )
    await pair_ws_manager.broadcast_to_admins({"event": "content_changed"})
    return result


@router.get("/templates")
def list_templates(
    category: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    templates, total = content_service.list_templates(db, category=category, skip=skip, limit=limit)
    return {"templates": templates, "total": total}


@router.get("/templates/{template_id}", response_model=ContentTemplateResponse)
def get_template(
    template_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    tpl = content_service.get_template(db, template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return tpl


@router.put("/templates/{template_id}", response_model=ContentTemplateResponse)
async def update_template(
    template_id: str,
    request: ContentTemplateUpdate,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    updates = request.model_dump(exclude_none=True)
    tpl = content_service.update_template(db, template_id, **updates)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    await pair_ws_manager.broadcast_to_admins({"event": "content_changed"})
    return tpl


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    if not content_service.delete_template(db, template_id):
        raise HTTPException(status_code=404, detail="Template not found")
    await pair_ws_manager.broadcast_to_admins({"event": "content_changed"})
    return {"ok": True}


# --- Sensitive Word CRUD ---

@router.post("/sensitive-words", response_model=SensitiveWordResponse)
async def add_sensitive_word(
    request: SensitiveWordCreate,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    try:
        result = content_service.add_sensitive_word(db, request.word)
        await pair_ws_manager.broadcast_to_admins({"event": "content_changed"})
        return result
    except ValueError:
        raise HTTPException(status_code=409, detail="Word already exists")


@router.get("/sensitive-words")
def list_sensitive_words(
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    words, total = content_service.list_sensitive_words(db, skip=skip, limit=limit)
    return {"words": words, "total": total}


@router.delete("/sensitive-words/{word_id}")
async def delete_sensitive_word(
    word_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    if not content_service.delete_sensitive_word(db, word_id):
        raise HTTPException(status_code=404, detail="Word not found")
    await pair_ws_manager.broadcast_to_admins({"event": "content_changed"})
    return {"ok": True}


# --- AI Generation ---

@router.post("/generate", response_model=GenerateResponse)
async def generate_content(
    request: GenerateRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    try:
        content = await content_service.generate_from_template(
            db, request.template_id, request.context,
        )
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail="Template not found")
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        if "not configured" in str(e):
            raise HTTPException(status_code=503, detail="AI service not configured. Set AI_API_KEY environment variable.")
        raise HTTPException(status_code=502, detail=f"AI service error: {e}")

    return GenerateResponse(content=content, template_id=request.template_id)


@router.post("/generate-keywords")
async def generate_keywords(
    request: KeywordMatrixRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    try:
        keywords = await content_service.generate_keyword_matrix(request.keyword, request.count, db=db)
    except RuntimeError as e:
        if "not configured" in str(e):
            raise HTTPException(status_code=503, detail="AI service not configured.")
        raise HTTPException(status_code=502, detail=f"AI service error: {e}")
    return {"keywords": keywords, "seed": request.keyword}

# --- AI Regex & Clean Prompt Generation ---

@router.post("/generate-regex")
async def generate_regex(
    request: GenerateRegexRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    try:
        regex = await content_service.generate_regex(db, request.description)
    except RuntimeError as e:
        if "not configured" in str(e):
            raise HTTPException(status_code=503, detail="AI service not configured.")
        raise HTTPException(status_code=502, detail=f"AI service error: {e}")
    return {"regex": regex}


@router.post("/generate-clean-prompt")
async def generate_clean_prompt(
    request: GenerateCleanPromptRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    try:
        prompt = await content_service.generate_clean_prompt(db, request.description)
    except RuntimeError as e:
        if "not configured" in str(e):
            raise HTTPException(status_code=503, detail="AI service not configured.")
        raise HTTPException(status_code=502, detail=f"AI service error: {e}")
    return {"prompt": prompt}
```

## app/routers/data.py

```python
"""Data center admin API — collected comments, users, conversations."""
import io
from fastapi import APIRouter, Query, Depends, HTTPException
from fastapi.responses import StreamingResponse
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, cast, Integer, desc, asc, func
from openpyxl import Workbook

from app.database import get_db
from app.deps import verify_admin_token
from app.config import bj_now
from app.db_models import CollectedComment, CollectedUser, Conversation, Device, Task

router = APIRouter(prefix="/api/data", tags=["data"])


def _build_xlsx(headers: list[str], rows: list[list]) -> io.BytesIO:
    wb = Workbook(write_only=True)
    ws = wb.create_sheet()
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _stream_xlsx(filename: str, buf: io.BytesIO) -> StreamingResponse:
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _paginate(query, skip: int, limit: int) -> dict:
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return {"items": items, "total": total}


@router.get("/comments")
def list_comments(
    keyword: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    query = db.query(CollectedComment)
    if keyword:
        query = query.filter(CollectedComment.keyword == keyword)
    if account_id:
        device_ids = db.query(Device.id).filter(Device.bound_account_id == account_id).subquery()
        query = query.filter(CollectedComment.device_id.in_(device_ids))
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(
            CollectedComment.nickname.like(pattern),
            CollectedComment.content.like(pattern),
        ))
    if task_id:
        query = query.filter(CollectedComment.task_id == task_id)
    user_id, role = user
    if role != 'admin':
        query = query.join(Task, CollectedComment.task_id == Task.id).filter(Task.user_id == user_id)
    query = query.order_by(CollectedComment.created_at.desc())
    return _paginate(query, skip, limit)


@router.get("/users")
def list_users(
    keyword: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    is_private: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("desc"),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    query = db.query(CollectedUser)
    if keyword:
        pattern = _build_like(keyword)
        query = query.filter(CollectedUser.keyword.like(pattern))
    if account_id:
        device_ids = db.query(Device.id).filter(Device.bound_account_id == account_id).subquery()
        query = query.filter(CollectedUser.device_id.in_(device_ids))
    if search:
        pattern = _build_like(search)
        query = query.filter(or_(
            CollectedUser.nickname.like(pattern),
            CollectedUser.douyin_id.like(pattern),
            CollectedUser.ip_location.like(pattern),
        ))
    if task_id:
        query = query.filter(CollectedUser.task_id == task_id)
    user_id, role = user
    if role != 'admin':
        query = query.join(Task, CollectedUser.task_id == Task.id).filter(Task.user_id == user_id)
    if is_private == "yes":
        query = query.filter(CollectedUser.is_private == "是")
    elif is_private == "no":
        query = query.filter(or_(
            CollectedUser.is_private.is_(None),
            CollectedUser.is_private == "否",
        ))
    if date_from:
        try:
            d = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(CollectedUser.created_at >= d)
        except ValueError:
            pass
    if date_to:
        try:
            d = datetime.strptime(date_to, "%Y-%m-%d")
            d = d.replace(hour=23, minute=59, second=59)
            query = query.filter(CollectedUser.created_at <= d)
        except ValueError:
            pass

    # Sort: numeric fields cast to Integer, COALESCE NULL→0 for stable ordering
    numeric_sort_fields = {
        "fans_count": func.coalesce(cast(CollectedUser.fans_count, Integer), 0),
        "likes_count": func.coalesce(cast(CollectedUser.likes_count, Integer), 0),
        "follow_count": func.coalesce(cast(CollectedUser.follow_count, Integer), 0),
        "works_count": func.coalesce(cast(CollectedUser.works_count, Integer), 0),
        "created_at": CollectedUser.created_at,
    }
    order_col = numeric_sort_fields.get(sort_by, CollectedUser.created_at)
    order_fn = desc if sort_order == "desc" else asc
    query = query.order_by(order_fn(order_col))

    return _paginate(query, skip, limit)


@router.get("/conversations")
def list_conversations(
    account_id: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    query = db.query(Conversation)
    if account_id:
        query = query.filter(Conversation.account_id == account_id)
    if stage:
        query = query.filter(Conversation.current_stage == stage)
    if status:
        query = query.filter(Conversation.status == status)
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(
            Conversation.recipient_nickname.like(pattern),
            Conversation.last_dm_content.like(pattern),
            Conversation.recipient_douyin_id.like(pattern),
        ))
    if task_id:
        query = query.filter(Conversation.task_id == task_id)
    user_id, role = user
    if role != 'admin':
        query = query.join(Task, Conversation.task_id == Task.id).filter(Task.user_id == user_id)
    query = query.order_by(Conversation.updated_at.desc())
    return _paginate(query, skip, limit)


# === Export endpoints ===

MAX_EXPORT_ROWS = 50000


def _escape_like(value: str) -> str:
    """Escape LIKE wildcards to prevent accidental full-table matches."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _build_like(pattern: str) -> str:
    return f"%{_escape_like(pattern)}%"


@router.get("/export/comments")
def export_comments(
    keyword: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    skip: Optional[int] = Query(None),
    limit: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    query = db.query(CollectedComment)
    if keyword:
        query = query.filter(CollectedComment.keyword == keyword)
    if account_id:
        device_ids = db.query(Device.id).filter(Device.bound_account_id == account_id).subquery()
        query = query.filter(CollectedComment.device_id.in_(device_ids))
    if search:
        pattern = _build_like(search)
        query = query.filter(or_(
            CollectedComment.nickname.like(pattern),
            CollectedComment.content.like(pattern),
        ))
    if task_id:
        query = query.filter(CollectedComment.task_id == task_id)
    if date_from:
        try:
            d = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(CollectedComment.created_at >= d)
        except ValueError:
            pass
    if date_to:
        try:
            d = datetime.strptime(date_to, "%Y-%m-%d")
            d = d.replace(hour=23, minute=59, second=59)
            query = query.filter(CollectedComment.created_at <= d)
        except ValueError:
            pass

    user_id, role = user
    if role != 'admin':
        query = query.join(Task, CollectedComment.task_id == Task.id).filter(Task.user_id == user_id)

    query = query.order_by(CollectedComment.created_at.desc())
    is_paged = limit is not None
    if is_paged:
        if skip: query = query.offset(skip)
        query = query.limit(min(limit, 100))
    else:
        count = query.count()
        if count > MAX_EXPORT_ROWS:
            raise HTTPException(400, f"导出数据量 ({count} 条) 超过上限 ({MAX_EXPORT_ROWS} 条)，请缩小筛选范围")
    rows = query.all()

    headers = ["昵称", "内容", "AI回复", "关键词", "点赞数", "回复数", "IP属地", "意向省份", "意向城市", "意向景点", "是否作者", "评论时间", "采集时间"]
    data = [[
        r.nickname or "", r.content or "", r.ai_reply or "", r.keyword or "",
        r.like_count or "", r.reply_count or "", r.location or "",
        r.intended_province or "", r.intended_city or "", r.intended_attraction or "",
        "是" if r.is_author else "否", r.time_str or "", str(r.created_at or "")
    ] for r in rows]

    buf = _build_xlsx(headers, data)
    return _stream_xlsx(f"comments_{bj_now().strftime('%Y%m%d')}.xlsx", buf)


@router.get("/export/users")
def export_users(
    keyword: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    skip: Optional[int] = Query(None),
    limit: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    query = db.query(CollectedUser)
    if keyword:
        pattern = _build_like(keyword)
        query = query.filter(CollectedUser.keyword.like(pattern))
    if account_id:
        device_ids = db.query(Device.id).filter(Device.bound_account_id == account_id).subquery()
        query = query.filter(CollectedUser.device_id.in_(device_ids))
    if search:
        pattern = _build_like(search)
        query = query.filter(or_(
            CollectedUser.nickname.like(pattern),
            CollectedUser.douyin_id.like(pattern),
        ))
    if task_id:
        query = query.filter(CollectedUser.task_id == task_id)
    if date_from:
        try:
            d = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(CollectedUser.created_at >= d)
        except ValueError:
            pass
    if date_to:
        try:
            d = datetime.strptime(date_to, "%Y-%m-%d")
            d = d.replace(hour=23, minute=59, second=59)
            query = query.filter(CollectedUser.created_at <= d)
        except ValueError:
            pass

    user_id, role = user
    if role != 'admin':
        query = query.join(Task, CollectedUser.task_id == Task.id).filter(Task.user_id == user_id)

    query = query.order_by(CollectedUser.created_at.desc())
    is_paged = limit is not None
    if is_paged:
        if skip: query = query.offset(skip)
        query = query.limit(min(limit, 100))
    else:
        count = query.count()
        if count > MAX_EXPORT_ROWS:
            raise HTTPException(400, f"导出数据量 ({count} 条) 超过上限 ({MAX_EXPORT_ROWS} 条)，请缩小筛选范围")
    rows = query.all()

    headers = ["昵称", "抖音号", "关键词", "意向省份", "意向城市", "意向景点", "获赞", "关注", "粉丝", "作品", "性别", "年龄", "IP属地", "私密账号", "采集时间"]
    data = [[
        r.nickname or "", r.douyin_id or "", r.keyword or "",
        r.intended_province or "", r.intended_city or "", r.intended_attraction or "",
        r.likes_count or "", r.follow_count or "", r.fans_count or "", r.works_count or "",
        r.gender or "", r.age or "", r.ip_location or "", r.is_private or "",
        str(r.created_at or "")
    ] for r in rows]

    buf = _build_xlsx(headers, data)
    return _stream_xlsx(f"users_{bj_now().strftime('%Y%m%d')}.xlsx", buf)


@router.get("/export/conversations")
def export_conversations(
    account_id: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    skip: Optional[int] = Query(None),
    limit: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    query = db.query(Conversation)
    if account_id:
        query = query.filter(Conversation.account_id == account_id)
    if stage:
        query = query.filter(Conversation.current_stage == stage)
    if status:
        query = query.filter(Conversation.status == status)
    if search:
        pattern = _build_like(search)
        query = query.filter(or_(
            Conversation.recipient_nickname.like(pattern),
            Conversation.last_dm_content.like(pattern),
            Conversation.recipient_douyin_id.like(pattern),
        ))
    if task_id:
        query = query.filter(Conversation.task_id == task_id)
    if date_from:
        try:
            d = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(Conversation.created_at >= d)
        except ValueError:
            pass
    if date_to:
        try:
            d = datetime.strptime(date_to, "%Y-%m-%d")
            d = d.replace(hour=23, minute=59, second=59)
            query = query.filter(Conversation.created_at <= d)
        except ValueError:
            pass

    user_id, role = user
    if role != 'admin':
        query = query.join(Task, Conversation.task_id == Task.id).filter(Task.user_id == user_id)

    query = query.order_by(Conversation.last_dm_at.desc().nullslast())
    is_paged = limit is not None
    if is_paged:
        if skip: query = query.offset(skip)
        query = query.limit(min(limit, 100))
    else:
        count = query.count()
        if count > MAX_EXPORT_ROWS:
            raise HTTPException(400, f"导出数据量 ({count} 条) 超过上限 ({MAX_EXPORT_ROWS} 条)，请缩小筛选范围")
    rows = query.all()

    stage_map = {"qualifying": "触达", "nurturing": "培育", "converting": "转化", "follow_up": "跟进"}

    headers = ["对方昵称", "抖音号", "阶段", "最新消息", "消息总数", "最后发送时间"]
    data = [[
        r.recipient_nickname or "", r.recipient_douyin_id or "",
        stage_map.get(r.current_stage, r.current_stage or ""),
        r.last_dm_content or "", str(r.total_dm_count or 0),
        str(r.last_dm_at or "")
    ] for r in rows]

    buf = _build_xlsx(headers, data)
    return _stream_xlsx(f"conversations_{bj_now().strftime('%Y%m%d')}.xlsx", buf)
```

## app/routers/device.py

```python
"""Device-facing API — poll, report, heartbeat, selectors."""
import logging
from fastapi import APIRouter, HTTPException, Query, Depends, UploadFile, File as FastAPIFile, WebSocket, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session
import asyncio
import io

logger = logging.getLogger(__name__)

from app.models import (
    TaskProgressReport, TaskResultReport, PollResponse, DeviceRegisterRequest,
    DeviceRegisterResponse, RiskReport, DeviceGenerateRequest, DeviceGenerateResponse,
    DeviceAIProxyRequest, DeviceAIProxyResponse, PairRequestCreate, PairStatusResponse,
    CollectReportRequest, CollectCommentData, CollectUserData,
    DMClaimRecipientRequest, DMClaimRecipientResponse,
    DMSendReportRequest, DMReleaseRecipientRequest, DMReleaseRecipientResponse,
    StatsIncrementRequest,
)
from app.database import get_db
from app.deps import verify_device_secret, verify_admin_token
from app.services.task_service import task_service
from app.config import ANTI_DETECT_CONFIG, ANTI_DETECT_CONFIG_VERSION, DEVICE_CONFIG, bj_now
from app.services.selector_service import selector_service
from app.services.prompt_template_service import prompt_template_service
from app.ws_manager import pair_ws_manager

router = APIRouter(prefix="/api/device", tags=["device"])

# In-memory rate limiter for unauthenticated endpoints (pair-request)
_pair_rate_limits: dict[str, list] = {}  # IP → [timestamps]


async def _notify_pending_tasks(db: Session, device_id: str):
    """Check if there are pending tasks for this device and notify it via WS."""
    import logging
    logger = logging.getLogger(__name__)

    from app.db_models import Device, Task as DBTask
    from app.models import TaskStatus
    from datetime import datetime, timezone
    from sqlalchemy import or_, and_

    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        logger.info(f"[notify] 设备 {device_id} 不存在，跳过")
        return

    now = bj_now()
    device_user_id = device.user_id

    # Build routing filter (same logic as task_service.get_pending_task)
    if device.bound_account_id:
        route_filter = or_(
            DBTask.device_id == device_id,
            and_(DBTask.device_id.is_(None), DBTask.account_id == device.bound_account_id),
        )
        logger.info(f"[notify] 设备 {device_id} 绑定账号 {device.bound_account_id}，查询匹配任务...")
    else:
        bound_account_ids = db.query(Device.bound_account_id).filter(
            Device.bound_account_id.isnot(None)
        ).scalar_subquery()
        route_filter = or_(
            DBTask.device_id == device_id,
            and_(DBTask.device_id.is_(None), ~DBTask.account_id.in_(bound_account_ids)),
        )
        logger.info(f"[notify] 设备 {device_id} 未绑定账号，查询孤儿任务...")

    pending_task_query = db.query(DBTask).filter(
        DBTask.status == TaskStatus.PENDING.value,
        route_filter,
        or_(DBTask.scheduled_at.is_(None), DBTask.scheduled_at <= now),
    )
    if device_user_id:
        pending_task_query = pending_task_query.filter(
            or_(DBTask.user_id == device_user_id, DBTask.user_id.is_(None))
        )
    pending_tasks = pending_task_query.all()

    # Also check pending channel items for this device
    from app.db_models import ChannelItem, Channel
    channel_subquery = db.query(Channel.id).filter(
        Channel.status == "active", Channel.deleted_at.is_(None)
    )
    if device_user_id:
        channel_subquery = channel_subquery.filter(
            or_(Channel.user_id == device_user_id, Channel.user_id.is_(None))
        )
    channel_item_query = db.query(ChannelItem).filter(
        ChannelItem.status == "pending",
        ChannelItem.channel_id.in_(channel_subquery),
    )
    if device.bound_account_id:
        channel_item_query = channel_item_query.filter(ChannelItem.account_id == device.bound_account_id)
    pending_channel_count = channel_item_query.count()

    logger.info(f"[notify] 设备 {device_id} 找到 {len(pending_tasks)} 个待执行任务, {pending_channel_count} 个待分发通道项")

    if pending_tasks or pending_channel_count > 0:
        sent = await pair_ws_manager.send_to_device(device_id, {"event": "new_task_available"})
        logger.info(f"[notify] 向设备 {device_id} 推送 new_task_available: {'成功' if sent else '失败'}")


@router.post("/pair-request", response_model=PairStatusResponse)
async def create_pair_request(
    request: PairRequestCreate,
    raw_request: Request,
    db: Session = Depends(get_db),
):
    """Unauthenticated — device sends pairing request to server.

    Flow:
    1. Device already has a valid secret → return "approved" (reconnect)
    2. Pending request exists → return same token (don't duplicate)
    3. Otherwise → clean old rejected, create new pending, notify admins
    """
    import uuid
    from app.db_models import DevicePairRequest, Device

    # Capture client IP (prefer X-Forwarded-For for reverse proxy setups)
    client_ip = raw_request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if not client_ip:
        client_ip = raw_request.client.host if raw_request.client else ""

    # Rate limit: max 5 pair requests per hour per IP
    import time as _time
    now_ts = _time.time()
    window = now_ts - 3600
    _pair_rate_limits.setdefault(client_ip, [])
    _pair_rate_limits[client_ip] = [t for t in _pair_rate_limits[client_ip] if t > window]
    if not _pair_rate_limits[client_ip]:
        _pair_rate_limits.pop(client_ip, None)  # prevent memory leak: clean empty entries
    elif len(_pair_rate_limits[client_ip]) >= 5:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    _pair_rate_limits.setdefault(client_ip, []).append(now_ts)

    # 1. Already paired — Device exists with a valid secret
    # SECURITY: Do NOT auto-return secret. If the device lost its local config,
    # create a new pending request so admin must re-approve.
    device = db.query(Device).filter(Device.id == request.device_id).first()
    if device and device.device_secret:
        # Update IP and device info on reconnect
        device.ip = client_ip or device.ip
        device.screen_resolution = request.screen_resolution or device.screen_resolution
        device.sdk_version = request.sdk_version or device.sdk_version
        device.total_memory = request.total_memory or device.total_memory
        device.manufacturer = request.manufacturer or device.manufacturer
        device.product = request.product or device.product
        device.device_model = request.device_model or device.device_model
        device.hardware = request.hardware or device.hardware
        device.display = request.display or device.display
        db.commit()
        # Create a new pending pair request — admin must re-approve
        # to disclose the secret. Don't auto-return it.
        logger.warning(
            "Already-paired device %s re-requested pairing (secret not disclosed). "
            "Creating pending request for admin re-approval.",
            request.device_id,
        )
        # Fall through to pending/new request logic below

    # 2. Pending request already exists — return same token
    pending = db.query(DevicePairRequest).filter(
        DevicePairRequest.device_id == request.device_id,
        DevicePairRequest.status == "pending",
    ).first()
    if pending:
        # Update IP and device info on re-request
        device = db.query(Device).filter(Device.id == request.device_id).first()
        if device:
            device.ip = client_ip or device.ip
            db.commit()
        return PairStatusResponse(pairing_token=pending.pairing_token, status="pending")

    # 3. Clean old rejected requests for this device (allow re-pairing)
    db.query(DevicePairRequest).filter(
        DevicePairRequest.device_id == request.device_id,
        DevicePairRequest.status == "rejected",
    ).delete()
    db.commit()

    # 4. Create new pair request with enriched device info
    token = uuid.uuid4().hex
    pair_req = DevicePairRequest(
        pairing_token=token,
        device_id=request.device_id,
        device_name=request.device_name,
        os_version=request.os_version,
        app_version=request.app_version,
        screen_resolution=request.screen_resolution,
        sdk_version=request.sdk_version,
        total_memory=request.total_memory,
        manufacturer=request.manufacturer,
        product=request.product,
        device_model=request.device_model,
        hardware=request.hardware,
        display=request.display,
        status="pending",
    )
    db.add(pair_req)

    # Also create/update Device record with IP
    device = db.query(Device).filter(Device.id == request.device_id).first()
    if device:
        device.ip = client_ip or device.ip
    else:
        device = Device(
            id=request.device_id,
            name=request.device_name,
            ip=client_ip,
            os_version=request.os_version,
            app_version=request.app_version,
            status="offline",
        )
        db.add(device)

    db.commit()
    db.refresh(pair_req)

    # 5. Broadcast to admin clients
    await pair_ws_manager.broadcast_to_admins({
        "event": "new_pair_request",
        "request": {
            "id": pair_req.id,
            "device_id": pair_req.device_id,
            "device_name": pair_req.device_name,
            "os_version": pair_req.os_version,
            "app_version": pair_req.app_version,
            "screen_resolution": pair_req.screen_resolution,
            "sdk_version": pair_req.sdk_version,
            "total_memory": pair_req.total_memory,
            "manufacturer": pair_req.manufacturer,
            "product": pair_req.product,
            "device_model": pair_req.device_model,
            "hardware": pair_req.hardware,
            "display": pair_req.display,
            "status": pair_req.status,
            "ip": client_ip,
            "created_at": str(pair_req.created_at),
        },
    })

    return PairStatusResponse(pairing_token=token, status="pending")


def _build_approved_payload(pair_req, db=None) -> dict:
    """Build the approved response payload (shared by HTTP and WS)."""
    from app.config import DEVICE_CONFIG, ANTI_DETECT_CONFIG, ANTI_DETECT_CONFIG_VERSION, get_ai_config

    config = {
        **DEVICE_CONFIG,
        "anti_detect_config": ANTI_DETECT_CONFIG,
        "anti_detect_config_version": ANTI_DETECT_CONFIG_VERSION,
    }
    ai_cfg = get_ai_config(db)
    if ai_cfg:
        config["ai_config"] = ai_cfg

    return {
        "status": "approved",
        "secret": pair_req.device_secret,
        "config": config,
    }


@router.get("/pair-status", response_model=PairStatusResponse)
def check_pair_status(
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    """Unauthenticated — device polls for approval result."""
    from app.db_models import DevicePairRequest, Device

    pair_req = db.query(DevicePairRequest).filter(
        DevicePairRequest.pairing_token == token,
    ).first()

    if not pair_req:
        raise HTTPException(status_code=404, detail="Pairing request not found")

    if pair_req.status == "pending":
        return PairStatusResponse(status="pending")

    if pair_req.status == "rejected":
        return PairStatusResponse(status="rejected")

    # Approved — verify Device still exists with matching secret
    device = db.query(Device).filter(Device.id == pair_req.device_id).first()
    if not device or device.device_secret != pair_req.device_secret:
        # Device was deleted or secret changed — need re-approval
        return PairStatusResponse(status="pending")

    payload = _build_approved_payload(pair_req)
    return PairStatusResponse(**payload)


@router.websocket("/ws/pair/{token}")
async def ws_pair_status(websocket: WebSocket, token: str):
    """Device connects via WS to receive real-time pairing approval result."""
    from app.db_models import DevicePairRequest, Device

    db = next(get_db())
    try:
        pair_req = db.query(DevicePairRequest).filter(
            DevicePairRequest.pairing_token == token,
        ).first()

        if not pair_req:
            await websocket.close(code=4004, reason="Invalid token")
            return

        # Already resolved — send result immediately and close
        if pair_req.status == "approved":
            # Verify Device still exists with matching secret
            device = db.query(Device).filter(Device.id == pair_req.device_id).first()
            if device and device.device_secret == pair_req.device_secret:
                await websocket.accept()
                await websocket.send_json(_build_approved_payload(pair_req))
                await websocket.close()
                return
            # Device deleted or secret changed — treat as pending (wait for re-approval)
            pair_req.status = "pending"
            db.commit()
        elif pair_req.status == "rejected":
            await websocket.accept()
            await websocket.send_json({"status": "rejected"})
            await websocket.close()
            return

        # pending — register connection, wait for admin action
        await pair_ws_manager.register(token, websocket)

        try:
            while True:
                # Keep connection alive; timeout after 5 minutes
                await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=300,
                )
        except (asyncio.TimeoutError, Exception):
            pass
        finally:
            pair_ws_manager.unregister(token)
    finally:
        db.close()


@router.websocket("/ws/status")
async def ws_device_status(websocket: WebSocket):
    """Device maintains a persistent WS connection for status tracking.
    Server detects disconnect immediately → marks device offline → broadcasts to admins.

    Authentication: device sends {"type":"auth","device_id":"...","secret":"..."}
    as the first message after connect (not in URL).
    """
    from app.db_models import Device
    from app.config import DEVICE_SECRET

    await websocket.accept()

    # Read auth message (first message after connect)
    try:
        auth_msg = await asyncio.wait_for(websocket.receive_json(), timeout=10)
    except (asyncio.TimeoutError, Exception):
        await websocket.close(code=4001, reason="Auth timeout or invalid message")
        return

    device_id = auth_msg.get("device_id", "")
    secret = auth_msg.get("secret", "")

    if not secret or not device_id:
        await websocket.close(code=4001, reason="Missing device_id or secret")
        return

    db = next(get_db())
    try:
        if secret != DEVICE_SECRET:
            device = db.query(Device).filter(Device.device_secret == secret).first()
            if not device:
                await websocket.close(code=4001, reason="Invalid secret")
                return
            device_id = device.id

        # Register WS connection FIRST — before DB update — so _offline_checker
        # never sees "DB online but no WS" during the race window
        await pair_ws_manager.register_device_status(device_id, websocket)

        # Mark device online and capture IP
        from app.services.device_service import device_service
        ws_client_ip = websocket.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if not ws_client_ip:
            ws_client_ip = websocket.client.host if websocket.client else ""
        device_service.update_heartbeat(db, device_id, ip=ws_client_ip)
        await pair_ws_manager.broadcast_to_admins({
            "event": "device_status_changed",
            "device_id": device_id,
            "status": "online",
        })

        # Check for pending tasks and notify device
        await _notify_pending_tasks(db, device_id)

        import logging
        _ws_log = logging.getLogger("device_ws")
        from starlette.websockets import WebSocketDisconnect
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(websocket.receive_text(), timeout=120)
                    if msg == '{"event":"device_disconnect"}':
                        _ws_log.info("device %s disconnected (explicit), marking offline", device_id)
                        try:
                            dev = db.query(Device).filter(Device.id == device_id).first()
                            if dev:
                                dev.status = "offline"
                                dev.last_seen_at = bj_now()
                                db.commit()
                        except Exception:
                            _ws_log.warning("device %s offline mark failed", device_id, exc_info=True)
                        await pair_ws_manager.broadcast_to_admins({
                            "event": "device_status_changed",
                            "device_id": device_id,
                            "status": "offline",
                        })
                        break
                    if msg == "ping":
                        await websocket.send_text("pong")
                        # Record heartbeat in memory — _offline_checker flushes to DB
                        pair_ws_manager.record_heartbeat(device_id, bj_now())
                except asyncio.TimeoutError:
                    try:
                        await websocket.send_text("ping")
                        msg = await asyncio.wait_for(websocket.receive_text(), timeout=10)
                    except asyncio.TimeoutError:
                        _ws_log.warning("device %s unresponsive to ping", device_id)
                        break
                    except WebSocketDisconnect:
                        _ws_log.info("device %s disconnected during ping probe", device_id)
                        break
                    except Exception:
                        _ws_log.warning("device %s error during ping probe", device_id, exc_info=True)
                        break
                except WebSocketDisconnect as dis:
                    _ws_log.info("device %s disconnected (code=%s)", device_id, dis.code)
                    break
        except Exception:
            _ws_log.warning("device %s WS loop exited with error", device_id, exc_info=True)
        finally:
            # 只在本连接仍是活跃连接时才清理（避免重连竞态）
            # WS 断开不标记离线 — _offline_checker 通过心跳超时统一判定
            if pair_ws_manager._device_status_connections.get(device_id) is websocket:
                pair_ws_manager.unregister_device_status(device_id)
    finally:
        db.close()


@router.get("/poll", response_model=PollResponse)
async def poll_tasks(
    device_id: str = Query(...),
    db: Session = Depends(get_db),
    authed_device_id: Optional[str] = Depends(verify_device_secret),
):
    # Per-device secret: use the verified device_id, reject mismatch
    if authed_device_id and authed_device_id != device_id:
        raise HTTPException(status_code=403, detail="Device ID mismatch")
    if authed_device_id:
        device_id = authed_device_id

    # HTTP poll itself is a heartbeat — update last_seen_at
    from app.services.device_service import device_service
    device_service.update_heartbeat(db, device_id)

    task = task_service.get_pending_task(db, device_id)
    version = selector_service.get_version(db)
    tmpl_version = prompt_template_service.get_version(db)

    # 设备领到任务 → 通知前端任务列表更新
    if task:
        await pair_ws_manager.broadcast_to_admins({
            "event": "task_updated",
            "task_id": task.id,
            "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
        })

    from app.services.device_service import device_service
    device_info = device_service.get_device_status(db, device_id)
    proxy = device_info.get("proxy_config") if device_info else None

    cancelled_task = task_service.check_cancelled_running(db, device_id)

    # DM sequence templates for device sync — scoped by device owner
    from app.db_models import DMSequence, Device
    device = db.query(Device).filter(Device.id == device_id).first()
    device_user_id = device.user_id if device else None
    dm_seqs = db.query(DMSequence).filter(
        (DMSequence.user_id == device_user_id) | (DMSequence.user_id == None)
    ).all()
    dm_sequences_list = [
        {
            "id": s.id,
            "messages": s.messages,
            "variants": s.variants,
        }
        for s in dm_seqs
    ] if dm_seqs else None
    logger.info("[poll] device=%s dm_sequences count=%s ids=%s",
        device_id,
        len(dm_sequences_list) if dm_sequences_list else 0,
        [s["id"][:8] for s in dm_sequences_list] if dm_sequences_list else [])
    if dm_sequences_list:
        for ds in dm_sequences_list:
            msgs = ds.get("messages", [])
            logger.info("[poll] dm_seq id=%s msg_count=%s msg_preview=%s",
                ds["id"][:8], len(msgs),
                [m.get("content","")[:30] for m in msgs[:2]] if msgs else [])

    from app.config import get_ai_config

    if task:
        logger.info("[poll] device=%s dispatching task_id=%s type=%s dm_seq_id=%s dm_messages=%s",
            device_id, task.id[:8], task.type,
            (task.params or {}).get("dm_sequence_id", "NONE"),
            "PRESENT" if (task.params or {}).get("dm_messages") else "NONE")

    return PollResponse(
        task=task,
        selectors_version=version,
        prompt_templates_version=tmpl_version,
        proxy=proxy,
        cancelled_task_id=cancelled_task.id if cancelled_task else None,
        anti_detect_config=ANTI_DETECT_CONFIG,
        anti_detect_config_version=ANTI_DETECT_CONFIG_VERSION,
        ai_config=get_ai_config(db),
        device_config=DEVICE_CONFIG,
        dm_sequences=dm_sequences_list,
        server_date=bj_now().strftime("%Y-%m-%d"),
    )


@router.post("/progress")
async def report_progress(
    report: TaskProgressReport,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    """Device reports task execution progress. Broadcast to admin WS for real-time UI."""
    from app.db_models import Task as DBTask
    db_task = db.query(DBTask).filter(DBTask.id == report.task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    if db_task.device_id != authed_device_id:
        raise HTTPException(status_code=403, detail="Task does not belong to this device")

    await pair_ws_manager.broadcast_to_admins({
        "event": "task_progress",
        "task_id": report.task_id,
        "step": report.step,
        "detail": report.detail,
        "progress": report.progress,
    })
    return {"ok": True}


@router.post("/report")
async def report_result(
    report: TaskResultReport,
    db: Session = Depends(get_db),
    authed_device_id: Optional[str] = Depends(verify_device_secret),
):
    # Verify the task belongs to this device (reject if unassigned or mismatched)
    if authed_device_id:
        from app.db_models import Task as DBTask
        db_task = db.query(DBTask).filter(DBTask.id == report.task_id).first()
        if not db_task:
            raise HTTPException(status_code=404, detail="Task not found")
        if db_task.device_id != authed_device_id:
            raise HTTPException(status_code=403, detail="Task does not belong to this device")

    try:
        task, channel_broadcast_info = task_service.report_result(
            db=db,
            task_id=report.task_id,
            status=report.status,
            result=report.result,
            ui_snapshot=report.ui_snapshot,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="Task not found")

    # Broadcast task status update to admin WS
    await pair_ws_manager.broadcast_to_admins({
        "event": "task_updated",
        "task_id": str(report.task_id),
        "status": str(report.status.value),
        "result": report.result or {},
    })

    # 通知所有在线设备有新任务可领取（通道内可能有下一批待执行 item）
    if report.status.value in ("completed", "failed"):
        await pair_ws_manager.broadcast_to_devices({"event": "new_task_available"})

    # Broadcast channel progress via WS (BackgroundTasks runs after response)
    if channel_broadcast_info:
        from fastapi import BackgroundTasks
        bg = BackgroundTasks()
        bg.add_task(pair_ws_manager.broadcast_channel_progress,
                    channel_broadcast_info["channel_id"], channel_broadcast_info["stats"])
        if channel_broadcast_info.get("channel_completed"):
            bg.add_task(pair_ws_manager.broadcast_channel_completed,
                        channel_broadcast_info["channel_id"])
        from fastapi.encoders import jsonable_encoder
        return JSONResponse(content=jsonable_encoder(task), background=bg)

    return task


@router.post("/stats/increment")
def stats_increment(
    body: StatsIncrementRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_device_secret),
):
    """设备端增量统计上报——每完成一个子操作（回复/关注/私信）调用一次。
    保证任务中途崩溃时，已完成操作的统计数据不丢失。
    """
    from app.services.stats_service import stats_service
    stats_service.increment(db, body.account_id, body.task_type, count=body.count)
    db.commit()
    return {"ok": True}


@router.post("/heartbeat")
async def heartbeat(
    body: dict,
    raw_request: Request,
    db: Session = Depends(get_db),
    authed_device_id: Optional[str] = Depends(verify_device_secret),
):
    device_id = body.get("device_id", "")
    # Per-device secret: use the verified device_id, reject mismatch
    if authed_device_id and authed_device_id != device_id:
        raise HTTPException(status_code=403, detail="Device ID mismatch")
    if authed_device_id:
        device_id = authed_device_id

    client_ip = raw_request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if not client_ip:
        client_ip = raw_request.client.host if raw_request.client else ""
    from app.services.device_service import device_service
    status_changed = device_service.update_heartbeat(db, device_id, ip=client_ip)
    if status_changed:
        await pair_ws_manager.broadcast_to_admins({
            "event": "device_status_changed",
            "device_id": device_id,
            "status": "online",
        })
        await _notify_pending_tasks(db, device_id)
    return {"status": "ok", "device_id": device_id}


@router.post("/register", response_model=DeviceRegisterResponse)
def register_device(
    request: DeviceRegisterRequest,
    raw_request: Request,
    db: Session = Depends(get_db),
    authed_device_id: Optional[str] = Depends(verify_device_secret),
):
    # Per-device secret: reject mismatch
    if authed_device_id and authed_device_id != request.device_id:
        raise HTTPException(status_code=403, detail="Device ID mismatch")
    from app.services.device_service import device_service
    from app.config import get_ai_config

    # Capture client IP
    client_ip = raw_request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if not client_ip:
        client_ip = raw_request.client.host if raw_request.client else ""

    result = device_service.register(
        db=db, device_id=request.device_id, name=request.name,
        os_version=request.os_version, app_version=request.app_version,
        ip=client_ip,
        screen_resolution=request.screen_resolution,
        sdk_version=request.sdk_version,
        total_memory=request.total_memory,
        manufacturer=request.manufacturer,
        product=request.product,
        device_model=request.device_model,
        hardware=request.hardware,
        display=request.display,
    )

    # 组装完整设备配置
    config = {
        **DEVICE_CONFIG,
        "anti_detect_config": ANTI_DETECT_CONFIG,
        "anti_detect_config_version": ANTI_DETECT_CONFIG_VERSION,
    }
    ai_cfg = get_ai_config(db)
    if ai_cfg:
        config["ai_config"] = ai_cfg

    return DeviceRegisterResponse(
        device_id=result["device_id"],
        name=result["name"],
        status=result["status"],
        config=config,
    )


@router.get("/selectors")
def get_selectors(
    version: int = Query(0),
    db: Session = Depends(get_db),
    device_id: str = Depends(verify_device_secret),
):

    current_version, selectors = selector_service.get_all_selectors(db, device_id=device_id)
    if version == current_version:
        return {"version": current_version, "selectors": None, "changed": False}

    return {
        "version": current_version,
        "selectors": selectors,
        "changed": True,
    }


@router.get("/prompt-templates")
def get_prompt_templates(
    version: int = Query(0),
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    current_version, templates = prompt_template_service.get_all_templates(db)
    if version == current_version:
        return {"version": current_version, "templates": None, "changed": False}

    return {
        "version": current_version,
        "templates": templates,
        "changed": True,
    }


@router.get("/script-version")
def script_version(
    _: None = Depends(verify_device_secret),
):
    from app.services.script_service import script_service
    return {"version": script_service.get_version()}


@router.get("/script-download")
def script_download(
    _: None = Depends(verify_device_secret),
):
    from app.services.script_service import script_service
    from fastapi.responses import Response
    data = script_service.download_script()
    if data is None:
        raise HTTPException(status_code=404, detail="No script available")
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=device-script.zip"},
    )


@router.post("/script-upload")
async def script_upload(
    file: UploadFile = FastAPIFile(...),
    user = Depends(verify_admin_token),
):
    from app.services.script_service import script_service
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files accepted")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")
    new_version = script_service.upload_script(io.BytesIO(content))
    return {"version": new_version, "size": len(content)}


@router.post("/risk-report")
async def report_risk(
    report: RiskReport,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    """Device reports risk control detection. Marks account as risk_controlled."""
    from app.db_models import Account
    account = db.query(Account).filter(Account.id == report.account_id).first()
    if not account:
        return {"status": "ignored", "account_status": "unknown"}
    if account.status == "active":
        account.status = "risk_controlled"
        # Skip pending channel items for this account
        from app.services.channel_service import channel_service
        channel_service.on_risk_control(db, report.account_id)
        db.commit()
        await pair_ws_manager.broadcast_to_admins({"event": "accounts_changed"})
    return {"status": "acknowledged", "account_status": account.status}


class CommentRepliedRequest(BaseModel):
    author: str = Field(..., description="评论作者")
    text: str = Field(..., description="评论内容")


@router.post("/comment-claim-reply")
def claim_comment_reply(
    request: CommentRepliedRequest,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    """原子操作：检查+标记。返回 claimed=true 表示该设备可以回复，false 表示已被其他设备占用"""
    import hashlib
    from sqlalchemy.exc import IntegrityError
    content_hash = hashlib.sha256(
        (request.author + "|" + request.text).encode("utf-8")
    ).hexdigest()
    from app.db_models import RepliedComment
    # INSERT first — PK collision triggers IntegrityError, no SELECT+INSERT race window
    db.add(RepliedComment(
        content_hash=content_hash,
        author=request.author,
        text=request.text,
        replied_by_device=authed_device_id,
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"claimed": False, "hash": content_hash}
    return {"claimed": True, "hash": content_hash}


@router.post("/comment-claim-release")
def release_comment_claim(
    request: CommentRepliedRequest,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    """回复失败时释放占位，避免误标记为已回复"""
    import hashlib
    content_hash = hashlib.sha256(
        (request.author + "|" + request.text).encode("utf-8")
    ).hexdigest()
    from app.db_models import RepliedComment
    db.query(RepliedComment).filter(
        RepliedComment.content_hash == content_hash,
        RepliedComment.replied_by_device == authed_device_id,
    ).delete()
    db.commit()
    return {"released": True}


@router.post("/generate-content", response_model=DeviceGenerateResponse)
async def generate_content(
    request: DeviceGenerateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    """Generate content from a template on-demand."""
    from app.services.content_service import content_service

    try:
        content = await content_service.generate_from_template(
            db, request.template_id, request.context,
        )
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail="Template not found")
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        if "not configured" in str(e):
            raise HTTPException(status_code=503, detail="AI service not configured")
        raise HTTPException(status_code=502, detail=f"AI service error: {e}")

    return DeviceGenerateResponse(content=content, template_id=request.template_id)


@router.get("/templates")
def device_list_templates(
    device_id: str = Depends(verify_device_secret),
    db: Session = Depends(get_db),
    resolution: str = Query(None),
):
    """Return template list with MD5 hashes for incremental sync.
    Filters by device resolution profile when available."""
    from app.services.template_service import template_service
    if not resolution and device_id:
        device = db.query(Device).filter(Device.id == device_id).first()
        if device and device.screen_resolution:
            resolution = device.screen_resolution
    templates = template_service.list_templates(resolution=resolution)
    return {"templates": templates}


@router.get("/templates/{filename}")
def device_download_template(
    filename: str,
    device_id: str = Depends(verify_device_secret),
    db: Session = Depends(get_db),
):
    """Download a single template image (binary). Falls back to 'default' resolution."""
    from app.services.template_service import template_service
    from fastapi.responses import FileResponse
    resolution = "default"
    if device_id:
        device = db.query(Device).filter(Device.id == device_id).first()
        if device and device.screen_resolution:
            resolution = device.screen_resolution
    filepath = template_service.get_template_path(filename, resolution=resolution)
    if not filepath:
        raise HTTPException(status_code=404, detail="模板文件不存在")
    return FileResponse(str(filepath), media_type="image/png", filename=filename)


class CalibrationItem(BaseModel):
    action_name: str
    filename: str
    data: str  # base64-encoded PNG


class CalibrationRequest(BaseModel):
    templates: list[CalibrationItem]
    resolution: str = ""


@router.post("/calibrate")
async def device_calibrate(
    request: CalibrationRequest,
    db: Session = Depends(get_db),
    device_id: str = Depends(verify_device_secret),
):
    """Device uploads auto-calibrated image templates.
    Saves templates and upserts UISelector rows for this resolution profile."""
    import base64
    from app.services.template_service import template_service
    from app.db_models import UISelector, Device

    resolution = request.resolution
    if not resolution:
        device = db.query(Device).filter(Device.id == device_id).first()
        if device and device.screen_resolution:
            resolution = device.screen_resolution
    if not resolution:
        raise HTTPException(status_code=400, detail="无法确定设备分辨率")

    uploaded = 0
    for item in request.templates:
        # Decode and save template
        try:
            content = base64.b64decode(item.data)
        except Exception:
            continue
        template_service.save_template(item.filename, content, resolution=resolution)

        # Upsert selector: clone existing "default" profile selector for this resolution
        existing = db.query(UISelector).filter(
            UISelector.action_name == item.action_name,
            UISelector.resolution_profile == resolution,
        ).first()
        if not existing:
            # Clone from default profile if it exists
            default_sel = db.query(UISelector).filter(
                UISelector.action_name == item.action_name,
                UISelector.resolution_profile == "default",
            ).first()
            if default_sel:
                new_sel = UISelector(
                    action_name=item.action_name,
                    description=default_sel.description,
                    platform_version=default_sel.platform_version,
                    resolution_profile=resolution,
                    strategies=default_sel.strategies,
                    version=1,
                    category=default_sel.category,
                    purpose=default_sel.purpose,
                    strategy_logic=default_sel.strategy_logic,
                    extract_field=default_sel.extract_field,
                    clean_mode=default_sel.clean_mode,
                    clean_pattern=default_sel.clean_pattern,
                    clean_prompt=default_sel.clean_prompt,
                )
                db.add(new_sel)
        uploaded += 1

    db.commit()

    # Broadcast version bump
    version = selector_service.get_version(db)
    await pair_ws_manager.broadcast_to_devices({
        "event": "selectors_updated",
        "version": version,
    })
    await pair_ws_manager.broadcast_to_admins({"event": "selectors_changed"})

    return {"uploaded": uploaded, "resolution": resolution}


@router.post("/ai-proxy", response_model=DeviceAIProxyResponse)
async def ai_proxy(
    request: DeviceAIProxyRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    """设备端 AI 代理 — 设备不持有 API Key，通过服务端调用 AI。"""
    import httpx
    from app.config import get_ai_config_with_key

    ai_cfg = get_ai_config_with_key(db)
    if not ai_cfg or not ai_cfg.get("api_url"):
        raise HTTPException(status_code=503, detail="AI service not configured")

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            model = ai_cfg.get("model", "deepseek-chat")
            json_body = {
                "model": model,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
                "messages": [{"role": "user", "content": request.prompt}],
            }
            # thinking 参数仅在 deepseek-reasoner 或明确支持 thinking 的模型上发送
            if ai_cfg.get("thinking_enabled") and ("reasoner" in model.lower() or "r1" in model.lower()):
                json_body["thinking"] = {"type": "enabled"}
            logger.debug("AI proxy request: model=%s max_tokens=%s temp=%s prompt_len=%s thinking=%s",
                          model, request.max_tokens, request.temperature, len(request.prompt),
                          "thinking" in json_body)
            resp = await client.post(
                ai_cfg["api_url"],
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {ai_cfg.get('api_key', '')}",
                },
                json=json_body,
            )
        if resp.status_code != 200:
            logger.error("AI API error: status=%s body=%s", resp.status_code, resp.text[:500])
            raise HTTPException(status_code=502, detail=f"AI API error: {resp.status_code}")
        result = resp.json()
        logger.debug("AI API response: %s", {k: str(v)[:200] for k, v in result.items() if k != "choices"})
        content = (result.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
        if not content:
            logger.error("AI API returned empty content. Full response: %s", str(result)[:1000])
        return DeviceAIProxyResponse(content=content)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="AI API timeout")
    except (KeyError, IndexError) as e:
        logger.error("Invalid AI response structure: %s", e)
        raise HTTPException(status_code=502, detail=f"Invalid AI response: {e}")

# --- 采集数据上报 ---


_dest_cache: dict[str, dict] = {}

async def _resolve_destination(keyword: str, db) -> dict | None:
    """服务端解析旅游关键词→省份/城市/景点，按 keyword 缓存。"""
    if not keyword or keyword in _dest_cache:
        return _dest_cache.get(keyword)
    from app.services.ai_generator import ai_generator
    try:
        raw = await ai_generator.generate_custom(
            db,
            "只输出 JSON，不要其他文本。",
            "将以下旅游关键词解析为目的地信息。\n关键词：" + keyword + "\n输出格式：{\"province\":\"省份\",\"city\":\"城市\",\"attraction\":\"景点\"}\n如果关键词本身是省份或城市，对应字段填空字符串。",
            max_tokens=200, temperature=0.1,
        )
        import json
        m = __import__("re").search(r'\{[\s\S]*\}', raw)
        if m:
            data = json.loads(m.group(0))
            _dest_cache[keyword] = data
            return data
    except Exception:
        pass
    _dest_cache[keyword] = None
    return None


@router.post("/collect-report")
async def collect_report(
    request: CollectReportRequest,
    db: Session = Depends(get_db),
    device_id: str = Depends(verify_device_secret),
):
    from app.db_models import CollectedComment, CollectedUser
    from sqlalchemy.exc import IntegrityError

    # 1. 解析目的地（设备端未传时服务端兜底，仅旅游行业任务触发）
    _is_travel = False
    has_dest = (request.comment.intended_province or request.comment.intended_city or request.comment.intended_attraction)
    if not has_dest and request.keyword and request.task_id:
        from app.db_models import Task
        task = db.query(Task).filter(Task.id == request.task_id).first()
        if task and task.params:
            tid = task.params.get("prompt_template_id")
            if tid:
                from app.db_models import PromptTemplate
                pt = db.query(PromptTemplate).filter(PromptTemplate.id == tid).first()
                _is_travel = pt and pt.industry == "travel"
    if _is_travel and not has_dest and request.keyword:
        dest = await _resolve_destination(request.keyword, db)
        if dest:
            if not request.comment.intended_province:
                request.comment.intended_province = dest.get("province")
            if not request.comment.intended_city:
                request.comment.intended_city = dest.get("city")
            if not request.comment.intended_attraction:
                request.comment.intended_attraction = dest.get("attraction")

    # 2. 保存评论（独立提交，用户去重失败不影响评论落库）
    comment = CollectedComment(
        task_id=request.task_id,
        device_id=device_id,
        keyword=request.keyword,
        nickname=request.comment.nickname,
        content=request.comment.content,
        time_str=request.comment.time_str,
        reply_count=request.comment.reply_count,
        like_count=request.comment.like_count,
        dislike_count=request.comment.dislike_count,
        location=request.comment.location,
        is_author=request.comment.is_author,
        data_source_type=request.data_source_type,
        ai_reply=request.comment.ai_reply,
        ai_replied_at=bj_now() if request.comment.ai_reply else None,
        intended_province=request.comment.intended_province or None,
        intended_city=request.comment.intended_city or None,
        intended_attraction=request.comment.intended_attraction or None,
    )
    db.add(comment)
    db.commit()  # 评论独立提交

    # 2. 保存用户（存在则更新，不存在则新建）
    user_new = False
    if request.user and request.user.douyin_id:
        existing = db.query(CollectedUser).filter(
            CollectedUser.douyin_id == request.user.douyin_id
        ).first()
        if existing:
            existing.nickname = request.user.nickname
            existing.likes_count = request.user.likes_count
            existing.follow_count = request.user.follow_count
            existing.fans_count = request.user.fans_count
            existing.works_count = request.user.works_count
            existing.gender = request.user.gender
            existing.age = request.user.age
            existing.ip_location = request.user.ip_location
            existing.is_private = request.user.is_private
            existing.data_source_type = request.data_source_type
            existing.keyword = request.keyword
            existing.task_id = request.task_id
            existing.device_id = device_id
            if request.comment.intended_province:
                existing.intended_province = request.comment.intended_province
            if request.comment.intended_city:
                existing.intended_city = request.comment.intended_city
            if request.comment.intended_attraction:
                existing.intended_attraction = request.comment.intended_attraction
            db.commit()
        else:
            db.add(CollectedUser(
                task_id=request.task_id,
                device_id=device_id,
                keyword=request.keyword,
                nickname=request.user.nickname,
                douyin_id=request.user.douyin_id,
                likes_count=request.user.likes_count,
                follow_count=request.user.follow_count,
                fans_count=request.user.fans_count,
                works_count=request.user.works_count,
                gender=request.user.gender,
                age=request.user.age,
                ip_location=request.user.ip_location,
                is_private=request.user.is_private,
                data_source_type=request.data_source_type,
                intended_province=request.comment.intended_province or None,
                intended_city=request.comment.intended_city or None,
                intended_attraction=request.comment.intended_attraction or None,
            ))
            try:
                db.commit()
                user_new = True
            except IntegrityError:
                db.rollback()
                existing2 = db.query(CollectedUser).filter(
                    CollectedUser.douyin_id == request.user.douyin_id
                ).first()
                if existing2:
                    existing2.nickname = request.user.nickname
                    existing2.likes_count = request.user.likes_count
                    existing2.follow_count = request.user.follow_count
                    existing2.fans_count = request.user.fans_count
                    existing2.works_count = request.user.works_count
                    existing2.gender = request.user.gender
                    existing2.age = request.user.age
                    existing2.ip_location = request.user.ip_location
                    existing2.is_private = request.user.is_private
                    existing2.data_source_type = request.data_source_type
                    existing2.keyword = request.keyword
                    existing2.task_id = request.task_id
                    existing2.device_id = device_id
                    db.commit()

    # WS 实时推送
    await pair_ws_manager.broadcast_to_admins({"event": "data_changed", "type": "comment", "id": comment.id})
    if user_new:
        await pair_ws_manager.broadcast_to_admins({"event": "data_changed", "type": "user", "id": request.user.douyin_id})

    return {"comment_saved": True, "user_new": user_new}


# --- DM conversation endpoints ---

@router.post("/dm-claim-recipient", response_model=DMClaimRecipientResponse)
def dm_claim_recipient(
    request: DMClaimRecipientRequest,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    """原子占用：insert conversation where not exists (account_id, douyin_id).
    SQLite WAL 竞态：并发 SELECT 可能同时通过 → IntegrityError → claimed=false."""
    from app.db_models import Conversation
    from sqlalchemy.exc import IntegrityError
    from datetime import datetime, timezone, timedelta

    now = bj_now()

    # 清理孤儿 claim（超 30min 未发送）
    orphan_threshold = now - timedelta(minutes=30)
    db.query(Conversation).filter(
        Conversation.claimed_at.isnot(None),
        Conversation.claimed_at < orphan_threshold,
        Conversation.status == "active",
        Conversation.last_dm_at.is_(None),
    ).delete()
    db.flush()

    # 检查已有会话
    existing = db.query(Conversation).filter(
        Conversation.account_id == request.account_id,
        Conversation.recipient_douyin_id == request.recipient_douyin_id,
    ).first()
    if existing:
        return DMClaimRecipientResponse(claimed=False, conversation_id=None)

    conv = Conversation(
        task_id=None,
        account_id=request.account_id,
        device_id=authed_device_id,
        recipient_nickname=request.recipient_nickname,
        recipient_douyin_id=request.recipient_douyin_id,
        claimed_at=now,
    )
    db.add(conv)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return DMClaimRecipientResponse(claimed=False, conversation_id=None)

    db.refresh(conv)
    return DMClaimRecipientResponse(claimed=True, conversation_id=conv.id)


@router.post("/dm-send-report")
async def dm_send_report(
    request: DMSendReportRequest,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    """DM 发送成功后上报：更新 stage、content、计数"""
    from app.db_models import Conversation

    now = bj_now()
    conv = db.query(Conversation).filter(Conversation.id == request.conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    if conv.device_id != authed_device_id:
        raise HTTPException(status_code=403, detail="会话不属于此设备")

    conv.current_stage = request.stage
    conv.intent = request.intent
    conv.last_dm_content = request.content
    conv.last_dm_at = now
    conv.total_dm_count = (conv.total_dm_count or 0) + 1
    conv.claimed_at = None  # 清除 claim 标记
    if request.keyword and not conv.keyword:
        conv.keyword = request.keyword
    db.commit()

    await pair_ws_manager.broadcast_to_admins({
        "event": "data_changed", "type": "conversation", "id": conv.id,
    })
    return {"ok": True}


@router.post("/dm-release-recipient", response_model=DMReleaseRecipientResponse)
def dm_release_recipient(
    request: DMReleaseRecipientRequest,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    """DM 发送失败时释放占用。仅允许 claim 设备释放，防止误删其他设备的成功会话。"""
    from app.db_models import Conversation

    conv = db.query(Conversation).filter(
        Conversation.id == request.conversation_id,
        Conversation.device_id == authed_device_id,
        Conversation.last_dm_at.is_(None),  # 尚未成功发送过
    ).first()
    if conv:
        db.delete(conv)
        db.commit()
        return DMReleaseRecipientResponse(released=True)
    return DMReleaseRecipientResponse(released=False)


class CommentAIReplyRequest(BaseModel):
    nickname: str
    text: str
    ai_reply: str
    task_id: str | None = None
    intended_province: str | None = None
    intended_city: str | None = None
    intended_attraction: str | None = None


@router.post("/comment-ai-reply")
def save_comment_ai_reply(
    request: CommentAIReplyRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_device_secret),
):
    """保存 AI 生成的回复到采集的评论记录（按昵称+内容+task_id 匹配，避免跨视频错配）"""
    from app.db_models import CollectedComment
    query = db.query(CollectedComment).filter(
        CollectedComment.nickname == request.nickname,
        CollectedComment.content == request.text,
        CollectedComment.ai_reply.is_(None),
    )
    if request.task_id:
        query = query.filter(CollectedComment.task_id == request.task_id)
    comment = query.order_by(CollectedComment.created_at.desc()).first()
    if comment:
        comment.ai_reply = request.ai_reply
        comment.ai_replied_at = bj_now()
        if request.intended_province is not None:
            comment.intended_province = request.intended_province
        if request.intended_city is not None:
            comment.intended_city = request.intended_city
        if request.intended_attraction is not None:
            comment.intended_attraction = request.intended_attraction
        db.commit()
        return {"updated": True}
    return {"updated": False}


class UserProfileRequest(BaseModel):
    nickname: str
    douyin_id: str = ""
    fans_count: str = ""
    likes_count: str = ""
    follow_count: str = ""
    works_count: str = ""
    gender: str = ""
    age: str = ""
    ip_location: str = ""
    is_private: str = ""
    keyword: str = ""
    task_id: str = ""
    intended_province: str | None = None
    intended_city: str | None = None
    intended_attraction: str | None = None


@router.post("/user-profile")
def save_user_profile(
    request: UserProfileRequest,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    """保存采集到的用户主页数据，按 douyin_id 去重插入。"""
    from app.db_models import CollectedUser
    from sqlalchemy.exc import IntegrityError

    douyin_id = request.douyin_id.strip()
    if not douyin_id:
        return {"saved": False, "reason": "empty douyin_id"}

    existing = db.query(CollectedUser).filter(CollectedUser.douyin_id == douyin_id).first()
    if existing:
        # Update fields if they changed
        changed = False
        for field in ("nickname", "fans_count", "likes_count", "follow_count",
                       "works_count", "gender", "age", "ip_location", "is_private",
                       "keyword"):
            val = getattr(request, field, "") or ""
            if getattr(existing, field, None) != val:
                setattr(existing, field, val)
                changed = True
        for field in ("intended_province", "intended_city", "intended_attraction"):
            val = getattr(request, field, None)
            if val and getattr(existing, field, None) != val:
                setattr(existing, field, val)
                changed = True
        if changed:
            db.commit()
        return {"saved": True, "updated": changed, "user_id": existing.id}

    try:
        user = CollectedUser(
            nickname=request.nickname,
            douyin_id=douyin_id,
            keyword=request.keyword or "",
            task_id=request.task_id or None,
            fans_count=request.fans_count or "",
            likes_count=request.likes_count or "",
            follow_count=request.follow_count or "",
            works_count=request.works_count or "",
            gender=request.gender or "",
            age=request.age or "",
            ip_location=request.ip_location or "",
            is_private=request.is_private or "",
            device_id=authed_device_id,
            intended_province=request.intended_province or None,
            intended_city=request.intended_city or None,
            intended_attraction=request.intended_attraction or None,
        )
        db.add(user)
        db.commit()
        return {"saved": True, "updated": False, "user_id": user.id}
    except IntegrityError:
        db.rollback()
        return {"saved": False, "reason": "duplicate douyin_id"}


class UserAvatarRequest(BaseModel):
    douyin_id: str
    image_base64: str  # base64-encoded JPEG/PNG


@router.post("/user-avatar")
def upload_user_avatar(
    request: UserAvatarRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_device_secret),
):
    """上传用户头像裁剪图，保存到本地并关联 CollectedUser."""
    import base64
    import os
    from app.db_models import CollectedUser

    douyin_id = request.douyin_id.strip()
    if not douyin_id:
        return {"saved": False, "reason": "empty douyin_id"}

    user = db.query(CollectedUser).filter(CollectedUser.douyin_id == douyin_id).first()
    if not user:
        return {"saved": False, "reason": "user not found"}

    try:
        img_data = base64.b64decode(request.image_base64)
    except Exception:
        return {"saved": False, "reason": "invalid base64"}

    if len(img_data) > 512 * 1024:
        return {"saved": False, "reason": "image too large (>512KB)"}

    avatar_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "avatars")
    os.makedirs(avatar_dir, exist_ok=True)
    filename = f"{douyin_id}.jpg"
    filepath = os.path.join(avatar_dir, filename)
    with open(filepath, "wb") as f:
        f.write(img_data)

    user.avatar_url = f"/api/device/avatar/{douyin_id}"
    db.commit()
    return {"saved": True, "filename": filename, "size": len(img_data)}


@router.get("/avatar/{douyin_id}")
def get_user_avatar(douyin_id: str):
    """获取用户头像图片."""
    import os
    from fastapi.responses import FileResponse
    avatar_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "avatars")
    filepath = os.path.join(avatar_dir, f"{douyin_id}.jpg")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Avatar not found")
    return FileResponse(filepath, media_type="image/jpeg")
```

## app/routers/devices.py

```python
"""Device management CRUD API."""
from fastapi import APIRouter, HTTPException, Depends, Query, WebSocket
from typing import Optional, Any
from pydantic import BaseModel
from sqlalchemy.orm import Session
import asyncio

from app.database import get_db
from app.db_models import Device, DevicePairRequest
from app.deps import verify_admin_token, verify_ws_admin_token, require_role
from app.ws_manager import pair_ws_manager

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.websocket("/ws/pair-events")
async def ws_pair_events(websocket: WebSocket, token: str = Query(...)):
    """Admin subscribes to real-time pairing events (new requests, approvals, rejections)."""
    result = verify_ws_admin_token(token)
    if not result or not result[0]:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    user_id, _ = result
    await pair_ws_manager.register_admin(websocket, user_id)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        pass
    finally:
        pair_ws_manager.unregister_admin(websocket)


class DeviceCreateRequest(BaseModel):
    name: str
    ip: Optional[str] = None
    bound_account_id: Optional[str] = None
    proxy_config: Optional[dict[str, Any]] = None


class DeviceUpdateRequest(BaseModel):
    name: Optional[str] = None
    ip: Optional[str] = None
    status: Optional[str] = None
    bound_account_id: Optional[str] = None
    proxy_config: Optional[dict[str, Any]] = None


def _device_to_dict(dev: Device) -> dict:
    return {
        "id": dev.id,
        "name": dev.name,
        "ip": dev.ip,
        "status": dev.status,
        "os_version": dev.os_version,
        "app_version": dev.app_version,
        "screen_resolution": dev.screen_resolution,
        "sdk_version": dev.sdk_version,
        "total_memory": dev.total_memory,
        "manufacturer": dev.manufacturer,
        "product": dev.product,
        "device_model": dev.device_model,
        "hardware": dev.hardware,
        "display": dev.display,
        "bound_account_id": dev.bound_account_id,
        "proxy_config": dev.proxy_config,
        "last_seen_at": str(dev.last_seen_at) if dev.last_seen_at else None,
        "created_at": str(dev.created_at) if dev.created_at else None,
        "updated_at": str(dev.updated_at) if dev.updated_at else None,
    }


@router.post("")
async def create_device(
    request: DeviceCreateRequest,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    user_id, _ = user
    # Validate bound_account_id references an existing account
    if request.bound_account_id:
        from app.db_models import Account
        if not db.query(Account).filter(Account.id == request.bound_account_id).first():
            raise HTTPException(status_code=404, detail="Account not found")

    dev = Device(
        name=request.name,
        ip=request.ip,
        bound_account_id=request.bound_account_id,
        proxy_config=request.proxy_config,
        user_id=user_id,
    )
    db.add(dev)
    db.commit()
    db.refresh(dev)
    await pair_ws_manager.broadcast_to_admins({"event": "devices_changed"})
    return _device_to_dict(dev)


@router.get("")
def list_devices(
    skip: int = 0,
    limit: int = 50,
    bound_account_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    query = db.query(Device)
    if bound_account_id is not None:
        query = query.filter(Device.bound_account_id == bound_account_id)
    user_id, role = user
    if role != "admin":
        query = query.filter(Device.user_id == user_id)
    total = query.count()
    devices = query.order_by(Device.created_at.desc()).offset(skip).limit(limit).all()
    return {"devices": [_device_to_dict(d) for d in devices], "total": total}


# --- Pair request management (admin-facing) ---
# MUST be defined BEFORE /{device_id} routes to avoid path conflicts


@router.get("/pair-requests")
def list_pair_requests(
    status: str = Query("pending"),
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """List device pairing requests, filtered by status."""
    query = db.query(DevicePairRequest)
    if status != "all":
        query = query.filter(DevicePairRequest.status == status)
    requests = query.order_by(DevicePairRequest.created_at.desc()).all()
    return {
        "requests": [
            {
                "id": r.id,
                "device_id": r.device_id,
                "device_name": r.device_name,
                "os_version": r.os_version,
                "app_version": r.app_version,
                "screen_resolution": r.screen_resolution,
                "sdk_version": r.sdk_version,
                "total_memory": r.total_memory,
                "manufacturer": r.manufacturer,
                "product": r.product,
                "device_model": r.device_model,
                "hardware": r.hardware,
                "display": r.display,
                "status": r.status,
                "created_at": str(r.created_at) if r.created_at else None,
            }
            for r in requests
        ],
        "total": len(requests),
    }


@router.post("/pair-requests/{request_id}/approve")
async def approve_pair_request(
    request_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """Approve a pairing request — generates per-device secret and creates Device record."""
    import uuid
    from app.config import DEVICE_CONFIG, ANTI_DETECT_CONFIG, ANTI_DETECT_CONFIG_VERSION, get_ai_config
    user_id, _ = user

    pair_req = db.query(DevicePairRequest).filter(DevicePairRequest.id == request_id).first()
    if not pair_req:
        raise HTTPException(status_code=404, detail="Pair request not found")
    if pair_req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request already {pair_req.status}")

    # Generate per-device secret
    device_secret = uuid.uuid4().hex

    # Create or update Device record
    device = db.query(Device).filter(Device.id == pair_req.device_id).first()
    if device:
        if not device.user_id:
            device.user_id = user_id
        device.device_secret = device_secret
        device.name = pair_req.device_name
        device.os_version = pair_req.os_version or device.os_version
        device.app_version = pair_req.app_version or device.app_version
        device.screen_resolution = pair_req.screen_resolution or device.screen_resolution
        device.sdk_version = pair_req.sdk_version or device.sdk_version
        device.total_memory = pair_req.total_memory or device.total_memory
        device.manufacturer = pair_req.manufacturer or device.manufacturer
        device.product = pair_req.product or device.product
        device.device_model = pair_req.device_model or device.device_model
        device.hardware = pair_req.hardware or device.hardware
        device.display = pair_req.display or device.display
    else:
        device = Device(
            id=pair_req.device_id,
            name=pair_req.device_name,
            os_version=pair_req.os_version,
            app_version=pair_req.app_version,
            screen_resolution=pair_req.screen_resolution,
            sdk_version=pair_req.sdk_version,
            total_memory=pair_req.total_memory,
            manufacturer=pair_req.manufacturer,
            product=pair_req.product,
            device_model=pair_req.device_model,
            hardware=pair_req.hardware,
            display=pair_req.display,
            device_secret=device_secret,
            user_id=user_id,
            status="offline",
        )
        db.add(device)

    # Update pair request
    pair_req.status = "approved"
    pair_req.device_secret = device_secret

    db.commit()

    # Push result to device via WebSocket (if connected)
    config = {
        **DEVICE_CONFIG,
        "anti_detect_config": ANTI_DETECT_CONFIG,
        "anti_detect_config_version": ANTI_DETECT_CONFIG_VERSION,
    }
    ai_cfg = get_ai_config(db)
    if ai_cfg:
        config["ai_config"] = ai_cfg
    await pair_ws_manager.notify(pair_req.pairing_token, {
        "status": "approved",
        "secret": device_secret,
        "config": config,
    })

    # Broadcast to admin clients
    await pair_ws_manager.broadcast_to_admins({
        "event": "pair_approved",
        "request_id": request_id,
        "device_id": pair_req.device_id,
    })

    return {"status": "approved", "device_id": pair_req.device_id}


@router.post("/pair-requests/{request_id}/reject")
async def reject_pair_request(
    request_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """Reject a pairing request."""
    pair_req = db.query(DevicePairRequest).filter(DevicePairRequest.id == request_id).first()
    if not pair_req:
        raise HTTPException(status_code=404, detail="Pair request not found")
    if pair_req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request already {pair_req.status}")

    pair_req.status = "rejected"
    db.commit()

    # Push result to device via WebSocket (if connected)
    await pair_ws_manager.notify(pair_req.pairing_token, {
        "status": "rejected",
    })

    # Broadcast to admin clients
    await pair_ws_manager.broadcast_to_admins({
        "event": "pair_rejected",
        "request_id": request_id,
        "device_id": pair_req.device_id,
    })

    return {"status": "rejected"}


@router.get("/{device_id}")
def get_device(
    device_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    query = db.query(Device).filter(Device.id == device_id)
    if role != "admin":
        query = query.filter(Device.user_id == user_id)
    dev = query.first()
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")
    return _device_to_dict(dev)


@router.put("/{device_id}")
async def update_device(
    device_id: str,
    request: DeviceUpdateRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    query = db.query(Device).filter(Device.id == device_id)
    if role != "admin":
        query = query.filter(Device.user_id == user_id)
    dev = query.first()
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")

    config_changed = False
    proxy_changed = False

    if request.name is not None:
        dev.name = request.name
    if request.ip is not None:
        dev.ip = request.ip
    if request.status is not None:
        dev.status = request.status
    if request.bound_account_id is not None:
        if request.bound_account_id:
            from app.db_models import Account
            if not db.query(Account).filter(Account.id == request.bound_account_id).first():
                raise HTTPException(status_code=404, detail="Account not found")
        dev.bound_account_id = request.bound_account_id
    if request.proxy_config is not None:
        dev.proxy_config = request.proxy_config
        proxy_changed = True

    db.commit()
    db.refresh(dev)

    # Push config/proxy changes to device via WS
    if proxy_changed:
        await pair_ws_manager.send_to_device(device_id, {
            "event": "config_updated",
            "proxy": dev.proxy_config,
        })

    await pair_ws_manager.broadcast_to_admins({"event": "devices_changed"})
    return _device_to_dict(dev)


@router.post("/{device_id}/disconnect")
async def disconnect_device(
    device_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """Force-disconnect a device by closing its WebSocket connection.

    The device will detect the disconnect, attempt to reconnect, and
    the server will mark it offline in the database.
    """
    user_id, role = user
    query = db.query(Device).filter(Device.id == device_id)
    if role != "admin":
        query = query.filter(Device.user_id == user_id)
    dev = query.first()
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")

    closed = await pair_ws_manager.disconnect_device(device_id)
    if not closed:
        return {"status": "not_connected", "device_id": device_id, "detail": "设备当前无活跃连接"}

    dev.status = "offline"
    db.commit()

    # Broadcast status change to admins
    await pair_ws_manager.broadcast_to_admins({
        "event": "device_status_changed",
        "device_id": device_id,
        "status": "offline",
    })

    return {"status": "disconnected", "device_id": device_id}


@router.delete("/{device_id}")
async def delete_device(
    device_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    from app.db_models import Task, DevicePairRequest

    user_id, role = user
    query = db.query(Device).filter(Device.id == device_id)
    if role != "admin":
        query = query.filter(Device.user_id == user_id)
    dev = query.first()
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")

    # 1. 通知设备：你已被移除
    await pair_ws_manager.send_to_device(device_id, {
        "event": "device_removed",
    })
    # 2. 关闭设备 WS 连接
    await pair_ws_manager.disconnect_device(device_id)

    # 3. 解绑该设备上的待执行任务（放回队列等待其他设备领取）
    db.query(Task).filter(
        Task.device_id == device_id,
        Task.status.in_(["pending", "running"]),
    ).update({"device_id": None, "status": "pending", "started_at": None}, synchronize_session=False)

    # 4. 删除配对请求记录
    db.query(DevicePairRequest).filter(DevicePairRequest.device_id == device_id).delete()

    # 5. 删除设备
    db.delete(dev)
    db.commit()

    # 6. 通知前端
    await pair_ws_manager.broadcast_to_admins({
        "event": "device_status_changed",
        "device_id": device_id,
        "status": "deleted",
    })

    return {"deleted": True, "id": device_id}
```

## app/routers/director.py

```python
"""导演工坊 API — 分镜编排 + 模型路由 + 音频策略."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import verify_admin_token

router = APIRouter(prefix="/api/director", tags=["director"])


class DirectorScene(BaseModel):
    narration: str
    image_prompt: str
    shot_type: str = "medium"
    camera_angle: str = "eye_level"
    camera_movement: str = "static"
    composition: str = "rule_of_thirds"
    color_grade: str = "natural"
    lighting_mood: str = "natural"
    voice_id: Optional[str] = None
    reference_urls: Optional[list[str]] = None
    audio_mode: str = "tts"
    duration: float = 5.0


class DirectorPlanRequest(BaseModel):
    series_id: str
    episode_id: str
    scenes: list[DirectorScene]
    bgm_path: Optional[str] = None
    bgm_volume: float = 0.3


@router.post("/plan")
async def build_plan(body: DirectorPlanRequest,
                     user = Depends(verify_admin_token)):
    """
    构建导演计划 (分镜表).
    自动为每帧选择最优模型路由.
    """
    frames = []
    for i, scene in enumerate(body.scenes):
        frames.append({
            "index": i,
            "narration": scene.narration,
            "image_prompt": scene.image_prompt,
            "shot_type": scene.shot_type,
            "camera_angle": scene.camera_angle,
            "camera_movement": scene.camera_movement,
            "composition": scene.composition,
            "color_grade": scene.color_grade,
            "lighting_mood": scene.lighting_mood,
            "voice_id": scene.voice_id,
            "reference_urls": scene.reference_urls,
            "audio_mode": scene.audio_mode,
            "duration": scene.duration,
        })

    total_duration = sum(f["duration"] for f in frames)
    return {
        "ok": True,
        "plan": {
            "series_id": body.series_id,
            "episode_id": body.episode_id,
            "frames": frames,
            "frame_count": len(frames),
            "total_duration": total_duration,
            "bgm_path": body.bgm_path,
            "bgm_volume": body.bgm_volume,
        }
    }
```

## app/routers/dm_sequences.py

```python
"""DM 私信序列模板 CRUD API."""
import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_admin_token, require_role, verify_device_secret
from app.db_models import DMSequence

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dm-sequences", tags=["dm-sequences"])


class SequenceMessage(BaseModel):
    order: int
    content: str = Field(..., min_length=1, max_length=500)
    delay_ms: int = Field(default=0, ge=0, le=60000)


class SequenceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    messages: list[SequenceMessage] = Field(..., min_length=1)
    industry: Optional[str] = None


class SequenceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    messages: Optional[list[SequenceMessage]] = Field(default=None, min_length=1)
    industry: Optional[str] = None
    variants: Optional[list] = None


class DMSequenceGenerateRequest(BaseModel):
    industry: str = Field(default="general", description="行业key: health/beauty/education/travel/secondhand/general")
    description: str = Field(..., min_length=5, max_length=500, description="大白话描述")
    link_url: str = Field(..., min_length=5, max_length=500, description="消息2的短链URL")


class VariantsGenerateRequest(BaseModel):
    count: int = Field(default=3, ge=1, le=10, description="生成变体套数")


def _to_dict(s: DMSequence) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "messages": s.messages,
        "message_count": len(s.messages),
        "industry": s.industry or "",
        "variants_count": len(s.variants) if s.variants else 0,
        "variants": s.variants,
        "created_at": str(s.created_at) if s.created_at else None,
        "updated_at": str(s.updated_at) if s.updated_at else None,
    }


def _to_device_dict(s: DMSequence) -> dict:
    """Device-facing: id + messages + variants for poll/sync."""
    return {"id": s.id, "messages": s.messages, "variants": s.variants}


@router.get("")
def list_sequences(
    industry: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: tuple = Depends(verify_admin_token),
):
    user_id, _ = user
    query = db.query(DMSequence).filter(
        (DMSequence.user_id == user_id) | (DMSequence.user_id == None)
    )
    if industry:
        query = query.filter(DMSequence.industry == industry)
    sequences = query.order_by(DMSequence.updated_at.desc()).all()
    return {"sequences": [_to_dict(s) for s in sequences]}


@router.post("")
def create_sequence(
    body: SequenceCreate,
    db: Session = Depends(get_db),
    user: tuple = Depends(require_role("admin")),
):
    # Auto-renumber: sort by order, assign 1,2,3...
    sorted_msgs = sorted(
        [{"order": i + 1, "content": m.content, "delay_ms": m.delay_ms}
         for i, m in enumerate(sorted(body.messages, key=lambda x: x.order))],
        key=lambda x: x["order"],
    )
    user_id, _ = user
    seq = DMSequence(
        name=body.name,
        messages=sorted_msgs,
        industry=body.industry or None,
        user_id=user_id,
    )
    db.add(seq)
    db.commit()
    db.refresh(seq)
    return _to_dict(seq)


@router.get("/{sequence_id}")
def get_sequence(
    sequence_id: str,
    db: Session = Depends(get_db),
    user: tuple = Depends(verify_admin_token),
):
    user_id, _ = user
    seq = db.query(DMSequence).filter(
        DMSequence.id == sequence_id,
        (DMSequence.user_id == user_id) | (DMSequence.user_id == None),
    ).first()
    if not seq:
        raise HTTPException(status_code=404, detail="序列模板不存在")
    return _to_dict(seq)


@router.put("/{sequence_id}")
def update_sequence(
    sequence_id: str,
    body: SequenceUpdate,
    db: Session = Depends(get_db),
    user: tuple = Depends(require_role("admin")),
):
    user_id, _ = user
    seq = db.query(DMSequence).filter(DMSequence.id == sequence_id).first()
    if not seq:
        raise HTTPException(status_code=404, detail="序列模板不存在")
    if seq.user_id and seq.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权修改其他用户的序列模板")

    if body.name is not None:
        seq.name = body.name
    if body.messages is not None:
        new_messages = [
            {"order": i + 1, "content": m.content, "delay_ms": m.delay_ms}
            for i, m in enumerate(sorted(body.messages, key=lambda x: x.order))
        ]
        # 只有消息内容/延迟实际变化时才清除旧变体
        if new_messages != seq.messages:
            seq.variants = None
        seq.messages = new_messages
    if body.industry is not None:
        old_industry = seq.industry
        seq.industry = body.industry or None
        if body.industry != (old_industry or None):
            seq.variants = None  # 行业变了，合规约束不同，旧变体失效
    if body.variants is not None:
        seq.variants = body.variants

    db.commit()
    db.refresh(seq)
    return _to_dict(seq)


@router.delete("/{sequence_id}")
def delete_sequence(
    sequence_id: str,
    db: Session = Depends(get_db),
    user: tuple = Depends(require_role("admin")),
):
    user_id, _ = user
    seq = db.query(DMSequence).filter(DMSequence.id == sequence_id).first()
    if not seq:
        raise HTTPException(status_code=404, detail="序列模板不存在")
    if seq.user_id and seq.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权删除其他用户的序列模板")
    db.delete(seq)
    db.commit()
    return {"deleted": True, "id": sequence_id}


@router.post("/generate")
async def generate_dm_sequence(
    body: DMSequenceGenerateRequest,
    db: Session = Depends(get_db),
    current_user: tuple = Depends(require_role("admin")),
):
    """AI生成完整3条消息序列 (SSE流式)."""
    from app.services.industry_profile_service import load_profile
    from app.services.ai_generator import ai_generator as gen

    profile = load_profile(body.industry)

    system_prompt = profile["system_prompt"]
    sensitive_words_str = "、".join(profile["sensitive_words"])
    extreme_words_str = "、".join(profile["extreme_words"])
    style_guide = profile["style_guide"]

    user_prompt = (
        f"你是一个专业的私信话术生成助手。\n\n"
        f"## 行业约束\n"
        f"- 行业: {profile['label']}\n"
        f"- 话术风格: {style_guide}\n"
        f"- 绝对禁用词(包含任一词即不合格): {sensitive_words_str}\n"
        f"- 极限词禁用: {extreme_words_str}\n\n"
        f"## 平台规则\n"
        f"{system_prompt}\n\n"
        f"## 任务\n"
        f"根据用户描述生成3条私信消息序列:\n"
        f"- 消息1: 建立信任的钩子，吸引用户注意，让用户愿意继续看\n"
        f"- 消息2: 用户提供的链接地址（原样保留，不修改）\n"
        f"- 消息3: 驱动点击的收口CTA，引导用户点击消息2的链接\n\n"
        f"要求:\n"
        f"1. 每条消息50-150字，语气自然像真人聊天\n"
        f"2. 消息1和消息3需要针对私信场景设计，不能像广告文案\n"
        f"3. 不出现任何禁用词或极限词\n"
        f'4. 返回纯JSON数组: [{{"order":1,"content":"...","delay_ms":2000}},'
        f'{{"order":2,"content":"{body.link_url}","delay_ms":1500}},'
        f'{{"order":3,"content":"...","delay_ms":2000}}]\n'
        f"5. delay_ms: 消息1用2000, 消息2用1500, 消息3用2000\n\n"
        f"用户描述: {body.description}"
    )

    async def event_stream():
        label = profile.get("label", body.industry)
        yield f"data: {json.dumps({'type': 'status', 'text': f'AI 正在生成 {label} 行业序列...'})}\n\n"

        raw_chunks = []
        try:
            async for chunk in gen.generate_custom_stream(
                db, system_prompt, user_prompt, max_tokens=2048
            ):
                raw_chunks.append(chunk)
                yield f"data: {json.dumps({'type': 'token', 'text': chunk})}\n\n"

            full = "".join(raw_chunks).strip()

            if full.startswith("```"):
                lines = full.split("\n")
                full = "\n".join(lines[1:])
                if full.endswith("```"):
                    full = full[: full.rfind("```")].strip()

            match = re.search(r"\[[\s\S]*\]", full)
            if not match:
                yield f"data: {json.dumps({'type': 'error', 'message': 'AI 返回格式异常，请重试'})}\n\n"
                return

            messages = json.loads(match.group())

            for msg in messages:
                content_text = msg.get("content", "")
                for word in profile["sensitive_words"]:
                    if word in content_text:
                        yield f"data: {json.dumps({'type': 'error', 'message': f'生成内容含敏感词: {word}'})}\n\n"
                        return
                for word in profile["extreme_words"]:
                    if word in content_text:
                        yield f"data: {json.dumps({'type': 'error', 'message': f'生成内容含极限词: {word}'})}\n\n"
                        return

            yield f"data: {json.dumps({'type': 'done', 'messages': messages})}\n\n"

        except json.JSONDecodeError:
            yield f"data: {json.dumps({'type': 'error', 'message': 'JSON 解析失败，请重试'})}\n\n"
        except Exception as e:
            logger.error("DM sequence generation failed: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': f'生成失败: {str(e)[:200]}'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{seq_id}/variants")
async def generate_variants(
    seq_id: str,
    body: VariantsGenerateRequest,
    db: Session = Depends(get_db),
    current_user: tuple = Depends(require_role("admin")),
):
    """基于已有messages生成N套变体."""
    from app.services.industry_profile_service import load_profile
    from app.services.ai_generator import ai_generator as gen

    seq = db.query(DMSequence).filter(DMSequence.id == seq_id).first()
    if not seq:
        raise HTTPException(404, "DM序列不存在")

    if not seq.messages or len(seq.messages) < 3:
        raise HTTPException(400, "DM序列至少需要3条消息才能生成变体")

    industry = getattr(seq, "industry", "general") or "general"
    profile = load_profile(industry)

    original_msg1 = (
        seq.messages[0].get("content", "")
        if isinstance(seq.messages[0], dict)
        else ""
    )
    original_msg2 = seq.messages[1]
    original_msg3 = (
        seq.messages[2].get("content", "")
        if len(seq.messages) > 2 and isinstance(seq.messages[2], dict)
        else ""
    )

    variant_system_prompt = (
        f"你是私信话术改写助手。遵守:\n"
        f"1. 保持原意不变\n"
        f"2. {profile['style_guide']}\n"
        f"3. 不使用禁用词和极限词\n"
        f"4. 语气自然如真人"
    )

    variants = []

    for vi in range(body.count):
        variant_prompt = (
            f"请对以下私信话术做同义改写，保持核心意思不变，换用不同的表达方式。\n\n"
            f"## 约束\n"
            f"- 禁用词: {'、'.join(profile['sensitive_words'][:20])}\n"
            f"- {profile['style_guide']}\n"
            f"- 每条50-150字\n"
            f"- 不要改变原意和核心信息\n"
            f"- 语气自然像真人\n\n"
            f"原始消息1(钩子): {original_msg1}\n"
            f"原始消息3(收口): {original_msg3}\n\n"
            f'返回JSON: {{"msg1": "改写后的消息1", "msg3": "改写后的消息3"}}'
        )

        try:
            response = await gen.generate_custom(
                db, variant_system_prompt, variant_prompt, max_tokens=1024
            )

            clean = response.strip()
            if clean.startswith("```"):
                lines = clean.split("\n")
                clean = "\n".join(lines[1:])
                if clean.endswith("```"):
                    clean = clean[: clean.rfind("```")].strip()

            match = re.search(r"\{[\s\S]*\}", clean)
            if match:
                result = json.loads(match.group())
            else:
                result = json.loads(clean)

            rewritten_msg1 = result.get("msg1", original_msg1)
            rewritten_msg3 = result.get("msg3", original_msg3)

            ok = True
            for word in profile["sensitive_words"]:
                if word in rewritten_msg1 or word in rewritten_msg3:
                    ok = False
                    break
            if ok:
                for word in profile["extreme_words"]:
                    if word in rewritten_msg1 or word in rewritten_msg3:
                        ok = False
                        break
            if not ok:
                continue

            variant = [
                {
                    "order": 1,
                    "content": rewritten_msg1,
                    "delay_ms": seq.messages[0].get("delay_ms", 2000),
                },
                original_msg2,
                {
                    "order": 3,
                    "content": rewritten_msg3,
                    "delay_ms": (
                        seq.messages[2].get("delay_ms", 2000)
                        if len(seq.messages) > 2
                        else 2000
                    ),
                },
            ]
            variants.append(variant)
        except Exception as e:
            logger.warning(
                "Variant generation attempt %d failed: %s", vi + 1, e
            )
            continue

    if not variants:
        raise HTTPException(500, "无法生成合规变体，请调整原始话术后重试")

    seq.variants = (seq.variants or []) + variants
    db.commit()

    total = len(seq.variants)
    return {"ok": True, "variants_count": len(variants), "total_variants": total, "variants": seq.variants}


@router.get("/device/sync")
def device_sync(
    db: Session = Depends(get_db),
    device_id: Optional[str] = Depends(verify_device_secret),
):
    """设备端同步 DM 序列模板 — 按设备所属用户过滤，NULL=共享模板"""
    from app.db_models import Device
    query = db.query(DMSequence)
    if device_id:
        device = db.query(Device).filter(Device.id == device_id).first()
        device_user_id = device.user_id if device else None
        query = query.filter(
            (DMSequence.user_id == device_user_id) | (DMSequence.user_id == None)
        )
    sequences = query.all()
    return {"dm_sequences": [_to_device_dict(s) for s in sequences]}
```

## app/routers/pipeline.py

```python
"""流水线编排 API — 模型感知 dispatch + L4 同步轮询 + Seedance 路由."""
import asyncio
import logging
import traceback
from datetime import datetime, timezone, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.deps import verify_admin_token, require_role
from app.db_models import PipelineRun, AIModel
from app.services.crypto import decrypt
from app.services.pixelle_client import _pixelle_request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

BJT = timezone(timedelta(hours=8))

# ============================================================
# Layer definitions
# ============================================================

LAYER_DEFS = [
    {"index": 0, "label": "assets",          "model_key": "imageModel", "desc": "图像生成"},
    {"index": 1, "label": "story_narration", "model_key": "scriptLLM",  "desc": "故事旁白"},
    {"index": 2, "label": "story_title",     "model_key": "scriptLLM",  "desc": "故事标题"},
    {"index": 3, "label": "director",        "model_key": "scriptLLM",  "desc": "图像提示词"},
    {"index": 4, "label": "render",          "model_key": "videoModel", "desc": "视频渲染"},
    {"index": 5, "label": "postproduction",  "model_key": "ttsModel",   "desc": "后处理合成"},
]

FORWARD_KEYS = {
    0: ["image_urls", "images"],
    1: ["narration", "content"],
    2: ["title", "content"],
    3: ["image_prompt"],
}

VIDEO_POLL_INTERVAL = 10
VIDEO_POLL_TIMEOUTS = {
    "seedance": 180, "kling": 120, "wan": 120, "pixelle": 120, "default": 120,
}

# ============================================================
# Pydantic schemas
# ============================================================

class PipelineStartRequest(BaseModel):
    series_id: str
    episode_id: str | None = None
    mode: str = "step_by_step"
    model_ids: dict | None = None
    director_plan: dict | None = None

# ============================================================
# Model lookup
# ============================================================

def _get_model_config(db: Session, model_id: str | None) -> dict:
    if not model_id:
        return {}
    m = db.query(AIModel).filter(AIModel.id == model_id).first()
    if not m:
        return {}
    ak = ""; asc = ""
    if m.api_key:
        try: ak = decrypt(m.api_key)
        except Exception: logger.warning("decrypt api_key failed for model %s", m.id)
    if m.api_secret:
        try: asc = decrypt(m.api_secret)
        except Exception: logger.warning("decrypt api_secret failed for model %s", m.id)
    return {
        "id": m.id, "name": m.name, "model_type": m.model_type,
        "provider": m.provider, "base_url": m.base_url or "",
        "api_key": ak, "api_secret": asc,
        "model_name": m.model_name or "",
        "config_json": m.config_json or {},
    }


def _llm_chat_completion(model: dict, messages: list[dict], temperature: float = 0.7, max_tokens: int = 4096) -> str:
    cfg = model.get("config_json", {})
    resp = httpx.post(
        f"{model['base_url'].rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {model['api_key']}"},
        json={
            "model": model["model_name"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=httpx.Timeout(120, connect=10),
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


# ============================================================
# Layer functions
# ============================================================

async def _layer_image_generate(run: PipelineRun, model: dict, common: dict, db: Session) -> dict:
    """L0: Per-provider image generation routing."""
    provider = model.get("provider", "")
    base = model.get("base_url", "")

    if provider == "openai":
        cfg = model.get("config_json", {})
        resp = httpx.post(
            f"{base.rstrip('/')}/images/generations",
            headers={"Authorization": f"Bearer {model['api_key']}"},
            json={
                "model": model.get("model_name", "dall-e-3"),
                "prompt": common.get("image_prompt", common.get("title", "")),
                "n": 1, "size": cfg.get("default_size", "1024x1024"),
                "quality": cfg.get("default_quality", "hd"),
            },
            timeout=httpx.Timeout(120, connect=10),
        )
        resp.raise_for_status()
        data = resp.json()
        return {"provider": "openai", "images": [img["url"] for img in data.get("data", [])]}

    if provider == "seedance":
        cfg = model.get("config_json", {})
        resp = httpx.post(
            f"{base.rstrip('/')}/images/generations",
            headers={"Authorization": f"Bearer {model['api_key']}"},
            json={
                "model": model.get("model_name", "seedance-image"),
                "prompt": common.get("image_prompt", common.get("title", "")),
                "size": cfg.get("default_size", "1024x1024"),
            },
            timeout=httpx.Timeout(120, connect=10),
        )
        resp.raise_for_status()
        data = resp.json()
        return {"provider": "seedance", "images": [img["url"] for img in data.get("data", [])]}

    # Fallback: Pixelle-Video
    result = await _pixelle_request("POST", "/api/image/generate", db, json=common)
    return {"provider": "pixelle", **result}


async def _layer_narration(run: PipelineRun, model: dict, common: dict, db: Session) -> dict:
    """L1: LLM narration or Pixelle-Video fallback."""
    if model.get("api_key") and model.get("base_url"):
        cfg = model.get("config_json", {})
        messages = [
            {"role": "system", "content": "你是一个短视频编剧，为视频画面生成简洁生动的旁白文案。只输出旁白文案。"},
            {"role": "user", "content": f"为以下内容生成旁白：{common.get('title', '')} {common.get('context', '')}"},
        ]
        text = _llm_chat_completion(model, messages,
                                     temperature=cfg.get("temperature", 0.7),
                                     max_tokens=cfg.get("max_tokens", 4096))
        return {"provider": model["provider"], "narration": text}
    result = await _pixelle_request("POST", "/api/content/narration", db, json=common)
    return {"provider": "pixelle", **result}


async def _layer_title(run: PipelineRun, model: dict, common: dict, db: Session) -> dict:
    """L2: LLM title or Pixelle-Video fallback."""
    if model.get("api_key") and model.get("base_url"):
        cfg = model.get("config_json", {})
        messages = [
            {"role": "system", "content": "你是一个短视频编剧，为视频系列生成吸引人的标题。只输出标题。"},
            {"role": "user", "content": f"为以下内容生成标题：{common.get('context', common.get('title', ''))}"},
        ]
        title = _llm_chat_completion(model, messages,
                                      temperature=cfg.get("temperature", 0.8),
                                      max_tokens=min(cfg.get("max_tokens", 4096), 200))
        return {"provider": model["provider"], "title": title.strip()}
    result = await _pixelle_request("GET", "/api/content/title", db, json=common)
    return {"provider": "pixelle", **result}


async def _layer_image_prompt(run: PipelineRun, model: dict, common: dict, db: Session) -> dict:
    """L3: LLM image prompts or Pixelle-Video fallback."""
    if model.get("api_key") and model.get("base_url"):
        cfg = model.get("config_json", {})
        narration = common.get("narration", common.get("title", ""))
        messages = [
            {"role": "system", "content": "你是一个AI图像提示词专家。为给定的旁白生成高质量的图像生成提示词，描述画面构图、光线、风格。只输出提示词。"},
            {"role": "user", "content": f"旁白：{narration}"},
        ]
        prompt = _llm_chat_completion(model, messages,
                                       temperature=cfg.get("temperature", 0.7),
                                       max_tokens=min(cfg.get("max_tokens", 4096), 500))
        return {"provider": model["provider"], "image_prompt": prompt.strip()}
    result = await _pixelle_request("POST", "/api/content/image-prompt", db, json=common)
    return {"provider": "pixelle", **result}


async def _layer_video_generate(run: PipelineRun, model: dict, common: dict, db: Session) -> dict:
    """L4: Video generation with sync polling (ADR-0003) + Seedance routing (ADR-0002)."""
    provider = model.get("provider", "pixelle")
    if provider == "seedance":
        return await _video_seedance_generate(run, model, common)
    return await _video_pixelle_poll(run, common, db)


async def _video_pixelle_poll(run: PipelineRun, common: dict, db: Session) -> dict:
    """Pixelle-Video submit + poll (ADR-0003)."""
    submit = await _pixelle_request("POST", "/api/video/generate/async", db, json=common)
    task_id = submit.get("task_id") or submit.get("id", "")
    if not task_id:
        return {"provider": "pixelle", "status": "submitted", **submit}

    max_polls = VIDEO_POLL_TIMEOUTS["pixelle"]
    for attempt in range(max_polls):
        await asyncio.sleep(VIDEO_POLL_INTERVAL)
        try:
            status_resp = await _pixelle_request("GET", f"/api/video/task/{task_id}", db)
        except Exception as e:
            logger.warning("L4 poll %d/%d failed: %s", attempt + 1, max_polls, e)
            if attempt >= 2: raise RuntimeError(f"视频任务轮询连续失败: {e}")
            continue

        status_val = status_resp.get("status", "")
        layers = run.layers_json or {}
        layers["4"] = {"status": "running", "progress": status_resp.get("progress", 0),
                        "task_id": task_id, "provider": "pixelle"}
        run.layers_json = layers; db.commit()

        if status_val in ("completed", "succeeded", "done"):
            return {"provider": "pixelle", "status": "completed", "task_id": task_id, **status_resp}
        if status_val in ("failed", "error"):
            raise RuntimeError(f"视频生成失败: {status_resp.get('error', status_val)}")

    raise RuntimeError(f"视频生成超时 ({max_polls * VIDEO_POLL_INTERVAL}s)")


async def _video_seedance_generate(run: PipelineRun, model: dict, common: dict) -> dict:
    """Seedance submit + poll (ADR-0002 + ADR-0003)."""
    base_url = model.get("base_url", "https://ark.cn-beijing.volces.com/api/v3")
    model_name = model.get("model_name", "doubao-seedance-2-0-260128")
    cfg = model.get("config_json", {})

    content = [{"type": "text", "text": common.get("image_prompt", common.get("title", ""))}]
    for url in common.get("image_urls", []):
        content.append({"type": "image_url", "image_url": {"url": url}})

    payload = {
        "model": model_name,
        "content": content,
        "parameters": {
            "aspect_ratio": cfg.get("default_aspect_ratio", "9:16"),
            "duration": cfg.get("default_duration", 5),
            "resolution": cfg.get("default_resolution", "720p"),
        },
    }

    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {model['api_key']}"},
        timeout=httpx.Timeout(600, connect=10),
    ) as client:
        submit_resp = await client.post("/contents/generations/tasks", json=payload)
        submit_resp.raise_for_status()
        submit_data = submit_resp.json()
        task_id = submit_data.get("id") or submit_data.get("task_id")
        if not task_id:
            raise RuntimeError(f"Seedance submit returned no task_id: {submit_data}")

        max_polls = VIDEO_POLL_TIMEOUTS["seedance"]
        for attempt in range(max_polls):
            await asyncio.sleep(VIDEO_POLL_INTERVAL)
            try:
                poll_resp = await client.get(f"/contents/generations/tasks/{task_id}")
                poll_resp.raise_for_status()
                poll_data = poll_resp.json()
            except Exception as e:
                logger.warning("Seedance poll %d/%d failed: %s", attempt + 1, max_polls, e)
                if attempt >= 2: raise RuntimeError(f"Seedance 轮询连续失败: {e}")
                continue

            status_val = poll_data.get("status", "unknown")
            layers = run.layers_json or {}
            layers["4"] = {"status": "running", "progress": poll_data.get("progress", 0),
                            "task_id": task_id, "provider": "seedance"}
            run.layers_json = layers; db.commit()

            if status_val == "succeeded":
                videos = poll_data.get("output", {}).get("videos", [])
                video_url = videos[0].get("url", "") if videos else ""
                return {"provider": "seedance", "status": "completed", "task_id": task_id, "video_url": video_url}
            if status_val == "failed":
                err = poll_data.get("error", {}).get("message", "任务失败")
                raise RuntimeError(f"Seedance 视频生成失败: {err}")

        raise RuntimeError(f"Seedance 视频生成超时 ({max_polls * VIDEO_POLL_INTERVAL}s)")


async def _layer_postproduction(run: PipelineRun, model: dict, common: dict, db: Session) -> dict:
    """L5: Post-production compositing."""
    result = await _pixelle_request("POST", "/api/postproduction/execute", db, json=common)
    return {"provider": "pixelle", **result}


_LAYER_FNS = [
    _layer_image_generate, _layer_narration, _layer_title,
    _layer_image_prompt, _layer_video_generate, _layer_postproduction,
]

# ============================================================
# Pipeline endpoints
# ============================================================

@router.post("/start")
async def pipeline_start(
    body: PipelineStartRequest,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    existing = db.query(PipelineRun).filter(
        PipelineRun.series_id == body.series_id,
        PipelineRun.status.in_(["pending", "running"]),
    ).first()
    if existing:
        raise HTTPException(409, f"Series {body.series_id} 已有运行中的流水线 (run_id={existing.id})")

    run = PipelineRun(
        series_id=body.series_id,
        episode_id=body.episode_id,
        mode=body.mode,
        model_ids=body.model_ids or {},
        status="running",
        started_at=datetime.now(BJT),
    )
    db.add(run); db.commit(); db.refresh(run)
    run_id = run.id

    task = asyncio.create_task(_run_all_layers(run_id, body.director_plan))
    task.add_done_callback(
        lambda t: logger.error("Pipeline task failed: %s", t.exception()) if t.exception() else None
    )
    return {"ok": True, "run_id": run_id}


async def _run_all_layers(run_id: str, director_plan: dict | None = None):
    local_db = SessionLocal()
    run = None
    try:
        run = local_db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        if not run:
            return

        model_ids = run.model_ids or {}
        common = {"series_id": run.series_id, "episode_id": run.episode_id or ""}

        frames = []
        if director_plan:
            frames = director_plan.get("frames", [])
            if frames:
                common["frame_count"] = len(frames)

        # Hydrate common from already-completed layers (resume support)
        prev_layers = (run.layers_json or {}).items()
        for _li_str, _lr in prev_layers:
            _li = int(_li_str)
            if _lr.get("status") != "completed":
                continue
            _res = _lr.get("result", {}) or {}
            for key in FORWARD_KEYS.get(_li, []):
                val = _res.get(key)
                if val:
                    common[key] = val
                    if key == "images":
                        common.setdefault("image_urls", val)

        for layer_def in LAYER_DEFS:
            i = layer_def["index"]
            layers = run.layers_json or {}
            if layers.get(str(i), {}).get("status") == "completed":
                continue

            run.current_layer = i
            local_db.commit()

            model_key = layer_def["model_key"]
            model_id = model_ids.get(model_key)
            model_config = _get_model_config(local_db, model_id)

            layer_fn = _LAYER_FNS[i]

            if frames and i in (0, 3, 4):
                frame_results = []
                for fi, frame in enumerate(frames):
                    frame_common = {**common, **frame, "frame_index": fi}
                    frame_results.append(await layer_fn(run, model_config, frame_common, local_db))
                result = {"frames": frame_results}
            else:
                result = await layer_fn(run, model_config, common, local_db)
                # Forward layer output to subsequent layers via common
                for key in FORWARD_KEYS.get(i, []):
                    val = result.get(key)
                    if val:
                        common[key] = val
                        # Normalize image keys so consumers (Seedance) find them
                        if key == "images":
                            common.setdefault("image_urls", val)

            layers[str(i)] = {"status": "completed", "result": result}
            run.layers_json = layers
            local_db.commit()

        run.status = "completed"
        run.completed_at = datetime.now(BJT)
    except Exception as e:
        tb = traceback.format_exc()
        if run is not None:
            logger.error("Pipeline %s failed at layer %d: %s\n%s",
                         run_id, run.current_layer if run else -1, e, tb)
            run.status = "failed"
            run.error_log = f"{e}\n{tb}"
        else:
            logger.error("Pipeline _run_all_layers failed before run loaded: %s\n%s", e, tb)
    finally:
        local_db.commit()
        local_db.close()


@router.post("/resume/{run_id}")
async def pipeline_resume(run_id: str, db: Session = Depends(get_db),
                          _ = Depends(require_role("admin"))):
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if not run or run.status not in ("pending", "running", "paused"):
        raise HTTPException(400, "PipelineRun not resumable")
    run.status = "running"; db.commit()
    task = asyncio.create_task(_run_all_layers(run_id))
    task.add_done_callback(
        lambda t: logger.error("Pipeline resume failed: %s", t.exception()) if t.exception() else None
    )
    return {"ok": True, "run_id": run.id}


@router.get("/runs/{series_id}")
def list_runs(series_id: str, db: Session = Depends(get_db),
              _ = Depends(verify_admin_token)):
    runs = db.query(PipelineRun).filter(
        PipelineRun.series_id == series_id
    ).order_by(PipelineRun.created_at.desc()).all()
    return {"ok": True, "runs": [
        {col.name: getattr(r, col.name) for col in PipelineRun.__table__.columns}
        for r in runs
    ]}


@router.get("/runs/{series_id}/{run_id}")
def get_run(series_id: str, run_id: str, db: Session = Depends(get_db),
            _ = Depends(verify_admin_token)):
    run = db.query(PipelineRun).filter(
        PipelineRun.id == run_id, PipelineRun.series_id == series_id
    ).first()
    if not run:
        raise HTTPException(404, "PipelineRun not found")
    return {"ok": True, "run": {
        col.name: getattr(run, col.name) for col in PipelineRun.__table__.columns
    }}
```

## app/routers/pixelle.py

```python
"""Pixelle-Video proxy — admin only."""
import logging
import os
from pathlib import Path

import httpx
import yaml
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import _resolve_pixelle_config, PIXELLE_CONFIG_PATH, JWT_SECRET
from app.database import get_db
from app.deps import verify_admin_token, verify_ws_admin_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pixelle", tags=["pixelle"])


# ---- Config bridge (Pixelle-Video config.yaml read/write) ----

class PixelleConfigUpdate(BaseModel):
    updates: dict = {}


def _read_pixelle_config() -> dict:
    path = Path(PIXELLE_CONFIG_PATH)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Pixelle-Video config 文件不存在: {PIXELLE_CONFIG_PATH}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _write_pixelle_config(data: dict):
    path = Path(PIXELLE_CONFIG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def _redact_api_key(key: str) -> str:
    if not key or len(key) < 8:
        return key
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


def _redact_secrets(config: dict) -> dict:
    """Return a copy with API keys redacted for safe display."""
    result = config.copy()
    if "llm" in result and isinstance(result["llm"], dict):
        result["llm"] = {**result["llm"]}
        if result["llm"].get("api_key"):
            result["llm"]["api_key"] = _redact_api_key(result["llm"]["api_key"])
    if "comfyui" in result and isinstance(result["comfyui"], dict):
        result["comfyui"] = {**result["comfyui"]}
        if result["comfyui"].get("runninghub_api_key"):
            result["comfyui"]["runninghub_api_key"] = _redact_api_key(result["comfyui"]["runninghub_api_key"])
        if result["comfyui"].get("comfyui_api_key"):
            result["comfyui"]["comfyui_api_key"] = _redact_api_key(result["comfyui"]["comfyui_api_key"])
    return result


@router.get("/config")
async def get_pixelle_config(
    user = Depends(verify_admin_token),
):
    """Read Pixelle-Video config.yaml (API keys redacted)."""
    return _redact_secrets(_read_pixelle_config())


@router.put("/config")
async def update_pixelle_config(
    body: PixelleConfigUpdate,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """Update Pixelle-Video config.yaml with deep merge, then trigger reload."""
    current = _read_pixelle_config()

    def deep_merge(base, updates):
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    merged = deep_merge(current, body.updates)
    _write_pixelle_config(merged)

    # Trigger Pixelle-Video to reload config from disk
    cfg = _resolve_pixelle_config(db)
    reload_ok = False
    try:
        async with httpx.AsyncClient(trust_env=False,
            base_url=cfg["url"],
            timeout=httpx.Timeout(5, connect=3),
        ) as client:
            resp = await client.post("/api/admin/reload")
            reload_ok = resp.is_success
    except Exception as e:
        logger.warning("Pixelle-Video config reload failed: %s (restart Pixelle-Video to apply)", e)

    return {"ok": True, "reloaded": reload_ok, "message": "Config saved" + (" and reloaded" if reload_ok else " — restart Pixelle-Video to apply")}


# ---- Template preview images ----
# Pixelle-Video stores preview JPGs in docs/images/ which isn't exposed via its file API.
# Serve them directly from disk to avoid modifying Pixelle-Video source.

@router.get("/template-preview/{size}/{filename}")
async def template_preview_image(
    size: str,
    filename: str,
    token: str = Query(None),
    authorization: str = Header(None),
):
    """Serve template preview image. Accepts token via query param for <img> tags."""
    username = None
    if authorization and authorization.startswith("Bearer "):
        try:
            import jwt as _jwt
            payload = _jwt.decode(authorization[7:], JWT_SECRET, algorithms=["HS256"])
            username = payload["sub"]
        except Exception:
            pass
    if not username and token:
        result = verify_ws_admin_token(token)
        username = result[0] if result[0] else None
    if not username:
        raise HTTPException(status_code=401, detail="请先登录")

    preview_dir = Path(PIXELLE_CONFIG_PATH).parent / "docs" / "images" / size
    # Try exact path first, then try common extensions
    filepath = preview_dir / filename
    if not filepath.exists():
        for ext in (".jpg", ".jpeg", ".png"):
            candidate = preview_dir / (Path(filename).stem + ext)
            if candidate.exists():
                filepath = candidate
                break
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"Preview image not found: {size}/{filename}")
    suffix = filepath.suffix.lower()
    media = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}.get(suffix, "image/jpeg")
    return FileResponse(str(filepath), media_type=media)


# ---- Test connection ----

@router.get("/test-connection")
async def test_connection(
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """Test connectivity to Pixelle-Video."""
    cfg = _resolve_pixelle_config(db)
    try:
        async with httpx.AsyncClient(trust_env=False,
            base_url=cfg["url"],
            timeout=httpx.Timeout(10, connect=5),
        ) as client:
            resp = await client.get("/openapi.json")
            data = resp.json()
            return {"ok": True, "version": data.get("info", {}).get("version", "unknown")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---- 透明代理 (admin) ----
# 前端 VideoStudio 页面通过此代理直接调用 Pixelle-Video 的所有 API，
# 避免浏览器 CORS 问题。代理根据 SystemSetting 中的 pixelle_video_url 转发。

PROXY_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"]

# Headers to NEVER forward to downstream Pixelle-Video
_STRIP_REQUEST_HEADERS = {
    "host", "connection", "content-length", "transfer-encoding",
    "authorization", "cookie", "x-forwarded-for", "x-forwarded-proto",
    "x-real-ip", "origin", "referer",
}

# Headers to strip from Pixelle-Video response (let FastAPI recalculate)
_STRIP_RESPONSE_HEADERS = {
    "transfer-encoding", "content-encoding", "content-length",
}

proxy_router = APIRouter(prefix="/api/pixelle-proxy", tags=["pixelle-proxy"])

# Module-level cached httpx client — reused across requests for connection pooling
_proxy_client = None
_proxy_client_url = None


def _get_proxy_client(db=None) -> httpx.AsyncClient:
    global _proxy_client, _proxy_client_url
    cfg = _resolve_pixelle_config(db)
    url = cfg["url"]
    if _proxy_client is None or _proxy_client_url != url:
        if _proxy_client:
            try:
                import asyncio
                asyncio.ensure_future(_proxy_client.aclose())
            except Exception:
                pass
        _proxy_client = httpx.AsyncClient(trust_env=False,
            base_url=url,
            timeout=httpx.Timeout(cfg["timeout"], connect=10),
        )
        _proxy_client_url = url
    return _proxy_client


async def _do_proxy(request: Request, db: Session, path: str = "") -> Response:
    """Core proxy logic — forward request to Pixelle-Video and return response."""
    client = _get_proxy_client(db)

    # Build target URL (path already handled by base_url, so strip leading /)
    target_path = path.lstrip("/")
    if request.query_params:
        target_path += "?" + str(request.query_params)

    # Forward only safe headers
    forward_headers = {}
    for key, val in request.headers.items():
        if key.lower() not in _STRIP_REQUEST_HEADERS:
            forward_headers[key] = val

    body = await request.body()

    try:
        resp = await client.request(
            method=request.method,
            url=target_path,
            headers=forward_headers,
            content=body or None,
        )

        proxy_headers = {}
        for key, val in resp.headers.items():
            if key.lower() not in _STRIP_RESPONSE_HEADERS:
                proxy_headers[key] = val

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=proxy_headers,
            media_type=resp.headers.get("content-type"),
        )
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Pixelle-Video 服务不可达")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Pixelle-Video 响应超时")
    except httpx.RequestError as e:
        logger.warning("Proxy request to Pixelle-Video failed: %s", e)
        raise HTTPException(status_code=502, detail="Pixelle-Video 代理请求失败")
    except Exception:
        logger.exception("Unexpected proxy error")
        raise HTTPException(status_code=502, detail="代理服务异常")


@proxy_router.api_route("/{path:path}", methods=PROXY_METHODS)
async def proxy_to_pixelle(
    path: str,
    request: Request,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    return await _do_proxy(request, db, path)


@proxy_router.api_route("/", methods=PROXY_METHODS)
async def proxy_root_to_pixelle(
    request: Request,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    return await _do_proxy(request, db, "")
```

## app/routers/prompt_templates.py

```python
"""Prompt template management CRUD API — admin only."""
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from typing import Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_admin_token, require_role
from app.services.prompt_template_service import prompt_template_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prompt-templates", tags=["prompt-templates"])


class TemplateGenerateRequest(BaseModel):
    description: str
    industry: str = "health"


class TemplateCreateRequest(BaseModel):
    name: str
    industry: str = "health"
    description: str = ""
    content: dict


class TemplateUpdateRequest(BaseModel):
    content: Optional[dict] = None
    industry: Optional[str] = None
    description: Optional[str] = None


class TemplateToggleRequest(BaseModel):
    enabled: bool


TEMPLATE_SCHEMA_DESC = """提示词模板 JSON 结构：
{
  "identity": { "role": "角色描述", "constraints": ["约束1", "约束2"] },
  "disabledWords": "禁用词列表，用 / 分隔",
  "semanticGuide": {
    "mission": "语义分析的核心问题",
    "highValueSignals": ["高价值信号1：描述 → 含义"],
    "lowValueSignals": ["低价值信号1：描述 → 含义"],
    "keyExamples": ["示例: 具体评论 → 信号分析 → 结论"]
  },
  "analysis": {
    "intents": ["intent_type: 描述和示例"],
    "sentiments": ["sentiment_type: 描述"],
    "scoringRules": ["评分规则"],
    "replyRules": ["回复生成规则"],
    "replyExample": { "good": "好的回复示例（纯回复正文，不含原文引用）", "bad": "不好的回复示例（纯回复正文，不含原文引用）" },
    "tiers": { "tier_name": "对应语气描述" }
  },
  "videoComment": {
    "context": "场景上下文",
    "goal": "评论的目标",
    "rules": ["规则1", "规则2"]
  },
  "dmOpener": {
    "context": "破冰上下文",
    "identity": ["身份设定"],
    "goal": "破冰目标",
    "style": ["风格规则"],
    "tierTones": { "tier_name": "语气描述" }
  },
  "dmStages": {
    "qualifying": { "name": "了解需求", "goal": "阶段目标", "style": "风格", "maxTokens": 150 },
    "nurturing": { "name": "信任培育", "goal": "...", "style": "...", "maxTokens": 200 },
    "converting": { "name": "转化引导", "goal": "...", "style": "...", "maxTokens": 150 },
    "follow_up": { "name": "唤回", "goal": "...", "style": "...", "maxTokens": 120 }
  },
  "localFilter": { "exclude": ["排除关键词"], "include": ["包含关键词"] }
}"""

TEMPLATE_GEN_SYSTEM = """你是一个 AI 提示词模板生成专家。根据用户描述，生成完整的提示词模板 JSON。

## 输出要求
1. 严格按指定的 JSON 结构输出
2. 所有字段必填，数组至少包含 3 个元素
3. 提示词内容具体、可执行，不要泛泛而谈
4. highValueSignals 要覆盖常见的需求表达模式
5. keyExamples 要给出正反面对比例子
6. scoringRules 要有明确分值
7. replyRules 要有具体指导，不要只说"自然一点"
8. 直接输出 JSON，不要 markdown 代码块包裹，不要解释
9. **replyExample.good 和 replyExample.bad 只写回复正文，绝对不要包含「评论'xxx' → 回复：'yyy'」这种元格式**

## 场景说明
- 场景1 (videoComment): 视频评论 = 在视频下留言吸引其他观众注意，相当于广告位
- 场景2 (analysis): 评论回复 = 分析已有评论并生成回复，吸引评论者注意
- 场景3 (dmOpener + dmStages): 私信转化 = 多阶段私信漏斗

## replyExample 正确 vs 错误示例
❌ 错误: { "good": "评论'价格多少' → 回复：'私信您了解详情哦'", "bad": "评论'太贵了' → 回复：'一分钱一分货'" }
✅ 正确: { "good": "私信您了解详情哦～不同方案价格不同，看看哪个适合您", "bad": "亲可以看看哦" }
replyExample 中的文本就是最终输出的回复内容，不需要标注原文是什么、回复是什么。"""


@router.post("/generate")
async def generate_template(
    request: TemplateGenerateRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """AI 根据描述生成提示词模板 JSON"""
    from app.services.ai_generator import ai_generator as gen

    user_prompt = (
        f"行业：{request.industry}\n"
        f"用户描述：{request.description}\n\n"
        f"参考 JSON 结构：\n{TEMPLATE_SCHEMA_DESC}\n\n"
        f"请根据用户描述和行业，生成完整的提示词模板 JSON。"
        f"行业特定的语义信号、禁用词、示例都要与行业匹配。"
    )

    try:
        raw = await gen.generate_custom(db, TEMPLATE_GEN_SYSTEM, user_prompt, max_tokens=4096)
        content = raw.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:]) if lines[0].startswith("```") else content
            if content.endswith("```"):
                content = content[: content.rfind("```")].strip()
        template = json.loads(content)
        # 校验 AI 生成的 replyExample 格式
        try:
            prompt_template_service._validate_reply_example(template)
        except ValueError as ve:
            raise HTTPException(status_code=422, detail=f"AI 生成的 replyExample 格式不正确: {str(ve)}")
        return {"content": template}
    except json.JSONDecodeError as e:
        logger.warning("AI generated invalid JSON: %s", str(e)[:200])
        raise HTTPException(status_code=500, detail=f"AI 生成的 JSON 格式无效: {str(e)[:200]}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Template generation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


@router.post("/generate-stream")
async def generate_template_stream(
    request: TemplateGenerateRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """AI 根据描述生成提示词模板 JSON（SSE 流式输出，避免超时）"""
    from app.services.ai_generator import ai_generator as gen

    user_prompt = (
        f"行业：{request.industry}\n"
        f"用户描述：{request.description}\n\n"
        f"参考 JSON 结构：\n{TEMPLATE_SCHEMA_DESC}\n\n"
        f"请根据用户描述和行业，生成完整的提示词模板 JSON。"
        f"行业特定的语义信号、禁用词、示例都要与行业匹配。"
    )

    async def event_stream():
        yield f"data: {json.dumps({'type': 'status', 'text': '正在调用 AI 生成...'})}\n\n"

        raw_chunks = []
        try:
            async for chunk in gen.generate_custom_stream(
                db, TEMPLATE_GEN_SYSTEM, user_prompt, max_tokens=4096
            ):
                raw_chunks.append(chunk)
                # Forward each token to the client
                yield f"data: {json.dumps({'type': 'token', 'text': chunk})}\n\n"

            # All tokens received, assemble and parse
            raw = "".join(raw_chunks).strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:])
                if raw.endswith("```"):
                    raw = raw[: raw.rfind("```")].strip()
            template = json.loads(raw)
            # 校验 AI 生成的 replyExample 格式
            try:
                prompt_template_service._validate_reply_example(template)
            except ValueError as ve:
                yield f"data: {json.dumps({'type': 'warning', 'message': f'replyExample 格式不正确: {str(ve)}。请重新生成。', 'content': template})}\n\n"
                return
            yield f"data: {json.dumps({'type': 'done', 'content': template})}\n\n"
        except json.JSONDecodeError as e:
            logger.warning("AI generated invalid JSON: %s", str(e)[:200])
            yield f"data: {json.dumps({'type': 'error', 'message': f'AI 生成的 JSON 格式无效: {str(e)[:200]}'})}\n\n"
        except Exception as e:
            logger.error("Template generation failed: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)[:200]})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("")
def list_templates(
    include_disabled: bool = Query(False),
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    templates = prompt_template_service.list_all_templates(db, include_disabled=include_disabled)
    version = prompt_template_service.get_version(db)
    return {"templates": templates, "total": len(templates), "version": version}


@router.get("/{name}")
def get_template(
    name: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    tmpl = prompt_template_service.get_template(db, name)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return tmpl


@router.post("")
async def create_template(
    request: TemplateCreateRequest,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    try:
        tmpl = prompt_template_service.create_template(
            db, name=request.name, industry=request.industry,
            content=request.content, description=request.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    version = prompt_template_service.get_version(db)
    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_devices({
        "event": "prompt_templates_updated",
        "version": version,
    })
    await pair_ws_manager.broadcast_to_admins({
        "event": "prompt_templates_changed",
        "version": version,
    })
    return tmpl


@router.put("/{name}")
async def update_template(
    name: str,
    request: TemplateUpdateRequest,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    try:
        tmpl = prompt_template_service.update_template(
            db, name=name,
            content=request.content,
            industry=request.industry,
            description=request.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    version = prompt_template_service.get_version(db)
    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_devices({
        "event": "prompt_templates_updated",
        "version": version,
    })
    await pair_ws_manager.broadcast_to_admins({
        "event": "prompt_templates_changed",
        "version": version,
    })
    return tmpl


@router.delete("/{name}")
async def delete_template(
    name: str,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    deleted = prompt_template_service.delete_template(db, name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Template not found")

    version = prompt_template_service.get_version(db)
    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_devices({
        "event": "prompt_templates_updated",
        "version": version,
    })
    await pair_ws_manager.broadcast_to_admins({
        "event": "prompt_templates_changed",
        "version": version,
    })
    return {"deleted": True, "name": name}


@router.patch("/{name}/toggle")
async def toggle_template(
    name: str,
    request: TemplateToggleRequest,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    try:
        tmpl = prompt_template_service.toggle_template(db, name, request.enabled)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    version = prompt_template_service.get_version(db)
    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_devices({
        "event": "prompt_templates_updated",
        "version": version,
    })
    await pair_ws_manager.broadcast_to_admins({
        "event": "prompt_templates_changed",
        "version": version,
    })
    return tmpl
```

## app/routers/reference_data.py

```python
"""系统字典 API — 管理所有下拉选项 + 分类."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import ReferenceData, ReferenceCategory

router = APIRouter(prefix="/api", tags=["reference-data"])

DEFAULT_CATEGORIES = [
    ("series_genre", "系列类型"),
    ("character_role", "角色类型"),
    ("scene_type", "场景类型"),
    ("scene_lighting", "场景光照"),
    ("scene_mood", "场景氛围"),
    ("dataSourceTypes", "数据来源类型"),
]

DEFAULT_DATA = {
    "series_genre": [
        ("drama", "都市爱情"), ("romance", "古装言情"), ("fantasy", "奇幻"),
        ("suspense", "悬疑推理"), ("scifi", "科幻"), ("comedy", "喜剧"),
        ("action", "动作"), ("horror", "恐怖"), ("history", "历史"),
    ],
    "character_role": [
        ("protagonist", "主角"), ("antagonist", "反派"),
        ("supporting", "配角"), ("cameo", "客串"),
    ],
    "scene_type": [
        ("indoor", "室内"), ("outdoor", "室外"),
        ("transition", "转场"), ("special", "特殊"),
    ],
    "scene_lighting": [
        ("day", "白天"), ("dusk", "黄昏"), ("night", "夜晚"),
        ("warm_indoor", "室内暖光"), ("cold_fluorescent", "冷荧光"),
    ],
    "scene_mood": [
        ("warm", "温馨"), ("tense", "紧张"), ("romantic", "浪漫"),
        ("mysterious", "悬疑"), ("sad", "悲伤"), ("joyful", "欢快"),
    ],
    "dataSourceTypes": [
        ("0", "普通视频"), ("1", "带货视频"),
    ],
}


# ==== Category CRUD ====

@router.get("/reference-categories")
def list_categories(db: Session = Depends(get_db)):
    """获取所有字典分类 (公开只读), 含每类已启用选项数."""
    cats = db.query(ReferenceCategory).order_by(ReferenceCategory.sort_order).all()
    # Per-category enabled item count
    counts = {}
    if cats:
        rows = (
            db.query(ReferenceData.category, func.count(ReferenceData.id))
            .filter(ReferenceData.enabled == True)
            .group_by(ReferenceData.category)
            .all()
        )
        counts = {row[0]: row[1] for row in rows}
    return {"ok": True, "categories": [
        {"id": c.id, "key": c.key, "label": c.label,
         "sort_order": c.sort_order, "item_count": counts.get(c.key, 0)}
        for c in cats
    ]}


class CategoryCreate(BaseModel):
    key: str
    label: str
    sort_order: int = 0


@router.post("/reference-categories")
def create_category(body: CategoryCreate, db: Session = Depends(get_db),
                    user = Depends(verify_admin_token)):
    cat = ReferenceCategory(key=body.key, label=body.label, sort_order=body.sort_order)
    db.add(cat)
    try:
        db.commit(); db.refresh(cat)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"分类 key '{body.key}' 已存在")
    return {"ok": True, "category": {"id": cat.id, "key": cat.key, "label": cat.label}}


@router.put("/reference-categories/{cat_id}")
def update_category(cat_id: str, body: dict, db: Session = Depends(get_db),
                    user = Depends(verify_admin_token)):
    cat = db.query(ReferenceCategory).filter(ReferenceCategory.id == cat_id).first()
    if not cat:
        raise HTTPException(404, "分类不存在")
    if "label" in body:
        cat.label = body["label"]
    if "sort_order" in body:
        cat.sort_order = body["sort_order"]
    if "key" in body and body["key"] != cat.key:
        old_key = cat.key
        cat.key = body["key"]
        db.query(ReferenceData).filter(ReferenceData.category == old_key).update(
            {"category": body["key"]}, synchronize_session=False)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"分类 key '{body.get('key')}' 已存在")
    return {"ok": True}


@router.delete("/reference-categories/{cat_id}")
def delete_category(cat_id: str, db: Session = Depends(get_db),
                    user = Depends(verify_admin_token)):
    cat = db.query(ReferenceCategory).filter(ReferenceCategory.id == cat_id).first()
    if not cat:
        raise HTTPException(404, "分类不存在")
    db.query(ReferenceData).filter(ReferenceData.category == cat.key).delete()
    db.delete(cat)
    db.commit()
    return {"ok": True}


# ==== Item CRUD ====

@router.get("/reference-data/{category}")
def list_items(category: str, db: Session = Depends(get_db)):
    """获取某分类下的所有启用选项 (公开只读)."""
    items = db.query(ReferenceData).filter(
        ReferenceData.category == category, ReferenceData.enabled == True
    ).order_by(ReferenceData.sort_order).all()
    return {"ok": True, "items": [
        {"value": it.value, "label": it.label, "description": it.description or ""}
        for it in items
    ]}


class RefDataCreate(BaseModel):
    category: str
    value: str
    label: str
    description: str = ""
    sort_order: int = 0


@router.post("/reference-data")
def create_item(body: RefDataCreate, db: Session = Depends(get_db),
                user = Depends(verify_admin_token)):
    item = ReferenceData(**body.model_dump())
    db.add(item)
    try:
        db.commit(); db.refresh(item)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"选项 '{body.value}' 在分类 '{body.category}' 中已存在")
    return {"ok": True, "item": {"value": item.value, "label": item.label}}


@router.put("/reference-data/{item_id}")
def update_item(item_id: str, body: dict, db: Session = Depends(get_db),
                user = Depends(verify_admin_token)):
    item = db.query(ReferenceData).filter(ReferenceData.id == item_id).first()
    if not item: raise HTTPException(404)
    for k, v in body.items():
        if hasattr(item, k): setattr(item, k, v)
    db.commit()
    return {"ok": True}


@router.delete("/reference-data/{item_id}")
def delete_item(item_id: str, db: Session = Depends(get_db),
                user = Depends(verify_admin_token)):
    db.query(ReferenceData).filter(ReferenceData.id == item_id).delete()
    db.commit()
    return {"ok": True}


@router.get("/reference-data/admin/{category}")
def list_all_items(category: str, db: Session = Depends(get_db),
                   user = Depends(verify_admin_token)):
    """管理端：列出某分类所有项 (含 id, enabled)."""
    items = db.query(ReferenceData).filter(
        ReferenceData.category == category
    ).order_by(ReferenceData.sort_order).all()
    return {"ok": True, "items": [
        {"id": it.id, "value": it.value, "label": it.label,
         "description": it.description or "",
         "sort_order": it.sort_order, "enabled": it.enabled}
        for it in items
    ]}


# ==== Seed ====

def seed_reference_data(db: Session):
    """启动时 seed 默认分类 + 字典数据。幂等：已存在则跳过。"""
    for i, (key, label) in enumerate(DEFAULT_CATEGORIES):
        exists = db.query(ReferenceCategory).filter(ReferenceCategory.key == key).first()
        if not exists:
            db.add(ReferenceCategory(key=key, label=label, sort_order=i))
    db.commit()
    for category, entries in DEFAULT_DATA.items():
        for i, entry in enumerate(entries):
            val = entry[0]
            label = entry[1]
            desc = entry[2] if len(entry) > 2 else ""
            exists = db.query(ReferenceData).filter(
                ReferenceData.category == category,
                ReferenceData.value == val
            ).first()
            if not exists:
                db.add(ReferenceData(category=category, value=val, label=label,
                                     description=desc, sort_order=i))
    db.commit()
```

## app/routers/scenes.py

```python
"""场景管理 API."""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import Scene
from app.services.ai_generator import ai_generator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scenes", tags=["scenes"])


class SceneCreate(BaseModel):
    name: str
    scene_type: str = "indoor"
    location_desc: Optional[str] = None
    lighting: Optional[str] = None
    mood: Optional[str] = None


class AutoGenerateInput(BaseModel):
    text: str = Field(..., min_length=10, max_length=5000)
    genre: str = "drama"
    count: int = Field(default=5, ge=1, le=10)

SCENE_GEN_SYSTEM = """你是一位资深的电影导演和场景设计师。根据用户提供的故事概要，生成详细的拍摄场景描述。

输出要求：
1. 必须是合法的 JSON，不要包含 markdown 代码块标记
2. 场景数量与用户要求一致
3. 每个场景必须包含所有字段
4. location_desc 要足够详细（50-100字），用于 AI 生成场景参考图
5. 场景之间要有区分度，覆盖故事的主要场景发生地"""


@router.get("")
def list_scenes(db: Session = Depends(get_db),
                _: str = Depends(verify_admin_token)):
    return {"ok": True, "scenes": [_to_dict(s) for s in db.query(Scene).all()]}


@router.post("")
def create_scene(body: SceneCreate, db: Session = Depends(get_db),
                 user = Depends(verify_admin_token)):
    s = Scene(**body.model_dump())
    db.add(s); db.commit(); db.refresh(s)
    return {"ok": True, "scene": _to_dict(s)}


@router.put("/{scene_id}")
def update_scene(scene_id: str, body: dict, db: Session = Depends(get_db),
                 user = Depends(verify_admin_token)):
    s = db.query(Scene).filter(Scene.id == scene_id).first()
    if not s:
        raise HTTPException(404, "Scene not found")
    for k, v in body.items():
        if hasattr(s, k):
            setattr(s, k, v)
    db.commit()
    return {"ok": True}


@router.delete("/{scene_id}")
def delete_scene(scene_id: str, db: Session = Depends(get_db),
                 user = Depends(verify_admin_token)):
    db.query(Scene).filter(Scene.id == scene_id).delete()
    db.commit()
    return {"ok": True}


@router.post("/auto-generate")
async def auto_generate_scenes(body: AutoGenerateInput, db: Session = Depends(get_db),
                               user = Depends(verify_admin_token)):
    """AI 根据故事文本自动生成场景描述。返回场景列表（不持久化），前端确认后逐个创建。"""
    user_prompt = f"""故事概要：{body.text}
类型：{body.genre}
需要生成的场景数量：{body.count}

为每个场景生成以下字段的 JSON：
- name: 场景/地点名称
- scene_type: indoor(室内) / outdoor(室外) / transition(转场) / special(特殊)
- location_desc: 详细地点描述（50-100字，用于 AI 图像生成）
- lighting: day(白天) / dusk(黄昏) / night(夜晚) / warm_indoor(室内暖光) / cold_fluorescent(冷荧光)
- mood: warm(温馨) / tense(紧张) / romantic(浪漫) / mysterious(悬疑) / sad(悲伤) / joyful(欢快)

严格输出 JSON 数组，格式：{{"scenes": [{{"name":"...","scene_type":"...",...}}]}}"""
    try:
        raw = await ai_generator.generate_custom(
            db, SCENE_GEN_SYSTEM, user_prompt, max_tokens=4096, temperature=0.8
        )
        parsed = _parse_scenes_json(raw)
        return {"ok": True, "scenes": parsed["scenes"]}
    except Exception as e:
        logger.warning("Scene auto-generation failed: %s", e)
        raise HTTPException(500, f"AI 场景生成失败: {e}")


def _parse_scenes_json(raw: str) -> dict:
    import re
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    m = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    m = re.search(r'\{[^{}]*"scenes"\s*:\s*\[[\s\S]*?\][^{}]*\}', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"无法解析 LLM 返回的场景 JSON: {raw[:300]}")


def _to_dict(s: Scene) -> dict:
    return {col.name: getattr(s, col.name) for col in Scene.__table__.columns}
```

## app/routers/seedance.py

```python
"""Seedance 2.0 集成 — 火山方舟 Ark API."""
import logging
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_admin_token

logger = logging.getLogger(__name__)

SEEDANCE_API_URL = "https://ark.cn-beijing.volces.com/api/v3"
SEEDANCE_MODEL_ID = "doubao-seedance-2-0-260128"

_STRIP_REQ_HEADERS = {
    "host", "connection", "content-length", "transfer-encoding",
    "authorization", "cookie", "x-forwarded-for", "x-forwarded-proto",
    "x-real-ip", "origin", "referer",
}
_STRIP_RES_HEADERS = {
    "transfer-encoding", "content-encoding", "content-length",
}

_client = None
_client_key = None


def _get_api_key(db: Session) -> str:
    key = os.getenv("SEEDANCE_API_KEY", "")
    if db:
        try:
            from app.db_models import SystemSetting
            row = db.query(SystemSetting).filter(SystemSetting.key == "seedance_api_key").first()
            if row and row.value:
                key = row.value
        except Exception:
            pass
    if not key:
        raise HTTPException(status_code=400, detail="请先在系统设置中配置 Seedance API Key")
    return key


def _get_client(api_key: str) -> httpx.AsyncClient:
    global _client, _client_key
    if _client is None or _client_key != api_key:
        if _client:
            import asyncio
            try:
                asyncio.ensure_future(_client.aclose())
            except Exception:
                pass
        _client = httpx.AsyncClient(
            trust_env=False,
            base_url=SEEDANCE_API_URL,
            timeout=httpx.Timeout(600, connect=10),
            headers={"Authorization": f"Bearer {api_key}"},
        )
        _client_key = api_key
    return _client


# ==== 便捷 API Router (/api/seedance) ====

api_router = APIRouter(prefix="/api/seedance", tags=["seedance"])


class SeedanceGenerateRequest(BaseModel):
    prompt: str
    aspect_ratio: str = "9:16"
    duration: int = 5
    resolution: str = "720p"
    image_urls: list[str] = []


@api_router.post("/generate")
async def seedance_generate(body: SeedanceGenerateRequest, db: Session = Depends(get_db), user = Depends(verify_admin_token)):
    """提交 Seedance 视频生成任务."""
    api_key = _get_api_key(db)
    client = _get_client(api_key)

    content = [{"type": "text", "text": body.prompt}]
    for url in body.image_urls:
        content.append({"type": "image_url", "image_url": {"url": url}})

    payload = {
        "model": SEEDANCE_MODEL_ID,
        "content": content,
        "parameters": {
            "aspect_ratio": body.aspect_ratio,
            "duration": body.duration,
            "resolution": body.resolution,
        },
    }

    try:
        resp = await client.post("/contents/generations/tasks", json=payload)
        data = resp.json()
        if resp.is_success:
            return {"ok": True, "task_id": data.get("id") or data.get("task_id")}
        return {"ok": False, "error": data.get("error", {}).get("message", str(data))}
    except Exception as e:
        logger.exception("Seedance generate failed")
        raise HTTPException(status_code=502, detail=f"Seedance 任务提交失败: {e}")


@api_router.get("/task/{task_id}")
async def seedance_get_task(task_id: str, db: Session = Depends(get_db), user = Depends(verify_admin_token)):
    """查询 Seedance 任务状态."""
    api_key = _get_api_key(db)
    client = _get_client(api_key)

    try:
        resp = await client.get(f"/contents/generations/tasks/{task_id}")
        data = resp.json()
        if not resp.is_success:
            return {"ok": False, "error": data.get("error", {}).get("message", "查询失败")}

        status = data.get("status", "unknown")
        result = {"ok": True, "task_id": task_id, "status": status}

        if status == "succeeded":
            output = data.get("output", {})
            videos = output.get("videos", [])
            if videos:
                result["video_url"] = videos[0].get("url", "")
            result["progress"] = 100
        elif status == "failed":
            result["error"] = data.get("error", {}).get("message", "任务失败")
        else:
            result["progress"] = data.get("progress", 0)

        return result
    except Exception as e:
        logger.exception("Seedance task query failed")
        raise HTTPException(status_code=502, detail=f"Seedance 任务查询失败: {e}")


# ==== 透明代理 Router (/api/seedance-proxy) ====

proxy_router = APIRouter(prefix="/api/seedance-proxy", tags=["seedance-proxy"])


async def _do_proxy(request: Request, db: Session, path: str = "") -> Response:
    api_key = _get_api_key(db)
    client = _get_client(api_key)

    target_path = path.lstrip("/")
    if request.query_params:
        target_path += "?" + str(request.query_params)

    forward_headers = {}
    for k, v in request.headers.items():
        if k.lower() not in _STRIP_REQ_HEADERS:
            forward_headers[k] = v

    body = await request.body()

    try:
        resp = await client.request(
            method=request.method,
            url=target_path,
            headers=forward_headers,
            content=body or None,
        )
        proxy_headers = {}
        for k, v in resp.headers.items():
            if k.lower() not in _STRIP_RES_HEADERS:
                proxy_headers[k] = v

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=proxy_headers,
            media_type=resp.headers.get("content-type"),
        )
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Seedance API 不可达")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Seedance API 响应超时")
    except httpx.RequestError as e:
        logger.warning("Seedance proxy failed: %s", e)
        raise HTTPException(status_code=502, detail="Seedance API 代理请求失败")
    except Exception:
        logger.exception("Unexpected Seedance proxy error")
        raise HTTPException(status_code=502, detail="代理服务异常")


PROXY_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"]


@proxy_router.api_route("/{path:path}", methods=PROXY_METHODS)
async def proxy_seedance(path: str, request: Request, db: Session = Depends(get_db), user = Depends(verify_admin_token)):
    return await _do_proxy(request, db, path)


@proxy_router.api_route("/", methods=PROXY_METHODS)
async def proxy_seedance_root(request: Request, db: Session = Depends(get_db), user = Depends(verify_admin_token)):
    return await _do_proxy(request, db, "")
```

## app/routers/selectors.py

```python
"""Selector management CRUD API — admin only."""
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File as FastAPIFile, Form
from typing import Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
import time

from app.database import get_db
from app.deps import verify_admin_token, require_role
from app.services.selector_service import selector_service
from app.services.template_service import template_service

router = APIRouter(prefix="/api/selectors", tags=["selectors"])


class SelectorCreateRequest(BaseModel):
    action_name: str
    strategies: list[dict]
    platform_version: str = "default"
    resolution_profile: str = "default"
    description: str = ""
    category: str = ""
    purpose: str = "locate"
    strategy_logic: str = "and"
    extract_field: Optional[str] = None
    clean_mode: Optional[str] = None
    clean_pattern: Optional[str] = None
    clean_prompt: Optional[str] = None


class SelectorUpdateRequest(BaseModel):
    strategies: Optional[list[dict]] = None
    platform_version: Optional[str] = None
    resolution_profile: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    purpose: Optional[str] = None
    strategy_logic: Optional[str] = None
    extract_field: Optional[str] = None
    clean_mode: Optional[str] = None
    clean_pattern: Optional[str] = None
    clean_prompt: Optional[str] = None
    # Note: version is auto-bumped on any change, not user-settable


class SelectorToggleRequest(BaseModel):
    enabled: bool


@router.get("")
def list_selectors(
    include_disabled: bool = Query(False),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    selectors = selector_service.list_all_selectors(db, include_disabled=include_disabled, category=category)
    version = selector_service.get_version(db)
    return {"selectors": selectors, "total": len(selectors), "version": version}


@router.get("/{action_name}")
def get_selector(
    action_name: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    sel = selector_service.get_selector(db, action_name)
    if not sel:
        raise HTTPException(status_code=404, detail="Selector not found")
    return sel


@router.post("")
async def create_selector(
    request: SelectorCreateRequest,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    try:
        sel = selector_service.create_selector(
            db, action_name=request.action_name,
            strategies=request.strategies,
            platform_version=request.platform_version,
            resolution_profile=request.resolution_profile,
            description=request.description,
            category=request.category,
            purpose=request.purpose,
            strategy_logic=request.strategy_logic,
            extract_field=request.extract_field,
            clean_mode=request.clean_mode,
            clean_pattern=request.clean_pattern,
            clean_prompt=request.clean_prompt,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    version = selector_service.get_version(db)
    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_devices({
        "event": "selectors_updated",
        "version": version,
    })
    await pair_ws_manager.broadcast_to_admins({"event": "selectors_changed"})
    return sel


@router.put("/{action_name}")
async def update_selector(
    action_name: str,
    request: SelectorUpdateRequest,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    try:
        sel = selector_service.update_selector(
            db, action_name=action_name,
            strategies=request.strategies,
            platform_version=request.platform_version,
            resolution_profile=request.resolution_profile,
            description=request.description,
            category=request.category,
            purpose=request.purpose,
            strategy_logic=request.strategy_logic,
            extract_field=request.extract_field,
            clean_mode=request.clean_mode,
            clean_pattern=request.clean_pattern,
            clean_prompt=request.clean_prompt,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    version = selector_service.get_version(db)
    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_devices({
        "event": "selectors_updated",
        "version": version,
    })
    await pair_ws_manager.broadcast_to_admins({"event": "selectors_changed"})
    return sel


@router.delete("/{action_name}")
async def delete_selector(
    action_name: str,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    deleted = selector_service.delete_selector(db, action_name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Selector not found")

    version = selector_service.get_version(db)
    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_devices({
        "event": "selectors_updated",
        "version": version,
    })
    await pair_ws_manager.broadcast_to_admins({"event": "selectors_changed"})
    return {"deleted": True, "action_name": action_name}


@router.patch("/{action_name}/toggle")
async def toggle_selector(
    action_name: str,
    request: SelectorToggleRequest,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    try:
        sel = selector_service.toggle_selector(db, action_name, request.enabled)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    version = selector_service.get_version(db)
    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_devices({
        "event": "selectors_updated",
        "version": version,
    })
    await pair_ws_manager.broadcast_to_admins({"event": "selectors_changed"})
    return sel


# --- Template image endpoints ---

@router.get("/templates")
def list_templates(
    resolution: str = Query(None),
    user = Depends(verify_admin_token),
):
    templates = template_service.list_templates(resolution=resolution)
    return {"templates": templates, "total": len(templates)}


@router.post("/templates/upload")
async def upload_template(
    file: UploadFile = FastAPIFile(...),
    action_name: str = Form(""),
    resolution: str = Query("default"),
    user = Depends(require_role("admin")),
):
    import os
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".png", ".jpg", ".jpeg"):
        raise HTTPException(status_code=400, detail="仅支持 .png/.jpg/.jpeg 格式")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过 5MB")

    safe_name = (action_name or "template").replace("/", "_").replace("\\", "_")
    filename = f"{safe_name}_{int(time.time() * 1000)}{ext}"
    template_service.save_template(filename, content, resolution=resolution)
    return {"filename": filename, "size": len(content), "resolution": resolution}


@router.delete("/templates/{filename}")
def delete_template(
    filename: str,
    resolution: str = Query("default"),
    user = Depends(require_role("admin")),
):
    deleted = template_service.delete_template(filename, resolution=resolution)
    if not deleted:
        raise HTTPException(status_code=404, detail="模板文件不存在")
    return {"deleted": True, "filename": filename}
```

## app/routers/series.py

```python
"""系列 + 剧集管理 API."""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import Series, Episode, Character, Scene, PipelineRun, series_characters, series_scenes
from app.services.ai_generator import ai_generator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/series", tags=["series"])


class SeriesCreate(BaseModel):
    title: str
    logline: Optional[str] = None
    genre: str = "drama"
    total_episodes: int = 30
    target_duration: int = 90
    mode: str = "step_by_step"
    pilot_first: bool = True


class EpisodeUpdate(BaseModel):
    title: Optional[str] = None
    script_json: Optional[dict] = None
    storyboard_json: Optional[dict] = None


# === AI 自动生成角色 + 场景 ===

@router.post("/{series_id}/auto-generate")
async def auto_generate_series_assets(series_id: str, db: Session = Depends(get_db),
                                      user = Depends(verify_admin_token)):
    """根据系列 logline 自动生成角色和场景，自动创建并关联到系列。"""
    s = db.query(Series).filter(Series.id == series_id).first()
    if not s:
        raise HTTPException(404, "Series not found")
    if not s.logline:
        raise HTTPException(400, "请先填写系列的故事概要 (logline)")

    text = s.logline
    genre = s.genre

    # 1. 生成角色
    char_prompt = f"""故事概要：{text}
类型：{genre}
需要生成的角色数量：4

为每个角色生成以下字段的 JSON：
- name: 角色姓名
- role_type: protagonist(主角) / antagonist(反派) / supporting(配角) / cameo(客串)
- gender: male / female
- age_range: 年龄段，如 "25-30"
- personality: 性格描述（2-3句）
- appearance_desc: 详细外貌描述（50-100字，用于 AI 图像生成）
- outfit_desc: 典型着装描述（30-50字，用于 AI 图像生成）

严格输出 JSON 数组，格式：{{"characters": [...]}}"""
    try:
        raw_chars = await ai_generator.generate_custom(
            db, _CHAR_SYSTEM, char_prompt, max_tokens=4096, temperature=0.8
        )
        char_data = _parse_json_with_key(raw_chars, "characters")
    except Exception as e:
        logger.warning("Auto-generate characters failed: %s", e)
        raise HTTPException(500, f"角色生成失败: {e}")

    # 2. 生成场景
    scene_prompt = f"""故事概要：{text}
类型：{genre}
需要生成的场景数量：5

为每个场景生成以下字段的 JSON：
- name: 场景/地点名称
- scene_type: indoor(室内) / outdoor(室外) / transition(转场) / special(特殊)
- location_desc: 详细地点描述（50-100字，用于 AI 图像生成）
- lighting: day(白天) / dusk(黄昏) / night(夜晚) / warm_indoor(室内暖光) / cold_fluorescent(冷荧光)
- mood: warm(温馨) / tense(紧张) / romantic(浪漫) / mysterious(悬疑) / sad(悲伤) / joyful(欢快)

严格输出 JSON 数组，格式：{{"scenes": [...]}}"""
    try:
        raw_scenes = await ai_generator.generate_custom(
            db, _SCENE_SYSTEM, scene_prompt, max_tokens=4096, temperature=0.8
        )
        scene_data = _parse_json_with_key(raw_scenes, "scenes")
    except Exception as e:
        logger.warning("Auto-generate scenes failed: %s", e)
        raise HTTPException(500, f"场景生成失败: {e}")

    # 3. 持久化角色
    created_chars = []
    for c in char_data["characters"]:
        ch = Character(
            name=c.get("name", "?"),
            role_type=c.get("role_type", "supporting"),
            gender=c.get("gender", "male"),
            age_range=c.get("age_range", ""),
            personality=c.get("personality", ""),
            appearance_desc=c.get("appearance_desc", ""),
            outfit_desc=c.get("outfit_desc", ""),
        )
        db.add(ch)
        created_chars.append(ch)

    # 4. 持久化场景
    created_scenes = []
    for sc in scene_data["scenes"]:
        scene = Scene(
            name=sc.get("name", "?"),
            scene_type=sc.get("scene_type", "indoor"),
            location_desc=sc.get("location_desc", ""),
            lighting=sc.get("lighting", ""),
            mood=sc.get("mood", ""),
        )
        db.add(scene)
        created_scenes.append(scene)

    db.flush()

    # 5. 关联到系列
    for ch in created_chars:
        s.characters.append(ch)
    for sc in created_scenes:
        s.scenes.append(sc)

    db.commit()

    return {
        "ok": True,
        "characters": [_series_char_dict(c) for c in created_chars],
        "scenes": [_series_scene_dict(sc) for sc in created_scenes],
    }


_CHAR_SYSTEM = """你是一位资深的编剧和角色设计师。根据故事概要生成详细的角色档案。
输出必须是合法的 JSON，不要包含 markdown 代码块标记。每个角色包含所有要求字段。
appearance_desc 要足够详细（50-100字），用于 AI 图像生成。角色之间要有区分度。"""

_SCENE_SYSTEM = """你是一位资深的电影导演和场景设计师。根据故事概要生成详细的场景描述。
输出必须是合法的 JSON，不要包含 markdown 代码块标记。每个场景包含所有要求字段。
location_desc 要足够详细（50-100字），用于 AI 图像生成。场景之间要有区分度。"""


def _parse_json_with_key(raw: str, key: str) -> dict:
    import re
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    m = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Brace-counting extraction: find {"key":[...]} with proper nesting
    key_pos = raw.find('"' + key + '"')
    if key_pos >= 0:
        # Find the opening brace before the key
        brace_start = raw.rfind('{', 0, key_pos)
        if brace_start >= 0:
            depth = 0
            i = brace_start
            while i < len(raw):
                if raw[i] == '{':
                    depth += 1
                elif raw[i] == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(raw[brace_start:i + 1])
                        except json.JSONDecodeError:
                            pass
                        break
                i += 1
    raise ValueError(f"无法解析 LLM 返回的 JSON (key={key}): {raw[:300]}")


def _series_char_dict(c: Character) -> dict:
    return {col.name: getattr(c, col.name) for col in Character.__table__.columns}


def _series_scene_dict(s: Scene) -> dict:
    return {col.name: getattr(s, col.name) for col in Scene.__table__.columns}


def _series_dict(s: Series) -> dict:
    base = {col.name: getattr(s, col.name) for col in Series.__table__.columns}
    base["character_count"] = len(s.characters) if hasattr(s, "characters") else 0
    base["scene_count"] = len(s.scenes) if hasattr(s, "scenes") else 0
    return base


def _episode_dict(e: Episode) -> dict:
    return {col.name: getattr(e, col.name) for col in Episode.__table__.columns}


# === Series CRUD ===

@router.get("")
def list_series(db: Session = Depends(get_db),
                _: str = Depends(verify_admin_token)):
    all_series = db.query(Series).order_by(Series.updated_at.desc()).all()
    return {"ok": True, "series": [_series_dict(s) for s in all_series]}

@router.post("")
def create_series(body: SeriesCreate, db: Session = Depends(get_db),
                  user = Depends(verify_admin_token)):
    s = Series(**body.model_dump())
    db.add(s)
    db.flush()  # 确保 s.id 已生成，满足 Episode FK 约束
    for ep_num in range(1, body.total_episodes + 1):
        db.add(Episode(series_id=s.id, episode_number=ep_num, status="pending"))
    db.commit(); db.refresh(s)
    return {"ok": True, "series": _series_dict(s)}

@router.get("/{series_id}")
def get_series(series_id: str, db: Session = Depends(get_db)):
    s = db.query(Series).filter(Series.id == series_id).first()
    if not s:
        raise HTTPException(404, "Series not found")
    episodes = db.query(Episode).filter(
        Episode.series_id == series_id
    ).order_by(Episode.episode_number).all()
    return {"ok": True, "series": _series_dict(s),
            "episodes": [_episode_dict(e) for e in episodes]}

@router.delete("/{series_id}")
def delete_series(series_id: str, db: Session = Depends(get_db),
                  user = Depends(verify_admin_token)):
    s = db.query(Series).filter(Series.id == series_id).first()
    if not s:
        raise HTTPException(404, "Series not found")
    # Clean M2M rows first, then episodes, then series
    db.execute(series_characters.delete().where(series_characters.c.series_id == series_id))
    db.execute(series_scenes.delete().where(series_scenes.c.series_id == series_id))
    db.query(Episode).filter(Episode.series_id == series_id).delete()
    db.query(PipelineRun).filter(PipelineRun.series_id == series_id).delete()
    db.delete(s)
    db.commit()
    return {"ok": True}

# === M2M 关联 ===

@router.post("/{series_id}/characters/{character_id}")
def link_character(series_id: str, character_id: str, db: Session = Depends(get_db),
                   user = Depends(verify_admin_token)):
    s = db.query(Series).filter(Series.id == series_id).first()
    c = db.query(Character).filter(Character.id == character_id).first()
    if not s or not c:
        raise HTTPException(404, "Series or Character not found")
    s.characters.append(c)
    db.commit()
    return {"ok": True}

@router.post("/{series_id}/scenes/{scene_id}")
def link_scene(series_id: str, scene_id: str, db: Session = Depends(get_db),
               user = Depends(verify_admin_token)):
    s = db.query(Series).filter(Series.id == series_id).first()
    sc = db.query(Scene).filter(Scene.id == scene_id).first()
    if not s or not sc:
        raise HTTPException(404, "Series or Scene not found")
    s.scenes.append(sc)
    db.commit()
    return {"ok": True}

# === Episode 管理 ===

@router.put("/{series_id}/episodes/{episode_id}")
def update_episode(series_id: str, episode_id: str, body: EpisodeUpdate,
                   db: Session = Depends(get_db), user = Depends(verify_admin_token)):
    ep = db.query(Episode).filter(
        Episode.id == episode_id, Episode.series_id == series_id
    ).first()
    if not ep:
        raise HTTPException(404, "Episode not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(ep, k, v)
    db.commit()
    return {"ok": True}
```

## app/routers/settings.py

```python
"""System settings API — key-value config store for admin UI."""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.database import get_db
from app.db_models import SystemSetting
from app.deps import verify_admin_token, require_role
from app.models import SettingUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Keys whose values are masked in GET responses (never sent to client)
_SENSITIVE_KEYS = {"ai_api_key", "llm_api_key"}
_MASKED_VALUE = "****"


@router.get("")
def get_settings(
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    try:
        rows = db.query(SystemSetting).all()
        result = {}
        for s in rows:
            if s.key in _SENSITIVE_KEYS:
                result[s.key] = _MASKED_VALUE
            else:
                result[s.key] = s.value
        return result
    except OperationalError:
        logger.warning("system_settings table missing, returning empty settings")
        return {}


@router.put("")
def update_settings(
    request: SettingUpdate,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    for key, value in request.settings.items():
        # Skip masked values — client sent placeholder, don't overwrite real secret
        if value == _MASKED_VALUE and key in _SENSITIVE_KEYS:
            continue
        try:
            existing = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        except OperationalError:
            logger.warning("system_settings table missing, attempting create")
            from app.database import init_db
            init_db()
            existing = None
        if existing:
            existing.value = value
        else:
            db.add(SystemSetting(key=key, value=value))
    db.commit()
    return {"updated": len(request.settings)}
```

## app/routers/stats.py

```python
"""Statistics API — dashboard, daily stats, realtime metrics."""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.config import bj_now

from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import Account, Device, Task, DailyStats
from app.services.stats_service import stats_service

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/dashboard")
def dashboard_summary(
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """Dashboard overview — account/device/task counts and status distribution."""
    # Account stats
    total_accounts = db.query(Account).count()
    active_accounts = db.query(Account).filter(Account.status == "active").count()
    risk_accounts = db.query(Account).filter(Account.status == "risk_controlled").count()

    # Device stats
    total_devices = db.query(Device).count()
    online_devices = db.query(Device).filter(Device.status == "online").count()

    # Task stats
    total_tasks = db.query(Task).count()
    pending_tasks = db.query(Task).filter(Task.status == "pending").count()
    running_tasks = db.query(Task).filter(Task.status == "running").count()
    completed_tasks = db.query(Task).filter(Task.status == "completed").count()
    failed_tasks = db.query(Task).filter(Task.status == "failed").count()
    cancelled_tasks = db.query(Task).filter(Task.status == "cancelled").count()

    return {
        "accounts": {
            "total": total_accounts,
            "active": active_accounts,
            "risk_controlled": risk_accounts,
        },
        "devices": {
            "total": total_devices,
            "online": online_devices,
        },
        "tasks": {
            "total": total_tasks,
            "pending": pending_tasks,
            "running": running_tasks,
            "completed": completed_tasks,
            "failed": failed_tasks,
            "cancelled": cancelled_tasks,
        },
    }


@router.get("/daily")
def daily_stats(
    date: Optional[str] = Query(None, description="YYYY-MM-DD, defaults to today"),
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """Daily operation stats for all accounts."""
    if not date:
        date = bj_now().strftime("%Y-%m-%d")

    rows = db.query(DailyStats).filter(DailyStats.date == date).all()
    if not rows:
        return {"date": date, "accounts": []}

    # Batch-load accounts to avoid N+1 query
    account_ids = [row.account_id for row in rows]
    accounts_map = {}
    for a in db.query(Account).filter(Account.id.in_(account_ids)).all():
        accounts_map[a.id] = {"nickname": a.nickname, "daily_limits": a.daily_limits or {}}

    default_limits = {"likes": 50, "comments": 20, "follows": 20, "dms": 10, "replies": 15}

    accounts = [{
        "account_id": row.account_id,
        "nickname": accounts_map.get(row.account_id, {}).get("nickname", "unknown"),
        "daily_limits": accounts_map.get(row.account_id, {}).get("daily_limits") or default_limits,
        "likes": row.likes,
        "comments": row.comments,
        "follows": row.follows,
        "dms": row.dms,
        "replies": row.replies,
    } for row in rows]

    return {"date": date, "accounts": accounts}


@router.get("/accounts/{account_id}")
def account_stats(
    account_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """Stats for a specific account — today's counts and remaining quotas."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    today_counts = stats_service.get_today_counts(db, account_id)
    remaining = stats_service.get_remaining_quotas(db, account_id)

    return {
        "account_id": account_id,
        "nickname": account.nickname,
        "today": today_counts,
        "remaining": remaining,
    }


@router.get("/realtime")
def realtime_stats(
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """Realtime metrics for dashboard auto-refresh."""
    online_devices = db.query(Device).filter(Device.status == "online").count()
    running_tasks = db.query(Task).filter(Task.status == "running").count()
    pending_tasks = db.query(Task).filter(Task.status == "pending").count()

    return {
        "online_devices": online_devices,
        "running_tasks": running_tasks,
        "pending_tasks": pending_tasks,
    }
```

## app/routers/tasks.py

```python
"""Task management CRUD API — admin only."""
import logging

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_admin_token
from app.config import bj_now
from app.models import TaskType, TaskStatus
from app.services.task_service import task_service
from app.services.content_service import content_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class TaskCreateRequest(BaseModel):
    type: TaskType
    account_id: Optional[str] = None
    device_id: Optional[str] = None
    params: dict = {}


class TaskBatchCreateRequest(BaseModel):
    type: TaskType
    group_ids: list[str] = []
    account_ids: list[str] = []
    device_id: Optional[str] = None
    params: dict = {}


async def _maybe_resolve_content_template(params: dict, task_type: str, db=None) -> dict:
    """If params has content_template_id, resolve it into params.content."""
    template_id = params.get("content_template_id")
    if not template_id:
        return params
    try:
        keyword = params.get("keyword") or (params.get("keywords", [None])[0]) or ""
        context = {"keyword": keyword, "task_type": task_type}
        generated = await content_service.generate_from_template(db, template_id, context)
        params["content"] = generated
        logger.info("Resolved content_template_id=%s for task_type=%s", template_id, task_type)
    except Exception as e:
        logger.warning("Failed to resolve content_template_id=%s: %s", template_id, e)
    return params


async def _maybe_resolve_dm_sequence(params: dict, db=None) -> dict:
    """If params has dm_sequence_id, resolve into inline dm_messages + content.
    Keeps dm_sequence_id so device can look up poll cache for variants.
    Inline dm_messages serves as fallback for old devices or cache miss."""
    seq_id = params.get("dm_sequence_id")
    if not seq_id or not db:
        return params
    try:
        from app.db_models import DMSequence
        seq = db.query(DMSequence).filter(DMSequence.id == seq_id).first()
        if seq and seq.messages:
            params["dm_messages"] = seq.messages
            # Fallback: first message content for old devices
            first = seq.messages[0]
            if isinstance(first, dict):
                params["content"] = first.get("content", "")
            logger.info("Resolved dm_sequence_id=%s into %d inline messages (id preserved for variants)", seq_id, len(seq.messages))
        else:
            logger.warning("dm_sequence_id=%s not found in DB, removing from params", seq_id)
            params.pop("dm_sequence_id", None)
    except Exception as e:
        logger.warning("Failed to resolve dm_sequence_id=%s: %s", seq_id, e)
        params.pop("dm_sequence_id", None)
    return params


async def _maybe_expand_keywords(params: dict, task_type: str, db=None) -> dict:
    """If nurture task has keywords (seed), expand them into keyword_matrix via AI."""
    if task_type != "nurture" or "keywords" not in params:
        return params
    seeds = [k.strip() for k in params.get("keywords", []) if k and k.strip()]
    if not seeds:
        return params
    try:
        all_expanded = []
        for seed in seeds[:3]:
            expand_count = int(params.get("expand_count", 8))
            expanded = await content_service.generate_keyword_matrix(seed, expand_count, db=db)
            all_expanded.extend(expanded)
        unique = list(dict.fromkeys(seeds + all_expanded))
        params["keyword_matrix"] = unique
        for kw in all_expanded:
            logger.info("AI expanded keyword: %s", kw)
    except Exception as e:
        logger.warning("Failed to expand keywords for nurture task: %s", e)
    return params


def _resolve_task_type(type_val) -> TaskType:
    if isinstance(type_val, TaskType):
        return type_val
    return TaskType(type_val)


def _validate_and_normalize_params(task_type: str, params: dict) -> dict:
    """Validate and normalize task params using models.TASK_PARAMS_VALIDATORS."""
    from app.models import TASK_PARAMS_VALIDATORS
    from pydantic import BaseModel as PydanticBase

    validator = TASK_PARAMS_VALIDATORS.get(task_type)
    if validator is None:
        return params  # unknown type, passthrough

    if callable(validator) and not isinstance(validator, type):
        # Function-style validator (e.g. _validate_nurture_params)
        return validator(params)
    elif isinstance(validator, type) and issubclass(validator, PydanticBase):
        # Pydantic model validator
        validated = validator(**params)
        return validated.model_dump(exclude_none=True)
    return params


@router.post("")
async def create_task(
    request: TaskCreateRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    if not request.account_id:
        raise HTTPException(status_code=400, detail="account_id is required for single create")
    try:
        params = _validate_and_normalize_params(request.type.value, request.params)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid params for {request.type.value}: {str(e)}")
    params = await _maybe_resolve_content_template(params, request.type.value, db=db)
    params = await _maybe_resolve_dm_sequence(params, db=db)
    params = await _maybe_expand_keywords(params, request.type.value, db=db)

    try:
        user_id, _ = user
        task = task_service.create_task(
            db=db,
            task_type=request.type,
            account_id=request.account_id,
            params=params,
            device_id=request.device_id or None,
            user_id=user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_devices({"event": "new_task_available"})
    await pair_ws_manager.broadcast_to_admins({
        "event": "task_updated",
        "task_id": task.id,
        "status": "pending",
    })
    return task


@router.post("/batch")
async def batch_create_tasks(
    request: TaskBatchCreateRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    if not request.group_ids and not request.account_ids:
        raise HTTPException(status_code=400, detail="需要提供 group_ids 或 account_ids")
    user_id, _ = user
    ttype = request.type.value

    try:
        params = _validate_and_normalize_params(ttype, request.params)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid params for {ttype}: {str(e)}")

    from app.db_models import Account, AccountGroupMember, Channel, ChannelItem as DBChannelItem
    from app.models import TaskType as TT, TASK_PARAMS_VALIDATORS

    params = await _maybe_resolve_content_template(params, ttype, db=db)
    params = await _maybe_resolve_dm_sequence(params, db=db)
    params = await _maybe_expand_keywords(params, ttype, db=db)
    raw_keywords = params.get("keywords", []) or ([params.get("keyword")] if params.get("keyword") else [])
    keywords = [k.strip() for k in raw_keywords if k and k.strip()]

    # Only require keywords for keyword-based task types (those with a params validator)
    # collect 允许只用 share_links (分享链接采集)，不需要 keyword
    _needs_keywords = ttype in TASK_PARAMS_VALIDATORS
    _has_share_links = bool(params.get("share_links"))
    if _needs_keywords and not keywords and not request.params.get("keyword") and not _has_share_links:
        raise HTTPException(status_code=400, detail="关键词不能为空（采集任务可使用分享链接代替）")

    # 关键词数量上限
    MAX_KEYWORDS = 500
    if len(keywords) > MAX_KEYWORDS:
        raise HTTPException(status_code=400, detail=f"关键词最多 {MAX_KEYWORDS} 个，当前 {len(keywords)} 个")

    # 校验 group_ids 存在性（避免 FK 约束异常）
    if request.group_ids:
        from app.db_models import AccountGroup
        existing_groups = db.query(AccountGroup.id).filter(
            AccountGroup.id.in_(request.group_ids)
        ).all()
        existing_ids = {g[0] for g in existing_groups}
        missing = [gid for gid in request.group_ids if gid not in existing_ids]
        if missing:
            raise HTTPException(status_code=400, detail=f"分组不存在: {', '.join(missing[:3])}")

    # Resolve accounts: from group_ids + from account_ids
    all_accounts = []
    seen_account_ids = set()

    for gid in request.group_ids:
        member_account_ids = db.query(AccountGroupMember.account_id).filter(
            AccountGroupMember.group_id == gid
        ).scalar_subquery()
        accounts = db.query(Account).filter(
            Account.id.in_(member_account_ids),
            Account.status == "active",
        ).all()
        for acc in accounts:
            if acc.id not in seen_account_ids:
                seen_account_ids.add(acc.id)
                all_accounts.append(acc)

    for aid in request.account_ids:
        if aid in seen_account_ids:
            continue
        acc = db.query(Account).filter(
            Account.id == aid, Account.status == "active"
        ).first()
        if acc:
            seen_account_ids.add(acc.id)
            all_accounts.append(acc)

    if not all_accounts:
        raise HTTPException(status_code=400, detail="所选分组/账号没有活跃账号，请先添加活跃账号")

    created_tasks = []
    if keywords:
        # 确定通道归属的分组：优先用 group_ids[0]，否则查账号所属分组
        channel_group_id = request.group_ids[0] if request.group_ids else None
        if not channel_group_id:
            # 从 account_ids 中查所属分组
            member_group = db.query(AccountGroupMember.group_id).filter(
                AccountGroupMember.account_id.in_(request.account_ids)
            ).first()
            if member_group:
                channel_group_id = member_group[0]
            else:
                # 账号不在任何分组中，自动创建分组
                from app.db_models import AccountGroup
                from datetime import datetime as dt
                display = all_accounts[0].nickname or all_accounts[0].douyin_id or all_accounts[0].id[:8]
                # name 字段 String(100)，截断 display 确保不超长
                ts = dt.now().strftime('%m%d%H%M%S')
                max_display = 100 - len(f"自动分组--{ts}") - 1  # 预留截断空间
                if len(display) > max_display:
                    display = display[:max_display]
                ag = AccountGroup(
                    name=f"自动分组-{display}-{ts}",
                    description="系统自动创建（单账号批量任务）",
                )
                db.add(ag)
                db.flush()
                channel_group_id = ag.id
                # 将账号加入新分组
                for acc in all_accounts:
                    db.add(AccountGroupMember(group_id=ag.id, account_id=acc.id))
                db.flush()

        # 总是新建通道（UUID 自动生成），不复用旧通道
        template_params = {k: v for k, v in params.items() if k not in ("keyword", "keywords", "keyword_matrix")}
        ch = Channel(
            group_id=channel_group_id,
            task_type=ttype,
            status="active",
            account_mode="round_robin",
            params_template=template_params,
            user_id=user_id,
        )
        db.add(ch)
        db.flush()

        # 轮询分配：每个关键词只分配给一个账号，多账号交叉领取
        from app.services.channel_service import channel_service as _ch_svc
        assigned_ids = _ch_svc._round_robin_assign(db, keywords, all_accounts)
        qpos = 0
        for idx, kw in enumerate(keywords):
            ci = DBChannelItem(
                channel_id=ch.id,
                keyword=kw.strip(),
                account_id=assigned_ids[idx],
                status="pending",
                queue_position=qpos,
            )
            qpos += 1
            db.add(ci)
            created_tasks.append({"keyword": kw.strip(), "account_id": assigned_ids[idx]})
        logger.info("通道 %s 已创建: %d 关键词 × %d 账号 (轮询) = %d 项",
                     ch.id, len(keywords), len(all_accounts), len(created_tasks))
    else:
        for acc in all_accounts:
            task = task_service.create_task(
                db=db,
                task_type=TT(ttype),
                account_id=acc.id,
                params=params,
                device_id=request.device_id or None,
                user_id=user_id,
            )
            created_tasks.append({"id": task.id, "account_id": acc.id})

    db.commit()

    if created_tasks:
        from app.db_models import Device
        from app.ws_manager import pair_ws_manager
        if any(t.get("id") for t in created_tasks):
            unbound_accounts = [
                t["account_id"] for t in created_tasks if t.get("id")
                if not db.query(Device).filter(Device.bound_account_id == t["account_id"]).first()
            ]
            if unbound_accounts:
                await pair_ws_manager.broadcast_to_devices({"event": "new_task_available"})
        else:
            await pair_ws_manager.broadcast_to_devices({"event": "new_task_available"})
        # 通知前端更新任务列表
        await pair_ws_manager.broadcast_to_admins({"event": "tasks_changed"})

    return {"created": len(created_tasks), "mode": "channel" if keywords else "direct"}


@router.get("")
def list_tasks(
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None, alias="type"),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    user_id, role = user
    tasks = task_service.list_tasks(db=db, status=status, task_type=type, search=search,
                                     sort_by=sort_by, sort_order=sort_order, skip=skip, limit=limit,
                                     current_user_id=None if role == "admin" else user_id)
    total = task_service.count_tasks(db=db, status=status, task_type=type, search=search,
                                     current_user_id=None if role == "admin" else user_id)
    return {"tasks": tasks, "total": total}


class BatchDeleteRequest(BaseModel):
    task_ids: list[str]


@router.post("/batch-delete")
async def batch_delete_tasks(
    body: BatchDeleteRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    count = task_service.delete_tasks_batch(db, body.task_ids)
    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_admins({"event": "tasks_changed"})
    return {"deleted": count}


@router.get("/{task_id}")
def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    task = task_service.get_task(db=db, task_id=task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    try:
        task = task_service.cancel_task(db=db, task_id=task_id)
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail="Task not found")
        raise HTTPException(status_code=400, detail=str(e))

    from app.ws_manager import pair_ws_manager

    if task.device_id:
        await pair_ws_manager.send_to_device(task.device_id, {
            "event": "cancel_task",
            "task_id": task.id,
        })

    # Broadcast so other devices know a channel item is now available
    await pair_ws_manager.broadcast_to_devices({"event": "new_task_available"})
    # 通知前端任务列表更新
    await pair_ws_manager.broadcast_to_admins({
        "event": "task_updated",
        "task_id": task.id,
        "status": "cancelled",
    })

    return task


@router.delete("/{task_id}")
async def delete_task(task_id: str, db=Depends(get_db), _=Depends(verify_admin_token)):
    try:
        task_service.delete_task(db=db, task_id=task_id)
    except ValueError as e:
        if "not found" in str(e): raise HTTPException(status_code=404, detail="Task not found")
        raise HTTPException(status_code=400, detail=str(e))
    # 通知前端
    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_admins({"event": "tasks_changed"})
    return {"deleted": True, "task_id": task_id}
```

## app/routers/videos.py

```python
"""Video management API — admin endpoints."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_admin_token, verify_ws_admin_token
from app.db_models import GeneratedVideo

router = APIRouter(prefix="/api/videos", tags=["videos"])


class VideoResponse(BaseModel):
    id: str
    task_id: Optional[str] = None
    keyword: str
    title: Optional[str] = None
    video_path: Optional[str] = None
    duration: Optional[float] = None
    status: str
    pixelle_task_id: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class VideoListResponse(BaseModel):
    items: list[VideoResponse]
    total: int


@router.get("", response_model=VideoListResponse)
def list_videos(
    keyword: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    query = db.query(GeneratedVideo)
    if keyword:
        query = query.filter(GeneratedVideo.keyword == keyword)
    if status:
        query = query.filter(GeneratedVideo.status == status)
    query = query.order_by(GeneratedVideo.created_at.desc())
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return {"items": items, "total": total}


@router.get("/{video_id}", response_model=VideoResponse)
def get_video(
    video_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    video = db.query(GeneratedVideo).filter(GeneratedVideo.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    return video


@router.get("/{video_id}/download")
def download_video(
    video_id: str,
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    # Browser-native elements (<video>, <a>) can't set headers — accept query token as fallback
    username = None
    if authorization and authorization.startswith("Bearer "):
        try:
            import jwt
            from app.config import JWT_SECRET
            payload = jwt.decode(authorization[7:], JWT_SECRET, algorithms=["HS256"])
            username = payload["sub"]
        except Exception:
            pass
    if not username and token:
        result = verify_ws_admin_token(token)
        username = result[0] if result[0] else None
    if not username:
        raise HTTPException(status_code=401, detail="请先登录")

    video = db.query(GeneratedVideo).filter(GeneratedVideo.id == video_id).first()
    if not video or not video.video_path:
        raise HTTPException(status_code=404, detail="视频文件不存在")

    filepath = Path(video.video_path)
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="视频文件已被删除")

    return FileResponse(str(filepath), media_type="video/mp4", filename=filepath.name)


@router.delete("/{video_id}")
def delete_video(
    video_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    video = db.query(GeneratedVideo).filter(GeneratedVideo.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    if video.video_path:
        filepath = Path(video.video_path)
        if filepath.exists():
            filepath.unlink()

    db.delete(video)
    db.commit()
    return {"deleted": True, "id": video_id}
```

## app/services/ai_generator.py

```python
"""AI content generation service -- calls external LLM API with sensitive word filtering."""
import json
import logging
from typing import Any

import httpx

from app.config import AI_MAX_RETRIES
from app.services.content_service import content_service

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个抖音评论/私信内容生成助手。根据给定的模板和上下文，生成自然、友好的中文内容。
规则：
1. 保持内容自然，像真人写的
2. 不要包含广告、链接、联系方式
3. 不要包含敏感、违规、政治相关内容
4. 内容长度控制在 20-100 字
5. 直接输出生成的内容，不要加引号或解释"""


class AiGeneratorService:
    """Generates content via external LLM API with sensitive word filtering.

    Supports two providers via AI_PROVIDER config:
    - "anthropic": Uses Anthropic Messages API (x-api-key header, /v1/messages)
    - "openai": Uses OpenAI-compatible API (Authorization Bearer, /v1/chat/completions)
    """

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Lazy-init httpx client with separated connect/read timeouts."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)
            )
        return self._client

    async def aclose(self):
        """Close the httpx client. Call during app shutdown."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def generate(
        self,
        db,
        template_body: str,
        context: dict[str, Any],
    ) -> str:
        """Generate content from template + context. Retries if sensitive words detected.

        Args:
            db: SQLAlchemy session (for sensitive word lookup and config)
            template_body: Template text with {variable} placeholders already substituted
            context: Additional context for the AI prompt

        Returns:
            Generated content string

        Raises:
            RuntimeError: If AI API is not configured or all retries fail
            ValueError: If all retries produce sensitive content
        """
        from app.config import get_ai_config_with_key
        ai_cfg = get_ai_config_with_key(db)
        if not ai_cfg or not ai_cfg.get("api_key"):
            raise RuntimeError("AI API not configured. Set AI_API_KEY env var or save in Settings page.")

        user_prompt = self._build_prompt(template_body, context)

        for attempt in range(AI_MAX_RETRIES):
            try:
                content = await self._call_api(ai_cfg, user_prompt)
            except httpx.HTTPError as e:
                logger.warning("AI API call failed (attempt %d/%d): %s", attempt + 1, AI_MAX_RETRIES, e)
                if attempt == AI_MAX_RETRIES - 1:
                    raise RuntimeError(f"AI API failed after {AI_MAX_RETRIES} attempts: {e}") from e
                continue

            if db and content_service.contains_sensitive(db, content):
                logger.info("Generated content contains sensitive words, retrying (%d/%d)", attempt + 1, AI_MAX_RETRIES)
                if attempt == AI_MAX_RETRIES - 1:
                    raise ValueError("All generated content contained sensitive words after max retries")
                continue

            return content

    async def generate_custom_stream(
        self, db, system_prompt: str, user_prompt: str,
        max_tokens: int = 4096, temperature: float = 0.7,
    ):
        """Generate content with streaming — yields text chunks as they arrive from the AI API.
        Only supports OpenAI-compatible streaming (DeepSeek, OpenAI, etc.).
        Anthropic streaming not yet implemented.
        """
        from app.config import get_ai_config_with_key, AI_MAX_RETRIES
        ai_cfg = get_ai_config_with_key(db)
        if not ai_cfg or not ai_cfg.get("api_key"):
            raise RuntimeError("AI API not configured")

        api_url = ai_cfg.get("api_url", "")
        client = self._get_client()

        for attempt in range(max(1, AI_MAX_RETRIES)):
            try:
                async with client.stream(
                    "POST",
                    api_url,
                    headers={
                        "Authorization": f"Bearer {ai_cfg['api_key']}",
                        "content-type": "application/json",
                    },
                    json={
                        "model": ai_cfg.get("model", "deepseek-chat"),
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "stream": True,
                        **({} if not ai_cfg.get("thinking_enabled") else {"thinking": {"type": "enabled"}}),
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    },
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            return
                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
                    return  # stream completed
            except httpx.HTTPError as e:
                logger.warning(
                    "generate_custom_stream API call failed (attempt %d/%d): %s",
                    attempt + 1, AI_MAX_RETRIES, e,
                )
                if attempt == AI_MAX_RETRIES - 1:
                    raise RuntimeError(
                        f"generate_custom_stream failed after {AI_MAX_RETRIES} attempts: {e}"
                    ) from e
                continue

    async def generate_custom(
        self, db, system_prompt: str, user_prompt: str,
        max_tokens: int = 4096, temperature: float = 0.7,
        thinking_enabled: bool = None,
    ) -> str:
        """Generate content with custom system prompt and parameters. No sensitive word filtering.

        Args:
            thinking_enabled: If not None, overrides the global AI thinking config.
        """
        from app.config import get_ai_config_with_key, AI_MAX_RETRIES
        ai_cfg = get_ai_config_with_key(db)
        if not ai_cfg or not ai_cfg.get("api_key"):
            raise RuntimeError("AI API not configured")

        use_thinking = ai_cfg.get("thinking_enabled") if thinking_enabled is None else thinking_enabled

        api_url = ai_cfg.get("api_url", "")
        client = self._get_client()
        is_anthropic = "/v1/messages" in api_url

        for attempt in range(max(1, AI_MAX_RETRIES)):
            try:
                if is_anthropic:
                    base_url = api_url.rstrip("/").rsplit("/v1/messages", 1)[0]
                    response = await client.post(
                        f"{base_url}/v1/messages",
                        headers={
                            "x-api-key": ai_cfg["api_key"],
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json={
                            "model": ai_cfg.get("model", "claude-3-haiku-20240307"),
                            "max_tokens": max_tokens,
                            **({} if not use_thinking else {"thinking": {"type": "enabled", "budget_tokens": ai_cfg.get("thinking_budget", 8192)}}),
                            "system": system_prompt,
                            "messages": [{"role": "user", "content": user_prompt}],
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                    return data["content"][0]["text"].strip()
                else:
                    response = await client.post(
                        api_url,
                        headers={
                            "Authorization": f"Bearer {ai_cfg['api_key']}",
                            "content-type": "application/json",
                        },
                        json={
                            "model": ai_cfg.get("model", "deepseek-chat"),
                            "max_tokens": max_tokens,
                            "temperature": temperature,
                            **({} if not use_thinking else {"thinking": {"type": "enabled"}}),
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                    return data["choices"][0]["message"]["content"].strip()
            except httpx.HTTPError as e:
                logger.warning("generate_custom API call failed (attempt %d/%d): %s", attempt + 1, AI_MAX_RETRIES, e)
                if attempt == AI_MAX_RETRIES - 1:
                    raise RuntimeError(f"generate_custom failed after {AI_MAX_RETRIES} attempts: {e}") from e
                continue

    async def _call_api(self, cfg: dict, user_prompt: str) -> str:
        """Call the AI API and return the generated text. Dispatches by provider."""
        api_url = cfg.get("api_url", "")
        # Anthropic uses /v1/messages; OpenAI-compatible uses /v1/chat/completions
        if "/v1/messages" in api_url:
            return await self._call_anthropic(cfg, user_prompt)
        return await self._call_openai(cfg, user_prompt)

    async def _call_anthropic(self, cfg: dict, user_prompt: str) -> str:
        """Call Anthropic Messages API."""
        client = self._get_client()
        base_url = cfg["api_url"].rstrip("/").rsplit("/v1/messages", 1)[0]
        response = await client.post(
            f"{base_url}/v1/messages",
            headers={
                "x-api-key": cfg["api_key"],
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": cfg.get("model", "claude-3-haiku-20240307"),
                "max_tokens": 512,
                **({} if not cfg.get("thinking_enabled") else {"thinking": {"type": "enabled", "budget_tokens": cfg.get("thinking_budget", 8192)}}),
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_prompt}],
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"].strip()

    async def _call_openai(self, cfg: dict, user_prompt: str) -> str:
        """Call OpenAI-compatible Chat Completions API."""
        client = self._get_client()
        response = await client.post(
            cfg["api_url"],
            headers={
                "Authorization": f"Bearer {cfg['api_key']}",
                "content-type": "application/json",
            },
            json={
                "model": cfg.get("model", "deepseek-chat"),
                "max_tokens": 512,
                **({} if not cfg.get("thinking_enabled") else {"thinking": {"type": "enabled"}}),
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    @staticmethod
    def _build_prompt(template_body: str, context: dict[str, Any]) -> str:
        """Build the user prompt from template and context.

        Dynamically includes all context keys that have values,
        rather than hardcoding specific field names.
        """
        parts = [f"模板内容：{template_body}"]

        # Dynamic context — include all non-empty string values
        key_labels = {
            "keyword": "搜索关键词",
            "username": "目标用户",
            "video_title": "视频标题",
        }
        for key, value in context.items():
            if isinstance(value, str) and value:
                label = key_labels.get(key, key)
                parts.append(f"{label}：{value}")

        parts.append("请根据以上信息生成一条自然的评论/私信内容。只输出内容本身。")
        return "\n".join(parts)


ai_generator = AiGeneratorService()
```

## app/services/chain_service.py

```python
"""Chain orchestration service — step-by-step task release."""
import asyncio
import logging
import threading
from datetime import datetime, timezone
from app.config import bj_now
from typing import Optional

from sqlalchemy.orm import Session

from app.db_models import (
    ChainTemplate, ChainInstance, Task as DBTask, Device, Account,
    AccountGroupMember,
)
from app.models import TaskType

logger = logging.getLogger(__name__)

# Thread lock for mutual exclusion checks (TOCTOU prevention)
_account_lock = threading.Lock()

VALID_STEP_TYPES = {t.value for t in TaskType}


class ChainService:
    def is_account_busy(self, db: Session, account_id: str) -> bool:
        """Check if account has pending or running tasks."""
        count = db.query(DBTask).filter(
            DBTask.account_id == account_id,
            DBTask.status.in_(["pending", "running"]),
        ).count()
        return count > 0

    def create_chain_instances(
        self,
        db: Session,
        template_id: str,
        account_ids: list[str],
        device_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> dict:
        """Create chain instances for each account, skipping busy ones.

        Uses a thread lock to prevent TOCTOU race on is_account_busy check.
        """
        template = db.query(ChainTemplate).filter(ChainTemplate.id == template_id).first()
        if not template:
            raise ValueError("模板不存在")

        # Validate step types in template
        for step in template.steps:
            if step.get("type") not in VALID_STEP_TYPES:
                raise ValueError(f"模板包含无效的步骤类型: {step.get('type')}")

        total_steps = len(template.steps)
        results = {"created": [], "skipped_busy": [], "skipped_error": []}

        with _account_lock:
            for account_id in account_ids:
                account = db.query(Account).filter(Account.id == account_id).first()
                if not account:
                    results["skipped_error"].append(account_id)
                    continue

                if self.is_account_busy(db, account_id):
                    results["skipped_busy"].append(account_id)
                    continue

                instance = ChainInstance(
                    template_id=template_id,
                    account_id=account_id,
                    device_id=device_id,
                    user_id=user_id,
                    current_step=1,
                    total_steps=total_steps,
                    status="pending",
                )
                db.add(instance)
                db.flush()

                self._create_step_task(db, instance, 1, template)
                instance.status = "running"
                instance.started_at = bj_now()
                results["created"].append(account_id)

            db.commit()

        self._safe_push_pending_tasks(db, results["created"])

        return results

    def resolve_accounts_from_groups(self, db: Session, group_ids: list[str], user_id: Optional[str] = None) -> list[str]:
        """Expand group IDs to unique active account IDs, optionally scoped to user."""
        query = (
            db.query(AccountGroupMember.account_id)
            .join(Account, Account.id == AccountGroupMember.account_id)
            .filter(
                AccountGroupMember.group_id.in_(group_ids),
                Account.status == "active",
            )
        )
        if user_id:
            query = query.filter(Account.user_id == user_id)
        account_ids = query.distinct().all()
        return [a[0] for a in account_ids]

    def advance_chain(self, db: Session, task_id: str, status: str, result: dict = None):
        """Advance chain to next step after task completion/failure.

        Uses flush (not commit) — caller is responsible for the final commit.
        """
        task = db.query(DBTask).filter(DBTask.id == task_id).first()
        if not task or not task.chain_instance_id:
            return

        chain = db.query(ChainInstance).filter(
            ChainInstance.id == task.chain_instance_id
        ).first()
        if not chain:
            return

        if status == "completed":
            next_step = task.step_order + 1
            if next_step > chain.total_steps:
                chain.status = "completed"
                chain.completed_at = bj_now()
            else:
                chain.current_step = next_step
                chain.status = "running"
                if not chain.started_at:
                    chain.started_at = bj_now()
                template = db.query(ChainTemplate).filter(ChainTemplate.id == chain.template_id).first()
                if template:
                    self._create_step_task(db, chain, next_step, template)
                    db.flush()
                    self._safe_push_step_task(db, chain)
        elif status == "failed":
            chain.status = "failed"
            chain.completed_at = bj_now()

        # Do NOT commit here — caller (report_result) handles the commit

    def _create_step_task(self, db: Session, chain: ChainInstance, step_order: int, template: ChainTemplate):
        """Create a Task for the given step. Caller is responsible for commit/flush."""
        step = next((s for s in template.steps if s["step_order"] == step_order), None)
        if not step:
            raise ValueError(f"Step {step_order} not found in template")

        step_type = step.get("type")
        if step_type not in VALID_STEP_TYPES:
            raise ValueError(f"无效的步骤类型: {step_type}")

        task = DBTask(
            type=step_type,
            account_id=chain.account_id,
            device_id=chain.device_id,
            user_id=chain.user_id,
            params=step.get("params", {}),
            status="pending",
            chain_instance_id=chain.id,
            step_order=step_order,
        )
        db.add(task)

    def _safe_push_pending_tasks(self, db: Session, account_ids: list[str]):
        """Push pending tasks for chain instances to devices.

        Uses chain's device_id if set, otherwise falls back to account-bound device.
        Safe for both sync and async contexts.
        """
        from app.ws_manager import pair_ws_manager

        for account_id in account_ids:
            task = (
                db.query(DBTask)
                .filter(DBTask.account_id == account_id, DBTask.status == "pending", DBTask.chain_instance_id.isnot(None))
                .order_by(DBTask.created_at.desc())
                .first()
            )
            if not task:
                continue

            # Use task's device_id (set from chain instance) or find bound device
            target_device_id = task.device_id
            if not target_device_id:
                device = db.query(Device).filter(Device.bound_account_id == account_id).first()
                if not device:
                    continue
                target_device_id = device.id

            self._schedule_push(target_device_id, {
                "event": "task",
                "task": _task_to_push_dict(task),
            })

    def _safe_push_step_task(self, db: Session, chain: ChainInstance):
        """Push the current step task to the device.

        Uses chain's device_id if set, otherwise falls back to account-bound device.
        Safe for both sync and async contexts.
        """
        from app.ws_manager import pair_ws_manager

        task = (
            db.query(DBTask)
            .filter(DBTask.chain_instance_id == chain.id, DBTask.status == "pending")
            .order_by(DBTask.step_order.desc())
            .first()
        )
        if not task:
            return

        target_device_id = chain.device_id
        if not target_device_id:
            device = db.query(Device).filter(Device.bound_account_id == chain.account_id).first()
            if not device:
                return
            target_device_id = device.id

        self._schedule_push(target_device_id, {
            "event": "task",
            "task": _task_to_push_dict(task),
        })

    @staticmethod
    def _schedule_push(device_id: str, data: dict):
        """Schedule a WS push, safe for both sync and async call sites."""
        from app.ws_manager import pair_ws_manager

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(pair_ws_manager.send_to_device(device_id, data))
        except RuntimeError:
            # No running event loop — fire and forget via a new thread
            def _push():
                try:
                    asyncio.run(pair_ws_manager.send_to_device(device_id, data))
                except Exception as e:
                    logger.warning("WS push failed for device %s: %s", device_id, e)
            threading.Thread(target=_push, daemon=True).start()


def _task_to_push_dict(task: DBTask) -> dict:
    return {
        "id": task.id,
        "type": task.type,
        "account_id": task.account_id,
        "device_id": task.device_id or "",
        "params": task.params or {},
        "status": task.status,
        "chain_instance_id": task.chain_instance_id,
        "step_order": task.step_order,
    }


chain_service = ChainService()
```

## app/services/channel_service.py

```python
"""Channel service -- create, claim, complete, stale recovery, risk control."""
from datetime import datetime, timezone
from app.config import bj_now
from typing import Optional

from sqlalchemy import update, and_, exists, select
from sqlalchemy.orm import Session

from app.db_models import (
    Channel, ChannelItem, Account, AccountGroup, AccountGroupMember,
    Task as DBTask, Device as DBDevice,
)
from app.models import TaskStatus


MAX_KEYWORDS = 500


def _get_active_accounts(db: Session, group_id: str) -> list[Account]:
    """Get active accounts in a group."""
    members = db.query(AccountGroupMember).filter(
        AccountGroupMember.group_id == group_id
    ).all()
    account_ids = [m.account_id for m in members]
    if not account_ids:
        return []
    accounts = db.query(Account).filter(
        Account.id.in_(account_ids),
        Account.status == "active",
    ).all()
    return accounts


class ChannelService:

    def create_channel(
        self,
        db: Session,
        group_id: str,
        task_type: str,
        account_mode: str,
        keywords: list[str],
        params_template: dict,
        account_id: Optional[str] = None,
        cooldown_seconds: int = 300,
        delay_range: list[int] = None,
        user_id: Optional[str] = None,
    ) -> Channel:
        if len(keywords) > MAX_KEYWORDS:
            raise ValueError(f"关键词最多 {MAX_KEYWORDS} 个，当前 {len(keywords)} 个")

        if delay_range is None:
            delay_range = [3000, 8000]

        # Validate group exists
        group = db.query(AccountGroup).filter(AccountGroup.id == group_id).first()
        if not group:
            raise ValueError(f"分组 {group_id} 不存在")

        # Get active accounts for distribution
        active_accounts = _get_active_accounts(db, group_id)
        if not active_accounts:
            raise ValueError("该分组内没有活跃账号")

        if account_mode == "single_account":
            if not account_id:
                raise ValueError("single_account 模式下 account_id 必填")
            acc = db.query(Account).filter(
                Account.id == account_id, Account.status == "active"
            ).first()
            if not acc:
                raise ValueError(f"账号 {account_id} 不存在或非 active 状态")
            item_accounts = [account_id] * len(keywords)
        else:
            item_accounts = self._round_robin_assign(db, keywords, active_accounts)

        ch = Channel(
            group_id=group_id,
            task_type=task_type,
            status="active",
            account_mode=account_mode,
            account_id=account_id,
            user_id=user_id,
            params_template=params_template,
            cooldown_seconds=cooldown_seconds,
            delay_range=delay_range,
            max_keywords=MAX_KEYWORDS,
        )
        db.add(ch)
        db.flush()

        for i, keyword in enumerate(keywords):
            item = ChannelItem(
                channel_id=ch.id,
                keyword=keyword,
                account_id=item_accounts[i],
                status="pending",
                queue_position=i,
            )
            db.add(item)

        db.commit()
        db.refresh(ch)
        return ch

    def _round_robin_assign(
        self, db: Session, keywords: list[str], accounts: list[Account]
    ) -> list[str]:
        """Assign accounts to keywords using round-robin, preferring least-used today."""
        if not accounts:
            raise ValueError("无可用账号")

        from app.services.stats_service import stats_service

        account_usage = []
        for acc in accounts:
            counts = stats_service.get_today_counts(db, acc.id)
            total = sum(counts.values())
            account_usage.append((acc, total))
        account_usage.sort(key=lambda x: x[1])

        sorted_accounts = [acc for acc, _ in account_usage]
        result = []
        for i in range(len(keywords)):
            acc = sorted_accounts[i % len(sorted_accounts)]
            result.append(acc.id)
        return result

    def claim_channel_item(self, db: Session, device_id: str):
        """Claim a pending channel item. Returns (PydanticTask, channel_item_id) or None."""
        from app.services.task_service import _db_task_to_pydantic
        from app.services.stats_service import stats_service
        from app.models import TaskType, TaskStatus

        now = bj_now()

        # Stale recovery: reset items assigned > 5 min ago
        # Skip items whose device is still online (slow but alive).
        # Also reset the associated RUNNING task to PENDING to prevent
        # duplicate execution when the item is re-claimed.
        from datetime import timedelta
        stale_threshold = now - timedelta(seconds=300)
        online_threshold = now - timedelta(seconds=120)
        online_device_ids = {
            d[0] for d in db.query(DBDevice.id).filter(
                DBDevice.last_seen_at.isnot(None),
                DBDevice.last_seen_at >= online_threshold,
            ).all()
        }
        stale_items = db.query(ChannelItem).filter(
            ChannelItem.status == "assigned",
            ChannelItem.assigned_at.isnot(None),
            ChannelItem.assigned_at < stale_threshold,
            ~ChannelItem.assigned_device_id.in_(online_device_ids),
        ).all()
        stale_channel_ids = set()
        stale_task_ids = []
        for si in stale_items:
            if si.task_id:
                stale_task_ids.append(si.task_id)
            si.status = "pending"
            si.assigned_device_id = None
            si.assigned_at = None
            si.task_id = None
            stale_channel_ids.add(si.channel_id)
        if stale_items:
            db.flush()
            # Reset orphaned RUNNING tasks so they don't linger for 10 min
            if stale_task_ids:
                from app.models import TaskStatus as TS
                db.query(DBTask).filter(
                    DBTask.id.in_(stale_task_ids),
                    DBTask.status == TS.RUNNING.value,
                ).update(
                    {"status": TS.PENDING.value, "device_id": None, "started_at": None},
                    synchronize_session=False,
                )
            for cid in stale_channel_ids:
                self._reactivate_channel(db, cid)
        db.expire_all()

        # Build routing filter based on device's bound_account_id
        device = db.query(DBDevice).filter(DBDevice.id == device_id).first()
        bound_account_id = device.bound_account_id if device else None
        device_user_id = device.user_id if device else None

        # Find active channels with pending items, scoped to device's user
        channel_query = db.query(Channel).filter(
            Channel.status == "active",
            Channel.deleted_at.is_(None),
        )
        if device_user_id:
            from sqlalchemy import or_ as ch_or
            channel_query = channel_query.filter(
                ch_or(Channel.user_id == device_user_id, Channel.user_id.is_(None))
            )
        active_channels = channel_query.all()

        # Self-heal: re-activate completed/cancelled channels that still have pending items
        stuck_query = db.query(Channel).filter(
            Channel.status.in_(["completed", "cancelled"]),
            Channel.deleted_at.is_(None),
        )
        if device_user_id:
            from sqlalchemy import or_ as ch_or2
            stuck_query = stuck_query.filter(
                ch_or2(Channel.user_id == device_user_id, Channel.user_id.is_(None))
            )
        stuck_channels = stuck_query.all()
        for sc in stuck_channels:
            has_pending = db.query(ChannelItem).filter(
                ChannelItem.channel_id == sc.id,
                ChannelItem.status.in_(["pending", "assigned"]),
            ).first()
            if has_pending:
                sc.status = "active"
                sc.completed_at = None
                active_channels.append(sc)
        if stuck_channels:
            db.flush()

        if not active_channels:
            return None

        channel_ids = [ch.id for ch in active_channels]
        channel_map = {ch.id: ch for ch in active_channels}

        # Build candidate query with account routing

        # Get pending items from active channels
        query = db.query(ChannelItem).filter(
            ChannelItem.channel_id.in_(channel_ids),
            ChannelItem.status == "pending",
        )
        if bound_account_id:
            query = query.filter(ChannelItem.account_id == bound_account_id)
        else:
            # Unbound device: exclude accounts bound to other devices
            bound_ids_subq = select(DBDevice.bound_account_id).where(
                DBDevice.bound_account_id.isnot(None)
            )
            query = query.filter(~ChannelItem.account_id.in_(bound_ids_subq))

        candidates = query.order_by(ChannelItem.queue_position.asc()).limit(50).all()

        for item in candidates:
            ch = channel_map[item.channel_id]

            # Filter: account must be active
            account = db.query(Account).filter(Account.id == item.account_id).first()
            if not account or account.status != "active":
                continue

            # Filter: per-account concurrency (check both ChannelItem and Task tables)
            running_item = db.query(ChannelItem).filter(
                ChannelItem.account_id == item.account_id,
                ChannelItem.status == "assigned",
                ChannelItem.channel_id.in_(channel_ids),
            ).first()
            if running_item:
                continue

            running_task = db.query(DBTask).filter(
                DBTask.account_id == item.account_id,
                DBTask.status == TaskStatus.RUNNING.value,
            ).first()
            if running_task:
                continue

            # Filter: cooldown（同一设备刚完成的不受限，反检测已控制节奏）
            last_completed = db.query(ChannelItem).filter(
                ChannelItem.account_id == item.account_id,
                ChannelItem.status == "completed",
                ChannelItem.completed_at.isnot(None),
            ).order_by(ChannelItem.completed_at.desc()).first()
            if last_completed and ch.cooldown_seconds > 0:
                same_device = last_completed.assigned_device_id == device_id
                if not same_device:
                    elapsed = (now - last_completed.completed_at.replace(tzinfo=None)).total_seconds()
                    if elapsed < ch.cooldown_seconds:
                        continue

            # Filter: daily quota（reply_comment 只在 reply 配额耗尽时阻塞，follow/DM 由 handler 优雅降级）
            if not stats_service.check_quota(db, item.account_id, ch.task_type):
                continue

            # Optimistic lock: claim the item
            result = db.execute(
                update(ChannelItem)
                .where(ChannelItem.id == item.id, ChannelItem.status == "pending")
                .values(
                    status="assigned",
                    assigned_device_id=device_id,
                    assigned_at=now,
                )
            )
            if result.rowcount == 0:
                continue

            # Flush-only Task creation (no commit)
            # Task is created as RUNNING to prevent get_pending_task from stealing it
            params = dict(ch.params_template or {})
            params["keyword"] = item.keyword
            # Resolve dm_sequence_id into inline dm_messages (keep id for device cache/variants)
            seq_id = params.get("dm_sequence_id")
            if seq_id:
                try:
                    from app.db_models import DMSequence
                    seq = db.query(DMSequence).filter(DMSequence.id == seq_id).first()
                    if seq and seq.messages:
                        params["dm_messages"] = seq.messages
                        first = seq.messages[0]
                        if isinstance(first, dict):
                            params["content"] = first.get("content", "")
                    else:
                        params.pop("dm_sequence_id", None)
                except Exception:
                    params.pop("dm_sequence_id", None)

            # Resolve content_template_id with the item's keyword (sync, no AI)
            template_id = params.pop("content_template_id", None)
            if template_id:
                try:
                    from app.services.content_service import content_service as cs
                    tpl_body = cs.get_template_body(db, template_id)
                    if tpl_body:
                        params["content"] = cs.substitute_variables(
                            tpl_body, {"keyword": item.keyword}
                        )
                except Exception:
                    pass
            # 注入账号配额和服务端每日计数（设备端日志和服务端同步）
            if ch.task_type == "reply_comment":
                remaining = stats_service.get_remaining_quotas(db, item.account_id)
                limits = stats_service._get_limits(db, item.account_id)
                today_counts = stats_service.get_today_counts(db, item.account_id)
                if "max_follows" not in params:
                    params["max_follows"] = remaining.get("follows", 20)
                if "max_dms" not in params:
                    params["max_dms"] = remaining.get("dms", 10)
                # 服务端每日配额上限（-1=不限）
                params["server_daily_limit_reply"] = limits.get("replies", 200)
                params["server_daily_limit_follow"] = limits.get("follows", 100)
                params["server_daily_limit_dm"] = limits.get("dms", 75)
                # 服务端今日已完成计数
                params["server_today_reply"] = today_counts.get("replies", 0)
                params["server_today_follow"] = today_counts.get("follows", 0)
                params["server_today_dm"] = today_counts.get("dms", 0)
            task = DBTask(
                type=ch.task_type,
                account_id=item.account_id,
                device_id=device_id,
                user_id=ch.user_id,
                params=params,
                status=TaskStatus.RUNNING.value,
                started_at=now,
            )
            db.add(task)
            db.flush()

            item.task_id = task.id
            db.flush()

            return (_db_task_to_pydantic(task), item.id)

        return None

    def complete_item(self, db: Session, item_id: str, status: str) -> dict:
        """Complete a channel item and check if channel is fully done.

        Returns {"channel_id": str, "stats": dict, "channel_completed": bool}
        for the caller to handle WS broadcast.
        """
        item = db.query(ChannelItem).filter(ChannelItem.id == item_id).first()
        if not item:
            return {}

        channel_id = item.channel_id

        item.status = status
        item.completed_at = bj_now()
        db.flush()

        channel_completed = False

        # Atomic completion check
        if status in ("completed", "failed"):
            db.execute(
                update(Channel)
                .where(
                    Channel.id == channel_id,
                    Channel.status == "active",
                    ~exists().where(
                        and_(
                            ChannelItem.channel_id == channel_id,
                            ChannelItem.status.notin_(["completed", "failed", "skipped"]),
                        )
                    ),
                )
                .values(status="completed", completed_at=bj_now())
            )
            db.flush()
            db.expire_all()
            ch = db.query(Channel).filter(Channel.id == channel_id).first()
            channel_completed = ch.status == "completed" if ch else False

        stats = self.get_channel_stats(db, channel_id)
        return {"channel_id": channel_id, "stats": stats, "channel_completed": channel_completed}

    def on_risk_control(self, db: Session, account_id: str):
        """Skip all pending channel items for a risk-controlled account."""
        db.execute(
            update(ChannelItem)
            .where(
                ChannelItem.account_id == account_id,
                ChannelItem.status == "pending",
            )
            .values(status="skipped", completed_at=bj_now())
        )
        db.flush()
        db.expire_all()

    def update_channel_status(self, db: Session, channel_id: str, new_status: str, user_id: Optional[str] = None):
        """Update channel status with validation."""
        ch = self.get_channel(db, channel_id, user_id=user_id)
        if not ch:
            raise ValueError(f"通道 {channel_id} 不存在")

        valid_transitions = {
            "active": ["paused", "cancelled"],
            "paused": ["active", "cancelled"],
        }
        allowed = valid_transitions.get(ch.status, [])
        if new_status not in allowed:
            raise ValueError(f"不允许从 {ch.status} 转换到 {new_status}")

        ch.status = new_status
        if new_status == "cancelled":
            db.execute(
                update(ChannelItem)
                .where(
                    ChannelItem.channel_id == channel_id,
                    ChannelItem.status == "pending",
                )
                .values(status="skipped", completed_at=bj_now())
            )
        db.commit()

    def soft_delete_channel(self, db: Session, channel_id: str, user_id: Optional[str] = None):
        """Soft delete a channel."""
        ch = self.get_channel(db, channel_id, user_id=user_id)
        if not ch:
            raise ValueError(f"通道 {channel_id} 不存在")
        ch.deleted_at = bj_now()
        db.execute(
            update(ChannelItem)
            .where(
                ChannelItem.channel_id == channel_id,
                ChannelItem.status == "pending",
            )
            .values(status="skipped", completed_at=bj_now())
        )
        db.commit()

    def append_items(self, db: Session, channel_id: str, keywords: list[str], user_id: Optional[str] = None):
        """Append new keywords to an active channel."""
        ch = self.get_channel(db, channel_id, user_id=user_id)
        if not ch:
            raise ValueError(f"通道 {channel_id} 不存在")
        if ch.status != "active":
            raise ValueError("只能向活跃通道追加关键词")

        existing_count = db.query(ChannelItem).filter(ChannelItem.channel_id == channel_id).count()
        if existing_count + len(keywords) > ch.max_keywords:
            raise ValueError(f"超出最大关键词数 {ch.max_keywords}")

        if ch.account_mode == "single_account":
            account_ids = [ch.account_id] * len(keywords)
        else:
            active_accounts = _get_active_accounts(db, ch.group_id)
            account_ids = self._round_robin_assign(db, keywords, active_accounts)

        for i, keyword in enumerate(keywords):
            item = ChannelItem(
                channel_id=channel_id,
                keyword=keyword,
                account_id=account_ids[i],
                status="pending",
                queue_position=existing_count + i,
            )
            db.add(item)
        db.commit()

    def _reactivate_channel(self, db: Session, channel_id: str):
        """If channel is completed/cancelled but now has pending items, revert to active."""
        ch = db.query(Channel).filter(Channel.id == channel_id).first()
        if ch and ch.status in ("completed", "cancelled"):
            ch.status = "active"
            ch.completed_at = None
            db.flush()

    def edit_channel(
        self,
        db: Session,
        channel_id: str,
        group_id: Optional[str] = None,
        account_mode: Optional[str] = None,
        account_id: Optional[str] = None,
        params_template: Optional[dict] = None,
        cooldown_seconds: Optional[int] = None,
        sync_to_items: bool = False,
        user_id: Optional[str] = None,
    ) -> Channel:
        """Edit channel metadata. Only active/paused channels allowed."""
        ch = self.get_channel(db, channel_id, user_id=user_id)
        if not ch:
            raise ValueError(f"通道 {channel_id} 不存在")
        if ch.status not in ("active", "paused"):
            raise ValueError("只能编辑活跃或暂停状态的通道")

        if all(v is None for v in (group_id, account_mode, account_id, params_template, cooldown_seconds)):
            raise ValueError("至少提供一个要修改的字段")

        if group_id is not None:
            group = db.query(AccountGroup).filter(AccountGroup.id == group_id).first()
            if not group:
                raise ValueError(f"分组 {group_id} 不存在")
            ch.group_id = group_id

        if account_mode is not None:
            ch.account_mode = account_mode

        if account_id is not None:
            acc = db.query(Account).filter(Account.id == account_id, Account.status == "active").first()
            if not acc:
                raise ValueError(f"账号 {account_id} 不存在或非 active 状态")
            effective_group_id = group_id if group_id is not None else ch.group_id
            member = db.query(AccountGroupMember).filter(
                AccountGroupMember.group_id == effective_group_id,
                AccountGroupMember.account_id == account_id,
            ).first()
            if not member:
                raise ValueError(f"账号 {account_id} 不属于分组 {effective_group_id}")
            ch.account_id = account_id

        if params_template is not None:
            ch.params_template = params_template

        if cooldown_seconds is not None:
            ch.cooldown_seconds = cooldown_seconds

        # Sync to pending/assigned items when requested
        if sync_to_items:
            if account_id is not None:
                db.query(ChannelItem).filter(
                    ChannelItem.channel_id == channel_id,
                    ChannelItem.status.in_(["pending", "assigned"]),
                ).update({"account_id": account_id}, synchronize_session=False)
            elif group_id is not None and ch.account_mode == "round_robin":
                active_accounts = _get_active_accounts(db, ch.group_id)
                if active_accounts:
                    pending_items = db.query(ChannelItem).filter(
                        ChannelItem.channel_id == channel_id,
                        ChannelItem.status.in_(["pending", "assigned"]),
                    ).order_by(ChannelItem.queue_position).all()
                    account_ids = self._round_robin_assign(
                        db, [i.keyword for i in pending_items], active_accounts
                    )
                    with db.begin_nested():
                        for i, item in enumerate(pending_items):
                            item.account_id = account_ids[i]

        db.commit()
        db.refresh(ch)
        return ch

    def edit_item(
        self,
        db: Session,
        item_id: str,
        account_id: Optional[str] = None,
        assigned_device_id: Optional[str] = None,
        keyword: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> ChannelItem:
        """Edit a single channel item. Only pending items allowed."""
        item = db.query(ChannelItem).filter(ChannelItem.id == item_id).first()
        if not item:
            raise ValueError(f"Item {item_id} 不存在")
        if user_id:
            ch = db.query(Channel).filter(Channel.id == item.channel_id, Channel.user_id == user_id).first()
            if not ch:
                raise ValueError(f"Item {item_id} 不属于当前用户")
        if item.status != "pending":
            raise ValueError("只能编辑待处理的子项")

        if account_id is not None:
            acc = db.query(Account).filter(Account.id == account_id, Account.status == "active").first()
            if not acc:
                raise ValueError(f"账号 {account_id} 不存在或非 active 状态")
            ch = db.query(Channel).filter(
                Channel.id == item.channel_id,
                Channel.deleted_at.is_(None),
            ).first()
            if ch:
                member = db.query(AccountGroupMember).filter(
                    AccountGroupMember.group_id == ch.group_id,
                    AccountGroupMember.account_id == account_id,
                ).first()
                if not member:
                    raise ValueError(f"账号 {account_id} 不属于通道分组 {ch.group_id}")
            item.account_id = account_id

        if assigned_device_id is not None:
            dev = db.query(DBDevice).filter(DBDevice.id == assigned_device_id).first()
            if not dev:
                raise ValueError(f"设备 {assigned_device_id} 不存在")
            item.assigned_device_id = assigned_device_id

        if keyword is not None:
            if not keyword.strip():
                raise ValueError("关键词不能为空")
            item.keyword = keyword

        db.commit()
        db.refresh(item)
        return item

    def batch_edit_items(
        self,
        db: Session,
        item_ids: list[str],
        account_id: Optional[str] = None,
        assigned_device_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> dict:
        """Batch edit items. Failures don't block successes."""
        updated = 0
        skipped = []
        errors = []

        if account_id is not None:
            acc = db.query(Account).filter(Account.id == account_id, Account.status == "active").first()
            if not acc:
                return {"updated": 0, "skipped": [], "errors": [f"账号 {account_id} 不存在或非 active 状态"]}

        if assigned_device_id is not None:
            dev = db.query(DBDevice).filter(DBDevice.id == assigned_device_id).first()
            if not dev:
                return {"updated": 0, "skipped": [], "errors": [f"设备 {assigned_device_id} 不存在"]}

        # Load all items in one query instead of N per-item queries
        items = db.query(ChannelItem).filter(ChannelItem.id.in_(item_ids)).all()
        item_map = {i.id: i for i in items}

        # Pre-load channel ownership for user-scoping
        channel_ids = []
        if items:
            channel_ids = list(set(i.channel_id for i in items))

        if user_id and channel_ids:
            owned_channels = set(
                ch[0] for ch in db.query(Channel.id).filter(
                    Channel.id.in_(channel_ids),
                    Channel.user_id == user_id,
                ).all()
            )
        else:
            owned_channels = None

        # Pre-load channel-group mapping for group membership validation
        valid_group_ids = set()
        if account_id is not None and channel_ids:
            channels = db.query(Channel).filter(
                Channel.id.in_(channel_ids),
                Channel.deleted_at.is_(None),
            ).all()
            channel_group_map = {c.id: c.group_id for c in channels}
            group_ids = list(set(channel_group_map.values()))
            if group_ids:
                rows = db.query(AccountGroupMember.group_id).filter(
                    AccountGroupMember.group_id.in_(group_ids),
                    AccountGroupMember.account_id == account_id,
                ).all()
                valid_group_ids = set(r[0] for r in rows)
        else:
            channel_group_map = {}

        for item_id in item_ids:
            try:
                item = item_map.get(item_id)
                if not item:
                    errors.append(f"{item_id}: 不存在")
                    continue
                if owned_channels is not None and item.channel_id not in owned_channels:
                    skipped.append(item_id)
                    continue
                if item.status != "pending":
                    skipped.append(item_id)
                    continue
                if account_id is not None and valid_group_ids:
                    item_group = channel_group_map.get(item.channel_id)
                    if item_group and item_group not in valid_group_ids:
                        skipped.append(item_id)
                        continue

                if account_id is not None:
                    item.account_id = account_id
                if assigned_device_id is not None:
                    item.assigned_device_id = assigned_device_id

                updated += 1
            except Exception as e:
                errors.append(f"{item_id}: {str(e)}")

        db.commit()
        return {"updated": updated, "skipped": skipped, "errors": errors}

    def update_item_status(self, db: Session, item_id: str, new_status: str, user_id: Optional[str] = None):
        """Update a single channel item status (skip/requeue)."""
        item = db.query(ChannelItem).filter(ChannelItem.id == item_id).first()
        if not item:
            raise ValueError(f"Item {item_id} 不存在")
        if user_id:
            ch = db.query(Channel).filter(Channel.id == item.channel_id, Channel.user_id == user_id).first()
            if not ch:
                raise ValueError(f"Item {item_id} 不属于当前用户")

        valid = {"pending": ["skipped"], "failed": ["pending"]}
        allowed = valid.get(item.status, [])
        if new_status not in allowed:
            raise ValueError(f"不允许从 {item.status} 转换到 {new_status}")

        item.status = new_status
        if new_status == "pending":
            item.assigned_device_id = None
            item.task_id = None
            item.completed_at = None
            self._reactivate_channel(db, item.channel_id)
        db.commit()

    def get_channel(self, db: Session, channel_id: str, user_id: Optional[str] = None) -> Optional[Channel]:
        query = db.query(Channel).filter(
            Channel.id == channel_id,
            Channel.deleted_at.is_(None),
        )
        if user_id:
            query = query.filter(Channel.user_id == user_id)
        return query.first()

    def list_channels(self, db: Session, user_id: Optional[str] = None) -> list[Channel]:
        query = db.query(Channel).filter(Channel.deleted_at.is_(None))
        if user_id:
            query = query.filter(Channel.user_id == user_id)
        return query.order_by(Channel.created_at.desc()).all()

    def get_channel_stats(self, db: Session, channel_id: str) -> dict:
        items = db.query(ChannelItem).filter(
            ChannelItem.channel_id == channel_id
        ).all()
        stats = {
            "total": len(items),
            "pending": 0,
            "assigned": 0,
            "completed": 0,
            "failed": 0,
            "skipped": 0,
        }
        for item in items:
            if item.status in stats:
                stats[item.status] += 1
        return stats

    def get_channels_stats_batch(self, db: Session, channel_ids: list[str]) -> dict[str, dict]:
        """Batch query stats for multiple channels. Returns {channel_id: stats_dict}."""
        from sqlalchemy import func
        if not channel_ids:
            return {}
        rows = db.query(
            ChannelItem.channel_id,
            ChannelItem.status,
            func.count(ChannelItem.id).label("cnt"),
        ).filter(
            ChannelItem.channel_id.in_(channel_ids),
        ).group_by(ChannelItem.channel_id, ChannelItem.status).all()

        result = {cid: {"total": 0, "pending": 0, "assigned": 0, "completed": 0, "failed": 0, "skipped": 0} for cid in channel_ids}
        for channel_id, status, cnt in rows:
            result[channel_id]["total"] += cnt
            if status in result[channel_id]:
                result[channel_id][status] = cnt
        return result


channel_service = ChannelService()
```

## app/services/content_service.py

```python
"""Content template and sensitive word service -- DB-backed."""
import json
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.db_models import ContentTemplate as DBTemplate, SensitiveWord as DBWord
from app.models import ContentTemplateResponse, SensitiveWordResponse


def _db_template_to_response(tpl: DBTemplate) -> ContentTemplateResponse:
    return ContentTemplateResponse(
        id=tpl.id,
        name=tpl.name,
        category=tpl.category,
        body=tpl.body,
        variables=tpl.variables or [],
        is_active=tpl.is_active,
        created_at=tpl.created_at,
        updated_at=tpl.updated_at,
    )


def _db_word_to_response(word: DBWord) -> SensitiveWordResponse:
    return SensitiveWordResponse(
        id=word.id,
        word=word.word,
        created_at=word.created_at,
    )


class ContentService:
    """Content template and sensitive word management."""

    # --- Template CRUD ---

    def create_template(
        self, db: Session, name: str, category: str = "comment",
        body: str = "", variables: list[str] | None = None,
    ) -> ContentTemplateResponse:
        tpl = DBTemplate(
            name=name,
            category=category,
            body=body,
            variables=variables or [],
        )
        db.add(tpl)
        db.commit()
        db.refresh(tpl)
        return _db_template_to_response(tpl)

    def get_template(
        self, db: Session, template_id: str, check_active: bool = False,
    ) -> Optional[ContentTemplateResponse]:
        q = db.query(DBTemplate).filter(DBTemplate.id == template_id)
        if check_active:
            q = q.filter(DBTemplate.is_active == True)
        tpl = q.first()
        if not tpl:
            return None
        return _db_template_to_response(tpl)

    def get_template_body(self, db: Session, template_id: str) -> Optional[str]:
        """Get just the body text of a template. Used for sync resolution."""
        tpl = db.query(DBTemplate).filter(
            DBTemplate.id == template_id,
            DBTemplate.is_active == True,
        ).first()
        return tpl.body if tpl else None

    def list_templates(
        self, db: Session, category: Optional[str] = None,
        skip: int = 0, limit: int = 50,
    ) -> tuple[list[ContentTemplateResponse], int]:
        q = db.query(DBTemplate)
        if category:
            q = q.filter(DBTemplate.category == category)
        total = q.count()
        templates = q.order_by(DBTemplate.created_at.desc()).offset(skip).limit(limit).all()
        return [_db_template_to_response(t) for t in templates], total

    def update_template(
        self, db: Session, template_id: str, **kwargs
    ) -> Optional[ContentTemplateResponse]:
        """Update template fields. Uses **kwargs for flexibility -- caller (router) passes
        validated data from ContentTemplateUpdate via model_dump(exclude_none=True)."""
        tpl = db.query(DBTemplate).filter(DBTemplate.id == template_id).first()
        if not tpl:
            return None
        for key, value in kwargs.items():
            if value is not None and hasattr(tpl, key):
                setattr(tpl, key, value)
        db.commit()
        db.refresh(tpl)
        return _db_template_to_response(tpl)

    def delete_template(self, db: Session, template_id: str) -> bool:
        tpl = db.query(DBTemplate).filter(DBTemplate.id == template_id).first()
        if not tpl:
            return False
        db.delete(tpl)
        db.commit()
        return True

    # --- Sensitive Word CRUD ---

    def add_sensitive_word(self, db: Session, word: str) -> SensitiveWordResponse:
        existing = db.query(DBWord).filter(DBWord.word == word).first()
        if existing:
            raise ValueError(f"Word '{word}' already exists")
        db_word = DBWord(word=word)
        db.add(db_word)
        db.commit()
        db.refresh(db_word)
        return _db_word_to_response(db_word)

    def list_sensitive_words(
        self, db: Session, skip: int = 0, limit: int = 200,
    ) -> tuple[list[SensitiveWordResponse], int]:
        total = db.query(DBWord).count()
        words = db.query(DBWord).order_by(DBWord.created_at.desc()).offset(skip).limit(limit).all()
        return [_db_word_to_response(w) for w in words], total

    def delete_sensitive_word(self, db: Session, word_id: str) -> bool:
        word = db.query(DBWord).filter(DBWord.id == word_id).first()
        if not word:
            return False
        db.delete(word)
        db.commit()
        return True

    def contains_sensitive(self, db: Session, text: str) -> bool:
        """Check if text contains any sensitive word.

        Loads all words from DB on each call (no cache) to ensure freshness.
        Uses substring match (not word-boundary) -- intentional for Douyin's
        aggressive content policy. False positives trigger a retry, which is
        acceptable since the AI prompt already avoids sensitive content.
        """
        words = [w for (w,) in db.query(DBWord.word).all()]
        return any(word in text for word in words)

    # --- Variable Substitution ---

    @staticmethod
    def substitute_variables(body: str, context: dict[str, str]) -> str:
        """Replace {variable} placeholders in body with context values.
        Missing variables are left unchanged."""
        def replacer(match):
            key = match.group(1)
            return context.get(key, match.group(0))
        return re.sub(r"\{(\w+)\}", replacer, body)

    # --- Content Generation ---

    async def generate_from_template(
        self, db: Session, template_id: str, context: dict[str, str],
    ) -> str:
        """Generate content from a template. Shared by admin, device, and poll resolution.

        Args:
            db: Database session
            template_id: Content template ID
            context: Variable values for substitution (e.g., {"keyword": "美食"})

        Returns:
            Generated content string

        Raises:
            ValueError: If template not found
            RuntimeError: If AI API not configured or all retries fail
        """
        tpl = self.get_template(db, template_id, check_active=True)
        if not tpl:
            raise ValueError(f"Template not found: {template_id}")

        substituted = self.substitute_variables(tpl.body, context)

        return await self._generate_content(db, substituted, context)

    async def _generate_content(
        self, db: Session, template_body: str, context: dict[str, str],
    ) -> str:
        """Delegate to the AI generator service."""
        from app.services.ai_generator import ai_generator
        return await ai_generator.generate(db, template_body, context)

    # --- Keyword Matrix Generation ---

    async def generate_keyword_matrix(self, keyword: str, count: int = 10, db=None) -> list[str]:
        """Generate expanded keyword matrix from a seed keyword using AI."""
        prompt = f"基于关键词「{keyword}」，生成 {count} 个相关的抖音搜索关键词。要求：包含同义词、长尾词、热门话题标签，每个关键词 2-8 个字。只返回 JSON 数组格式。"

        from app.services.ai_generator import ai_generator
        system_prompt = (
            "你是一个抖音搜索引擎优化专家。用户提供一个种子关键词，"
            "你返回一个 JSON 字符串数组，包含相关的长尾关键词和同义词。"
            "只返回 JSON 数组，不要加引号、不要解释、不要 markdown 代码块。"
        )
        try:
            response = await ai_generator.generate_custom(
                db, system_prompt, prompt,
                max_tokens=1024, temperature=0.8,
                thinking_enabled=False,
            )
        except Exception:
            return [keyword]

        try:
            keywords = json.loads(response)
            if isinstance(keywords, list):
                return [str(k) for k in keywords][:count]
        except (json.JSONDecodeError, TypeError):
            pass

        # AI 没有返回纯 JSON，尝试提取 [...] 部分
        match = re.search(r"\[.*?\]", response, re.DOTALL)
        if match:
            try:
                keywords = json.loads(match.group())
                if isinstance(keywords, list):
                    return [str(k) for k in keywords][:count]
            except (json.JSONDecodeError, TypeError):
                pass

        return [keyword]

    # --- Regex Generation ---

    async def generate_regex(self, db: Session, description: str) -> str:
        """Generate a regex pattern from natural language description."""
        from app.services.ai_generator import ai_generator
        system_prompt = (
            "你是一个正则表达式专家。用户用大白话描述需求，你只返回对应的正则表达式，"
            "不要加引号、不要解释、不要 markdown 代码块。"
        )
        return await ai_generator.generate_custom(
            db, system_prompt,
            f"请生成一个正则表达式：{description}",
            max_tokens=512, temperature=0.2,
            thinking_enabled=False,
        )

    # --- Clean Prompt Generation ---

    async def generate_clean_prompt(self, db: Session, description: str) -> str:
        """Generate an AI cleaning prompt from natural language description."""
        from app.services.ai_generator import ai_generator
        system_prompt = (
            "你是一个数据清洗专家。用户描述需要从一段文本中提取或清洗什么信息，"
            "你返回一个清晰的清洗提示词，这个提示词会被用于 AI 清洗从抖音控件中提取的原始数据。"
            "只返回提示词本身，不要加引号、不要解释、不要 markdown 代码块。"
        )
        return await ai_generator.generate_custom(
            db, system_prompt,
            f"请生成一个清洗提示词：{description}",
            max_tokens=512, temperature=0.3,
            thinking_enabled=False,
        )


content_service = ContentService()
```

## app/services/crypto.py

```python
"""Fernet (AES-128-CBC + HMAC-SHA256) field-level encryption for sensitive settings."""
import os
import hashlib
import base64
from cryptography.fernet import Fernet


def _get_key() -> bytes:
    raw = os.getenv("ENCRYPTION_KEY", "dy-auto-default-key-change-me")
    if raw == "dy-auto-default-key-change-me":
        return base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
    derived = hashlib.sha256(raw.encode()).digest()
    return base64.urlsafe_b64encode(derived)


_cipher: Fernet | None = None


def _get_cipher() -> Fernet:
    global _cipher
    if _cipher is None:
        _cipher = Fernet(_get_key())
    return _cipher


SENSITIVE_KEYS = {
    "seedance_api_key", "kling_access_key", "kling_secret_key",
    "runninghub_api_key", "comfyui_api_key", "llm_api_key",
    "oss_access_key", "oss_secret_key",
}


def is_sensitive_key(key: str) -> bool:
    return key in SENSITIVE_KEYS


def encrypt(value: str) -> str:
    return _get_cipher().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return _get_cipher().decrypt(value.encode()).decode()
```

## app/services/device_service.py

```python
"""Device registration, heartbeat, and status management."""
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.config import bj_now

from app.db_models import Device


class DeviceService:
    def register(
        self, db: Session, device_id: str, name: str,
        os_version: str = "", app_version: str = "",
        ip: str = "",
        screen_resolution: str = "", sdk_version: str = "",
        total_memory: int = None,
        manufacturer: str = "", product: str = "",
        device_model: str = "", hardware: str = "", display: str = "",
    ) -> dict:
        """Register or update a device. Returns device info dict."""
        device = db.query(Device).filter(Device.id == device_id).first()
        now = bj_now()

        if device:
            device.name = name
            device.os_version = os_version
            device.app_version = app_version
            if ip:
                device.ip = ip
            device.screen_resolution = screen_resolution or device.screen_resolution
            device.sdk_version = sdk_version or device.sdk_version
            device.total_memory = total_memory or device.total_memory
            device.manufacturer = manufacturer or device.manufacturer
            device.product = product or device.product
            device.device_model = device_model or device.device_model
            device.hardware = hardware or device.hardware
            device.display = display or device.display
            device.status = "online"
            device.last_seen_at = now
        else:
            device = Device(
                id=device_id, name=name, os_version=os_version, app_version=app_version,
                ip=ip or None,
                screen_resolution=screen_resolution, sdk_version=sdk_version,
                total_memory=total_memory, manufacturer=manufacturer, product=product,
                device_model=device_model, hardware=hardware, display=display,
                status="online", last_seen_at=now,
            )
            db.add(device)

        db.commit()
        db.refresh(device)

        return {
            "device_id": device.id,
            "name": device.name,
            "os_version": device.os_version,
            "app_version": device.app_version,
            "status": device.status,
        }

    def update_heartbeat(self, db: Session, device_id: str, ip: str = "") -> bool:
        """Update device last_seen_at. Returns True if status changed to online."""
        device = db.query(Device).filter(Device.id == device_id).first()
        if not device:
            return False
        was_offline = device.status != "online"
        device.last_seen_at = bj_now()
        device.status = "online"
        if ip:
            device.ip = ip
        db.commit()
        return was_offline

    def get_device_status(self, db: Session, device_id: str) -> dict | None:
        """Get device status info including proxy_config. Returns None for unknown devices."""
        device = db.query(Device).filter(Device.id == device_id).first()
        if not device:
            return None
        return {
            "device_id": device.id,
            "name": device.name,
            "status": device.status,
            "os_version": device.os_version,
            "app_version": device.app_version,
            "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
            "proxy_config": device.proxy_config,
        }

    def set_offline_devices(self, db: Session, timeout_seconds: int = 300) -> int:
        """Mark devices as offline if no heartbeat for timeout_seconds. Returns count."""
        now = bj_now()
        cutoff_dt = now - timedelta(seconds=timeout_seconds)
        count = (
            db.query(Device)
            .filter(Device.status == "online", Device.last_seen_at < cutoff_dt)
            .update({"status": "offline"})
        )
        db.commit()
        return count


device_service = DeviceService()
```

## app/services/industry_profile_service.py

```python
"""行业合规Profile加载器 — 从 JSON 文件加载，LRU 缓存"""
import json
import os
from functools import lru_cache

PROFILES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "data", "industry_profiles"
)


@lru_cache(maxsize=8)
def load_profile(industry: str) -> dict:
    """加载行业合规Profile，文件不存在时回退到 general.json"""
    path = os.path.join(PROFILES_DIR, f"{industry}.json")
    if not os.path.exists(path):
        path = os.path.join(PROFILES_DIR, "general.json")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_industries() -> list[dict]:
    """返回可用行业列表供前端下拉使用"""
    result = []
    try:
        for fname in sorted(os.listdir(PROFILES_DIR)):
            if fname.endswith(".json"):
                with open(os.path.join(PROFILES_DIR, fname), "r", encoding="utf-8") as f:
                    profile = json.load(f)
                    result.append({"key": profile["industry"], "label": profile["label"]})
    except FileNotFoundError:
        pass
    return result
```

## app/services/oss_service.py

```python
"""OSS/CDN Upload Service — 自动上传参考图获得公网 URL."""
import os
from loguru import logger


async def upload_to_oss(local_path: str, remote_key: str = "",
                        provider: str = "local",
                        endpoint: str = "", bucket: str = "",
                        access_key: str = "", secret_key: str = "") -> str:
    """
    上传文件到 OSS，返回公网 URL.

    Provider: local | minio | aliyun_oss
    """
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"Local file not found: {local_path}")

    if provider == "local":
        return f"file://{os.path.abspath(local_path)}"

    if provider == "minio":
        import boto3
        from botocore.config import Config
        client = boto3.client(
            "s3",
            endpoint_url=endpoint or "http://localhost:9000",
            aws_access_key_id=access_key or "minioadmin",
            aws_secret_access_key=secret_key or "minioadmin",
            config=Config(signature_version="s3v4"),
        )
        key = remote_key or os.path.basename(local_path)
        client.upload_file(local_path, bucket or "dy-auto-assets", key)
        url = f"{endpoint}/{bucket}/{key}"
        logger.info(f"Uploaded to MinIO: {url}")
        return url

    if provider == "aliyun_oss":
        import oss2
        auth = oss2.Auth(access_key, secret_key)
        b = oss2.Bucket(auth, endpoint, bucket)
        key = remote_key or f"characters/{os.path.basename(local_path)}"
        b.put_object_from_file(key, local_path)
        url = f"https://{bucket}.{endpoint.replace('https://', '')}/{key}"
        logger.info(f"Uploaded to OSS: {url}")
        return url

    logger.warning(f"Unknown OSS provider: {provider}, returning local path")
    return f"file://{os.path.abspath(local_path)}"
```

## app/services/pixelle_client.py

```python
"""Pixelle-Video HTTP client — unified request with retry, lazy singleton."""
import asyncio
import json
import logging
import httpx
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://127.0.0.1:8500/api"
TIMEOUT = httpx.Timeout(600, connect=10)
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0  # seconds, exponential: 2, 4, 8

_client: httpx.AsyncClient | None = None
_base_url: str = ""


def _get_base_url(db: Session | None = None) -> str:
    global _base_url
    if _base_url:
        return _base_url
    if db is not None:
        try:
            from app.db_models import SystemSetting
            row = db.query(SystemSetting).filter(SystemSetting.key == "pixelle_video_url").first()
            if row and row.value:
                _base_url = row.value.strip()
                return _base_url
        except Exception:
            pass
    _base_url = DEFAULT_BASE_URL
    return _base_url


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=TIMEOUT)
    return _client


async def close_client():
    """Close the module-level httpx client. Call during app shutdown."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


async def _pixelle_request(method: str, path: str, db: Session | None = None, **kwargs) -> dict:
    """统一的 Pixelle-Video HTTP 请求入口，带指数退避重试."""
    url = f"{_get_base_url(db)}{path}"
    client = _get_client()
    last_err = None

    for attempt in range(MAX_RETRIES):
        try:
            r = await client.request(method, url, **kwargs)
            r.raise_for_status()
            try:
                return r.json()
            except json.JSONDecodeError:
                raw = r.text[:500]
                logger.error("Pixelle-Video returned non-JSON response: %s", raw)
                raise RuntimeError(f"Pixelle-Video returned invalid JSON (status={r.status_code}): {raw}")
        except RuntimeError:
            raise  # JSON decode error — don't retry, it's not transient
        except httpx.HTTPStatusError as e:
            last_err = e
            if e.response.status_code < 500:
                raise  # 4xx — don't retry client errors
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as e:
            last_err = e
        if attempt < MAX_RETRIES - 1:
            delay = RETRY_BACKOFF * (2 ** attempt)
            logger.warning("Pixelle %s %s attempt %d/%d failed, retrying in %.0fs: %s",
                           method, path, attempt + 1, MAX_RETRIES, delay, last_err)
            await asyncio.sleep(delay)
    raise last_err
```

## app/services/prompt_template_service.py

```python
"""Prompt template management service — backed by SQLAlchemy database."""
from typing import Optional

from sqlalchemy.orm import Session

from app.db_models import PromptTemplate


def _to_dict(tmpl: PromptTemplate) -> dict:
    return {
        "id": tmpl.id,
        "name": tmpl.name,
        "industry": tmpl.industry,
        "description": tmpl.description or "",
        "content": tmpl.content,
        "version": tmpl.version,
        "enabled": tmpl.enabled,
        "created_at": tmpl.created_at.isoformat() if tmpl.created_at else None,
        "updated_at": tmpl.updated_at.isoformat() if tmpl.updated_at else None,
    }


def _to_device_dict(tmpl: PromptTemplate) -> dict:
    """Device-facing dict — strips admin fields."""
    return {
        "id": tmpl.id,
        "name": tmpl.name,
        "industry": tmpl.industry,
        "content": tmpl.content,
    }


class PromptTemplateService:
    """Prompt template management — DB-backed."""

    def get_all_templates(self, db: Session) -> tuple[int, list[dict]]:
        """Returns (version, templates_list)."""
        templates = db.query(PromptTemplate).filter(PromptTemplate.enabled == True).all()
        if not templates:
            return 0, []
        version = max(t.version for t in templates)
        return version, [_to_device_dict(t) for t in templates]

    def get_version(self, db: Session) -> int:
        """Get current max version across all enabled templates."""
        templates = db.query(PromptTemplate).filter(PromptTemplate.enabled == True).all()
        if not templates:
            return 0
        return max(t.version for t in templates)

    def get_template(self, db: Session, name: str) -> Optional[dict]:
        """Get a single template by name."""
        t = db.query(PromptTemplate).filter(
            PromptTemplate.name == name,
            PromptTemplate.enabled == True,
        ).first()
        if not t:
            return None
        return _to_dict(t)

    # replyExample 中不允许出现的元格式模式
    # 这些模式用于检测"评论'xxx' → 回复：'yyy'"类的元格式
    _REPLY_EXAMPLE_FORBIDDEN = [
        ("→ 回复", "replyExample 中不应包含「→ 回复」元格式，只需写回复正文，不需要标注原文"),
        ("→ 私信", "replyExample 中不应包含「→」箭头标注原文，只需写回复正文"),
        ("评论'", "replyExample 中不应包含「评论'...'」引用原文的写法，只需写回复正文"),
        ('评论"', 'replyExample 中不应包含「评论"..."」引用原文的写法，只需写回复正文'),
    ]

    @classmethod
    def _validate_reply_example(cls, content: dict) -> None:
        """校验 replyExample 不含元格式（评论xxx→回复：xxx 等）。"""
        an = content.get("analysis", {})
        re_example = an.get("replyExample", {})
        if not re_example:
            return
        for key in ("good", "bad"):
            text = re_example.get(key, "")
            if not isinstance(text, str) or not text.strip():
                continue
            for pattern, tip in cls._REPLY_EXAMPLE_FORBIDDEN:
                if pattern in text:
                    raise ValueError(f"replyExample.{key} 格式错误: {tip}。当前值: {text[:80]}")

    @classmethod
    def _validate_content(cls, content: dict) -> None:
        """Validate required template content fields. Raises ValueError on mismatch."""
        required = ["identity", "disabledWords", "semanticGuide", "analysis", "localFilter"]
        for field in required:
            if field not in content or not content[field]:
                raise ValueError(f"Missing required field: '{field}'")
        an = content.get("analysis", {})
        if not an.get("intents") or not an.get("scoringRules") or not an.get("replyRules"):
            raise ValueError("analysis must contain intents, scoringRules, replyRules")
        sg = content.get("semanticGuide", {})
        if not sg.get("highValueSignals") or not sg.get("lowValueSignals") or not sg.get("keyExamples"):
            raise ValueError("semanticGuide must contain highValueSignals, lowValueSignals, keyExamples")
        cls._validate_reply_example(content)

    def create_template(self, db: Session, name: str, industry: str,
                        content: dict, description: str = "") -> dict:
        """Create a new prompt template."""
        self._validate_content(content)
        existing = db.query(PromptTemplate).filter(PromptTemplate.name == name).first()
        if existing:
            raise ValueError(f"Template '{name}' already exists")

        tmpl = PromptTemplate(
            name=name,
            industry=industry,
            description=description,
            content=content,
            version=1,
        )
        db.add(tmpl)
        db.commit()
        db.refresh(tmpl)
        return _to_dict(tmpl)

    def update_template(self, db: Session, name: str,
                        content: dict = None, industry: str = None,
                        description: str = None) -> dict:
        """Update an existing template. Auto-bumps version on any change."""
        if content is not None:
            self._validate_content(content)
        tmpl = db.query(PromptTemplate).filter(PromptTemplate.name == name).first()
        if not tmpl:
            raise ValueError(f"Template '{name}' not found")

        if content is not None:
            tmpl.content = content
        if industry is not None:
            tmpl.industry = industry
        if description is not None:
            tmpl.description = description
        tmpl.version = (tmpl.version or 1) + 1

        db.commit()
        db.refresh(tmpl)
        return _to_dict(tmpl)

    def delete_template(self, db: Session, name: str) -> bool:
        """Delete a template by name."""
        tmpl = db.query(PromptTemplate).filter(PromptTemplate.name == name).first()
        if not tmpl:
            return False
        db.delete(tmpl)
        db.commit()
        return True

    def toggle_template(self, db: Session, name: str, enabled: bool) -> dict:
        """Enable or disable a template."""
        tmpl = db.query(PromptTemplate).filter(PromptTemplate.name == name).first()
        if not tmpl:
            raise ValueError(f"Template '{name}' not found")

        tmpl.enabled = enabled
        db.commit()
        db.refresh(tmpl)
        return _to_dict(tmpl)

    def list_all_templates(self, db: Session, include_disabled: bool = False) -> list[dict]:
        """List all templates (optionally including disabled ones)."""
        query = db.query(PromptTemplate)
        if not include_disabled:
            query = query.filter(PromptTemplate.enabled == True)
        templates = query.order_by(PromptTemplate.name).all()
        return [_to_dict(t) for t in templates]


# Module-level singleton
prompt_template_service = PromptTemplateService()
```

## app/services/script_service.py

```python
"""Device script version management — upload, version, download."""
from pathlib import Path

from app.config import SERVER_DIR


class ScriptService:
    def __init__(self, script_dir: Path | None = None, version_file: Path | None = None):
        self._script_dir = script_dir or (SERVER_DIR / "scripts")
        self._version_file = version_file or (self._script_dir / "version.txt")

    def _ensure_dir(self):
        self._script_dir.mkdir(parents=True, exist_ok=True)

    def get_version(self) -> str:
        """Return current script version. Defaults to '0.0.0'."""
        if self._version_file.exists():
            return self._version_file.read_text(encoding="utf-8").strip()
        return "0.0.0"

    def _bump_version(self) -> str:
        """Bump patch version: 1.0.0 -> 1.0.1."""
        current = self.get_version()
        parts = current.split(".")
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            parts[2] = str(int(parts[2]) + 1)
        else:
            parts = ["0", "0", "1"]
        new_version = ".".join(parts)
        self._version_file.write_text(new_version, encoding="utf-8")
        return new_version

    def upload_script(self, fileobj) -> str:
        """Upload a new script zip, bump version, return new version string."""
        self._ensure_dir()
        script_path = self._script_dir / "device-script.zip"
        content = fileobj.read() if hasattr(fileobj, "read") else fileobj
        script_path.write_bytes(content)
        return self._bump_version()

    def download_script(self) -> bytes | None:
        """Download current script zip. Returns None if no script exists."""
        script_path = self._script_dir / "device-script.zip"
        if not script_path.exists():
            return None
        return script_path.read_bytes()


script_service = ScriptService()
```

## app/services/selector_service.py

```python
"""Selector management service — backed by SQLAlchemy database."""
from typing import Optional

from sqlalchemy.orm import Session

from app.db_models import UISelector, Device


def _aspect_tag(resolution: str) -> str:
    """Compute aspect-ratio tag from 'WxH' string, e.g. '1080x2400' → '9:20'."""
    try:
        w, h = resolution.split("x")
        w, h = int(w), int(h)
    except (ValueError, AttributeError):
        return "unknown"
    if w == 0 or h == 0:
        return "unknown"
    # Reduce to simplest ratio
    a, b = w, h
    while b:
        a, b = b, a % b
    gcd = a
    return f"{w // gcd}:{h // gcd}"


def _profile_priority(sel_profile: str, dev_resolution: str, dev_ar: str) -> int:
    """Score a selector's resolution_profile against device resolution.
    3=exact match, 2=same aspect ratio, 1=default, 0=other."""
    if not sel_profile or sel_profile == "default":
        return 1
    if sel_profile == dev_resolution:
        return 3
    if _aspect_tag(sel_profile) == dev_ar:
        return 2
    return 0


def _to_dict(sel: UISelector) -> dict:
    return {
        "action_name": sel.action_name,
        "description": sel.description or "",
        "platform_version": sel.platform_version,
        "resolution_profile": sel.resolution_profile or "default",
        "strategies": sel.strategies,
        "version": sel.version,
        "enabled": sel.enabled,
        "category": sel.category or "",
        "purpose": sel.purpose or "locate",
        "strategy_logic": sel.strategy_logic or "and",
        "extract_field": sel.extract_field,
        "clean_mode": sel.clean_mode,
        "clean_pattern": sel.clean_pattern,
        "clean_prompt": sel.clean_prompt,
    }


def _to_device_dict(sel: UISelector) -> dict:
    """Device-facing dict (no description/version/enabled)."""
    return {
        "action_name": sel.action_name,
        "platform_version": sel.platform_version,
        "resolution_profile": sel.resolution_profile or "default",
        "strategies": sel.strategies,
        "purpose": sel.purpose or "locate",
        "strategy_logic": sel.strategy_logic or "and",
        "extract_field": sel.extract_field,
        "clean_mode": sel.clean_mode,
        "clean_pattern": sel.clean_pattern,
        "clean_prompt": sel.clean_prompt,
    }


class SelectorService:
    """UI selector management — DB-backed."""

    def get_all_selectors(self, db: Session, device_id: str = None) -> tuple[int, list[dict]]:
        """Returns (version, selectors_list). Version is max version across all selectors.
        When device_id is given, filters by resolution_profile: exact match > same AR > default.
        """
        selectors = db.query(UISelector).filter(UISelector.enabled == True).all()
        if not selectors:
            return 0, []

        # Resolve device resolution for profile filtering
        if device_id:
            device = db.query(Device).filter(Device.id == device_id).first()
            if device and device.screen_resolution:
                dev_res = device.screen_resolution
                dev_ar = _aspect_tag(dev_res)
                # Keep all resolution-compatible candidates. The device knows the
                # installed Douyin version, so it must make the final per-action
                # choice between platform-specific/default selector rows.
                selectors = [
                    s for s in selectors
                    if _profile_priority(s.resolution_profile or "default", dev_res, dev_ar) > 0
                ]

        version = max(s.version for s in selectors)
        return version, [_to_device_dict(s) for s in selectors]

    def get_selector(self, db: Session, action_name: str) -> Optional[dict]:
        """Get a single selector by action_name."""
        s = db.query(UISelector).filter(
            UISelector.action_name == action_name,
            UISelector.enabled == True,
        ).first()
        if not s:
            return None
        return _to_dict(s)

    def get_version(self, db: Session) -> int:
        """Get current selectors version."""
        selectors = db.query(UISelector).filter(UISelector.enabled == True).all()
        if not selectors:
            return 0
        return max(s.version for s in selectors)

    def create_selector(self, db: Session, action_name: str, strategies: list,
                        platform_version: str = "default", version: int = 1,
                        description: str = "", category: str = "",
                        purpose: str = "locate", strategy_logic: str = "and",
                        extract_field: str = None,
                        clean_mode: str = None, clean_pattern: str = None,
                        clean_prompt: str = None, resolution_profile: str = "default") -> dict:
        """Create a new UI selector."""
        existing = db.query(UISelector).filter(
            UISelector.action_name == action_name,
            UISelector.platform_version == platform_version,
            UISelector.resolution_profile == resolution_profile,
        ).first()
        if existing:
            raise ValueError(f"Selector '{action_name}' already exists for this platform/profile")

        sel = UISelector(
            action_name=action_name,
            description=description,
            platform_version=platform_version,
            resolution_profile=resolution_profile,
            strategies=strategies,
            version=version,
            category=category or None,
            purpose=purpose or "locate",
            strategy_logic=strategy_logic or "and",
            extract_field=extract_field,
            clean_mode=clean_mode,
            clean_pattern=clean_pattern,
            clean_prompt=clean_prompt,
        )
        db.add(sel)
        db.commit()
        db.refresh(sel)
        return _to_dict(sel)

    def update_selector(self, db: Session, action_name: str,
                        strategies: list = None, platform_version: str = None,
                        description: str = None, category: str = None,
                        purpose: str = None, strategy_logic: str = None,
                        extract_field: str = None,
                        clean_mode: str = None, clean_pattern: str = None,
                        clean_prompt: str = None, resolution_profile: str = None) -> dict:
        """Update an existing selector. Auto-bumps version on any change."""
        sel = db.query(UISelector).filter(UISelector.action_name == action_name).first()
        if not sel:
            raise ValueError(f"Selector '{action_name}' not found")

        if strategies is not None:
            sel.strategies = strategies
        if platform_version is not None:
            sel.platform_version = platform_version
        if resolution_profile is not None:
            sel.resolution_profile = resolution_profile
        if description is not None:
            sel.description = description
        if category is not None:
            sel.category = category or None
        if purpose is not None:
            sel.purpose = purpose
        if strategy_logic is not None:
            sel.strategy_logic = strategy_logic
        if extract_field is not None:
            sel.extract_field = extract_field
        if clean_mode is not None:
            sel.clean_mode = clean_mode
        if clean_pattern is not None:
            sel.clean_pattern = clean_pattern
        if clean_prompt is not None:
            sel.clean_prompt = clean_prompt
        # Auto-bump version on any change
        sel.version = (sel.version or 1) + 1

        db.commit()
        db.refresh(sel)
        return _to_dict(sel)

    def delete_selector(self, db: Session, action_name: str, platform_version: str = None) -> bool:
        """Delete a selector by action_name (and optionally platform_version)."""
        q = db.query(UISelector).filter(UISelector.action_name == action_name)
        if platform_version:
            q = q.filter(UISelector.platform_version == platform_version)
        sel = q.first()
        if not sel:
            return False
        db.delete(sel)
        db.commit()
        return True

    def toggle_selector(self, db: Session, action_name: str, enabled: bool) -> dict:
        """Enable or disable a selector."""
        sel = db.query(UISelector).filter(UISelector.action_name == action_name).first()
        if not sel:
            raise ValueError(f"Selector '{action_name}' not found")

        sel.enabled = enabled
        db.commit()
        db.refresh(sel)
        return _to_dict(sel)

    def list_all_selectors(self, db: Session, include_disabled: bool = False,
                           category: str = None) -> list[dict]:
        """List all selectors (optionally including disabled ones and filtering by category)."""
        query = db.query(UISelector)
        if not include_disabled:
            query = query.filter(UISelector.enabled == True)
        if category:
            query = query.filter(UISelector.category == category)
        selectors = query.order_by(UISelector.action_name).all()
        return [_to_dict(s) for s in selectors]


# Module-level singleton — stateless, DB sessions injected per call
selector_service = SelectorService()
```

## app/services/stats_service.py

```python
"""Daily stats tracking service — operation counts per account per day."""
from datetime import datetime, timezone
from app.config import bj_now
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db_models import DailyStats, Account


# Task type -> daily_stats column mapping
_TASK_TYPE_TO_COLUMN = {
    "search_like": "likes",
    "nurture": "nurture_likes",
    "search_comment": "comments",
    "reply_comment": "replies",
    "search_dm": "dms",
    "follow": "follows",
    "collect": "collected",
}


class StatsService:
    def _today(self) -> str:
        return bj_now().strftime("%Y-%m-%d")

    def _get_or_create(self, db: Session, account_id: str, date: str) -> DailyStats:
        """Get or create daily stats row for an account+date."""
        stats = db.query(DailyStats).filter(
            and_(DailyStats.account_id == account_id, DailyStats.date == date)
        ).first()
        if not stats:
            stats = DailyStats(account_id=account_id, date=date)
            db.add(stats)
            db.flush()
        return stats

    def increment(self, db: Session, account_id: str, task_type: str, count: int = 1) -> None:
        """Increment operation count for a task type. Only flushes — caller must commit."""
        column = _TASK_TYPE_TO_COLUMN.get(task_type)
        if not column:
            return
        date = self._today()
        stats = self._get_or_create(db, account_id, date)
        current = getattr(stats, column, 0)
        setattr(stats, column, current + count)
        db.flush()

    def get_today_counts(self, db: Session, account_id: str) -> dict[str, int]:
        """Get today's operation counts for an account."""
        date = self._today()
        stats = self._get_or_create(db, account_id, date)
        return {
            "likes": stats.likes,
            "nurture_likes": stats.nurture_likes,
            "comments": stats.comments,
            "follows": stats.follows,
            "dms": stats.dms,
            "replies": stats.replies,
            "collected": stats.collected,
        }

    def _get_limits(self, db: Session, account_id: str) -> dict[str, int]:
        """Get the daily limits for an account."""
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account or not account.daily_limits:
            return {}
        return dict(account.daily_limits)

    def check_quota(self, db: Session, account_id: str, task_type: str) -> bool:
        """Check if account has remaining quota for this task type today.

        Returns True if quota is available, False if limit reached.
        Limit of -1 means unlimited (always returns True).
        """
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            return True  # no account found, don't block

        limits = account.daily_limits or {}
        counts = self.get_today_counts(db, account_id)

        def _check_limit(column_key: str, default: int = 999) -> bool:
            limit = limits.get(column_key, default)
            if limit == -1:
                return True
            used = counts.get(column_key, 0)
            return used < limit

        # nurture 使用独立列 nurture_likes，与 search_like 分离
        if task_type == "nurture":
            return _check_limit("nurture_likes", limits.get("likes", 999))

        # reply_comment 不阻塞 follow/DM，handler 内部优雅降级
        if task_type == "reply_comment":
            col = _TASK_TYPE_TO_COLUMN.get(task_type)
            if col:
                return _check_limit(col, 999)
            return True

        column = _TASK_TYPE_TO_COLUMN.get(task_type)
        if not column:
            return True  # unknown type, don't block

        return _check_limit(column, 999)

    def get_remaining_quotas(self, db: Session, account_id: str) -> dict[str, int]:
        """Get remaining quotas for all operation types."""
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            return {}

        limits = account.daily_limits or {}
        counts = self.get_today_counts(db, account_id)

        remaining = {}
        for key in ("likes", "nurture_likes", "comments", "follows", "dms", "replies", "collected"):
            limit = limits.get(key, 999)
            if limit == -1:
                remaining[key] = 999  # -1 = 不限
            else:
                used = counts.get(key, 0)
                remaining[key] = max(0, limit - used)
        return remaining


stats_service = StatsService()
```

## app/services/task_service.py

```python
"""Task scheduling service — backed by SQLAlchemy database."""
from datetime import datetime, timezone
from app.config import bj_now
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import update, or_, and_, null, String, select

from app.db_models import Task as DBTask, Device as DBDevice
from app.models import TaskType, TaskStatus, Task as PydanticTask
from app.services.stats_service import stats_service

MAX_RETRIES = 3


def _db_task_to_pydantic(task: DBTask) -> PydanticTask:
    """Convert SQLAlchemy Task to Pydantic Task for API responses."""
    return PydanticTask(
        id=task.id,
        type=TaskType(task.type),
        account_id=task.account_id,
        device_id=task.device_id or "",
        params=task.params or {},
        status=TaskStatus(task.status),
        created_at=task.created_at,
        scheduled_at=task.scheduled_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        result=task.result,
        retry_count=task.retry_count,
        chain_instance_id=task.chain_instance_id,
        step_order=task.step_order,
    )


class TaskService:
    """Task scheduling service — DB-backed."""

    def create_task(
        self,
        db: Session,
        task_type: TaskType,
        account_id: str,
        params: dict,
        scheduled_at: Optional[datetime] = None,
        device_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> PydanticTask:
        db_task = DBTask(
            type=task_type.value,
            account_id=account_id,
            device_id=device_id,
            user_id=user_id,
            params=params,
            status=TaskStatus.PENDING.value,
            scheduled_at=scheduled_at,
        )
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        return _db_task_to_pydantic(db_task)

    def get_task(self, db: Session, task_id: str) -> Optional[PydanticTask]:
        db_task = db.query(DBTask).filter(DBTask.id == task_id).first()
        if not db_task:
            return None
        return _db_task_to_pydantic(db_task)

    def get_pending_task(self, db: Session, device_id: str) -> Optional[PydanticTask]:
        """Claim a pending task using optimistic locking, respecting daily quotas and device routing.

        Routing rules:
        - Directed task (task.device_id set) -> only that device can claim it
        - Bound device (device.bound_account_id set) -> only tasks for that account
        - Unbound device -> only tasks with no device_id AND whose account is not bound to any device
        """
        # --- Channel claim (priority path) ---
        from app.services.channel_service import channel_service
        channel_result = channel_service.claim_channel_item(db, device_id)
        if channel_result:
            task_pydantic, _channel_item_id = channel_result
            db.commit()
            return task_pydantic

        # 1. Look up the polling device's bound account and user
        device = db.query(DBDevice).filter(DBDevice.id == device_id).first()
        bound_account_id = device.bound_account_id if device else None
        device_user_id = device.user_id if device else None

        # 2. Build routing filter
        if bound_account_id:
            # Bound device: can claim directed tasks OR tasks for its bound account
            route_filter = or_(
                DBTask.device_id == device_id,
                and_(DBTask.device_id.is_(None), DBTask.account_id == bound_account_id),
            )
        else:
            # Unbound device: can claim directed tasks OR orphan tasks
            # (tasks with no device_id whose account is not bound to any device)
            bound_account_ids = db.query(DBDevice.bound_account_id).filter(
                DBDevice.bound_account_id.isnot(None)
            ).scalar_subquery()
            route_filter = or_(
                DBTask.device_id == device_id,
                and_(DBTask.device_id.is_(None), ~DBTask.account_id.in_(bound_account_ids)),
            )

        # 3. Recover stuck RUNNING tasks (device crashed while executing)
        # Only reclaim tasks from devices that haven't sent a heartbeat recently.
        from datetime import timedelta
        import os
        stale_minutes = int(os.getenv("TASK_STALE_MINUTES", "10"))
        stale_threshold = bj_now() - timedelta(minutes=stale_minutes)

        # Find devices that were recently seen (still online)
        online_device_ids = select(DBDevice.id).where(
            DBDevice.last_seen_at.isnot(None),
            DBDevice.last_seen_at >= stale_threshold,
        )

        stale_running = db.query(DBTask).filter(
            DBTask.status == TaskStatus.RUNNING.value,
            DBTask.started_at.isnot(None),
            DBTask.started_at < stale_threshold,
            ~DBTask.device_id.in_(online_device_ids),  # skip tasks on online devices
        ).all()
        for stale in stale_running:
            stale.retry_count += 1
            if stale.retry_count >= MAX_RETRIES:
                stale.status = TaskStatus.FAILED.value
                stale.completed_at = bj_now()
            else:
                stale.status = TaskStatus.PENDING.value
                stale.device_id = None
                stale.started_at = None
        if stale_running:
            db.flush()
            # Reset associated channel items so keywords can be re-dispatched
            from app.db_models import ChannelItem
            from app.services.channel_service import channel_service as ch_svc
            stale_ids = [t.id for t in stale_running]
            stale_ch_items = db.query(ChannelItem).filter(ChannelItem.task_id.in_(stale_ids)).all()
            stale_ch_ids = set()
            for sci in stale_ch_items:
                sci.status = "pending"
                sci.assigned_device_id = None
                sci.assigned_at = None
                sci.task_id = None
                stale_ch_ids.add(sci.channel_id)
            if stale_ch_items:
                db.flush()
                for cid in stale_ch_ids:
                    ch_svc._reactivate_channel(db, cid)

        # 4. Find candidate tasks with routing, user scope, and scheduled_at applied
        now = bj_now()
        candidate_query = db.query(DBTask).filter(
            DBTask.status == TaskStatus.PENDING.value,
            route_filter,
            or_(DBTask.scheduled_at.is_(None), DBTask.scheduled_at <= now),
        )
        if device_user_id:
            candidate_query = candidate_query.filter(
                or_(DBTask.user_id == device_user_id, DBTask.user_id.is_(None))
            )
        candidates = candidate_query.order_by(DBTask.created_at.asc()).limit(10).all()

        if not candidates:
            return None

        # 5. Filter by daily quota and claim via atomic optimistic locking
        # Subquery: accounts that already have a RUNNING task
        busy_account_ids = db.query(DBTask.account_id).filter(
            DBTask.status == TaskStatus.RUNNING.value,
        ).distinct().scalar_subquery()

        for db_task in candidates:
            # Check task quota (reply_comment 不阻塞 follow/DM，handler 内部优雅降级)
            if not stats_service.check_quota(db, db_task.account_id, db_task.type):
                continue
            # Atomic claim: only succeeds if no other task for this account is RUNNING
            result = db.execute(
                update(DBTask)
                .where(
                    DBTask.id == db_task.id,
                    DBTask.status == TaskStatus.PENDING.value,
                    ~DBTask.account_id.in_(busy_account_ids),
                )
                .values(status=TaskStatus.RUNNING.value, device_id=device_id, started_at=bj_now())
            )
            db.commit()

            if result.rowcount == 0:
                continue

            db.refresh(db_task)
            return _db_task_to_pydantic(db_task)

        return None

    def report_result(
        self,
        db: Session,
        task_id: str,
        status: TaskStatus,
        result: Optional[dict] = None,
        ui_snapshot: Optional[dict] = None,
    ) -> tuple[PydanticTask, Optional[dict]]:
        db_task = db.query(DBTask).filter(DBTask.id == task_id).first()
        if not db_task:
            raise ValueError(f"Task {task_id} not found")

        # Task already in terminal state — ignore late reports
        if db_task.status in (TaskStatus.CANCELLED.value, TaskStatus.COMPLETED.value, TaskStatus.FAILED.value):
            import logging
            _logger = logging.getLogger("task_service")
            _logger.warning("Late report discarded: task %s already in terminal state %s (reported status=%s)",
                            task_id, db_task.status, status.value if hasattr(status, 'value') else status)
            return _db_task_to_pydantic(db_task), None

        # Check channel association early (affects retry logic)
        from app.db_models import ChannelItem
        from app.services.channel_service import channel_service
        channel_item = db.query(ChannelItem).filter(ChannelItem.task_id == task_id).first()

        if status == TaskStatus.COMPLETED:
            db_task.status = TaskStatus.COMPLETED.value
            db_task.result = result
            db_task.completed_at = bj_now()
            # 统计由设备端增量上报 (POST /api/device/stats/increment)
            # 每个子操作完成后实时上报，避免中途崩溃丢失数据 + 防止双重计数
        elif status == TaskStatus.FAILED:
            db_task.retry_count += 1
            if db_task.retry_count >= MAX_RETRIES:
                db_task.status = TaskStatus.FAILED.value
                db_task.result = result
                db_task.completed_at = bj_now()
            else:
                db_task.status = TaskStatus.PENDING.value  # re-queue for retry
                db_task.device_id = None
                db_task.started_at = None
                # Keep ChannelItem assigned — prevents channel from re-dispatching
                # the same keyword while the task retries via the direct queue.
                # Refresh assigned_at to extend the stale recovery window.
                if channel_item:
                    channel_item.assigned_at = bj_now()

        # Advance chain if this task is part of one
        if db_task.chain_instance_id and db_task.status in ("completed", "failed"):
            from app.services.chain_service import chain_service
            chain_service.advance_chain(db, task_id, db_task.status, result)

        # Update channel item status
        channel_broadcast_info = None
        if channel_item and db_task.status in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value):
            channel_broadcast_info = channel_service.complete_item(db, channel_item.id,
                "completed" if db_task.status == TaskStatus.COMPLETED.value else "failed")

        db.commit()
        db.refresh(db_task)
        return _db_task_to_pydantic(db_task), channel_broadcast_info

    def list_tasks(self, db: Session, status=None, task_type: str = None, search: str = None,
                   sort_by: str = "created_at", sort_order: str = "desc",
                   skip: int = 0, limit: int = 50, current_user_id: str = None) -> list[PydanticTask]:
        query = db.query(DBTask)
        if status:
            query = query.filter(DBTask.status == (status.value if hasattr(status, 'value') else status))
        if task_type:
            query = query.filter(DBTask.type == task_type)
        if search:
            pattern = f"%{search}%"
            query = query.filter(or_(
                DBTask.account_id.like(pattern),
                DBTask.device_id.like(pattern),
                DBTask.params.like(pattern),
            ))
        if current_user_id:
            query = query.filter(DBTask.user_id == current_user_id)
        col = getattr(DBTask, sort_by, DBTask.created_at)
        order = col.desc() if sort_order == "desc" else col.asc()
        db_tasks = query.order_by(order).offset(skip).limit(limit).all()
        return [_db_task_to_pydantic(t) for t in db_tasks]

    def count_tasks(self, db: Session, status=None, task_type: str = None, search: str = None, current_user_id: str = None) -> int:
        query = db.query(DBTask)
        if status:
            query = query.filter(DBTask.status == (status.value if hasattr(status, 'value') else status))
        if task_type:
            query = query.filter(DBTask.type == task_type)
        if search:
            pattern = f"%{search}%"
            query = query.filter(or_(
                DBTask.account_id.like(pattern),
                DBTask.device_id.like(pattern),
                DBTask.params.like(pattern),
            ))
        if current_user_id:
            query = query.filter(DBTask.user_id == current_user_id)
        return query.count()

    def cancel_task(self, db: Session, task_id: str):
        """Cancel a pending or running task. Resets associated channel item if any."""
        task = db.query(DBTask).filter(DBTask.id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")
        if task.status in (TaskStatus.COMPLETED.value, TaskStatus.CANCELLED.value, TaskStatus.FAILED.value):
            raise ValueError(f"Cannot cancel task in status: {task.status}")
        task.status = TaskStatus.CANCELLED.value
        task.completed_at = bj_now()

        # Reset associated channel item so it can be re-dispatched
        from app.db_models import ChannelItem
        from app.services.channel_service import channel_service as ch_svc
        channel_item = db.query(ChannelItem).filter(ChannelItem.task_id == task_id).first()
        if channel_item:
            channel_item.status = "pending"
            channel_item.assigned_device_id = None
            channel_item.assigned_at = None
            channel_item.task_id = None
            db.flush()
            ch_svc._reactivate_channel(db, channel_item.channel_id)

        db.commit()
        db.refresh(task)
        return _db_task_to_pydantic(task)

    def delete_task(self, db: Session, task_id: str) -> bool:
        """Delete a task. Only non-running tasks can be deleted. Resets ChannelItem."""
        task = db.query(DBTask).filter(DBTask.id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")
        if task.status == TaskStatus.RUNNING.value:
            raise ValueError("Cannot delete a running task. Cancel it first.")

        # Reset associated ChannelItem so the keyword can be re-dispatched
        from app.db_models import ChannelItem, CollectedComment, CollectedUser, Conversation, GeneratedVideo
        from app.services.channel_service import channel_service as ch_svc
        channel_item = db.query(ChannelItem).filter(ChannelItem.task_id == task_id).first()
        if channel_item:
            channel_item.status = "pending"
            channel_item.assigned_device_id = None
            channel_item.assigned_at = None
            channel_item.task_id = None
            db.flush()
            ch_svc._reactivate_channel(db, channel_item.channel_id)

        # Null out FK references from child tables to avoid FK constraint error on delete
        for model in (CollectedComment, CollectedUser, Conversation, GeneratedVideo):
            db.query(model).filter(model.task_id == task_id).update(
                {"task_id": None}, synchronize_session=False
            )

        db.delete(task)
        db.commit()
        return True

    def delete_tasks_batch(self, db: Session, task_ids: list[str]) -> int:
        """Delete multiple tasks in batch. Returns count of deleted tasks."""
        if not task_ids:
            return 0
        from app.db_models import ChannelItem
        # Only delete non-running tasks; running tasks are protected
        deletable = db.query(DBTask.id).filter(
            DBTask.id.in_(task_ids),
            DBTask.status != TaskStatus.RUNNING.value,
        ).all()
        deletable_ids = [t[0] for t in deletable]
        if not deletable_ids:
            return 0
        # Reset channel items only for tasks that will actually be deleted
        from app.services.channel_service import channel_service as ch_svc
        channel_items = db.query(ChannelItem).filter(ChannelItem.task_id.in_(deletable_ids)).all()
        ch_ids = set()
        for ci in channel_items:
            ci.status = "pending"
            ci.assigned_device_id = None
            ci.assigned_at = None
            ci.task_id = None
            ch_ids.add(ci.channel_id)
        if channel_items:
            db.flush()
            for cid in ch_ids:
                ch_svc._reactivate_channel(db, cid)
        # Null out FK references from child tables
        from app.db_models import CollectedComment, CollectedUser, Conversation, GeneratedVideo
        for model in (CollectedComment, CollectedUser, Conversation, GeneratedVideo):
            db.query(model).filter(model.task_id.in_(deletable_ids)).update(
                {"task_id": None}, synchronize_session=False
            )
        result = db.query(DBTask).filter(
            DBTask.id.in_(deletable_ids),
        ).delete(synchronize_session=False)
        db.commit()
        return result

    def check_cancelled_running(self, db: Session, device_id: str) -> Optional[PydanticTask]:
        """Check if device has a running task that was recently cancelled.

        Only returns tasks cancelled within the last 5 minutes — older ones are
        treated as acknowledged to prevent the same stale cancellation from
        being returned on every poll.
        """
        from datetime import timedelta
        cutoff = bj_now() - timedelta(minutes=5)
        task = (
            db.query(DBTask)
            .filter(
                DBTask.device_id == device_id,
                DBTask.status == TaskStatus.CANCELLED.value,
                DBTask.completed_at >= cutoff,
            )
            .order_by(DBTask.completed_at.desc())
            .first()
        )
        return _db_task_to_pydantic(task) if task else None


# Module-level singleton — services are stateless, DB sessions come from get_db
task_service = TaskService()
```

## app/services/template_service.py

```python
"""Template image storage — listing, caching, and file operations.

Templates are stored in resolution subdirectories:
  template_images/
    default/          ← fallback templates
    1080x2400/        ← device-specific templates
    720x1600/
"""

import hashlib
import os
from pathlib import Path
from typing import Optional

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "template_images"
TEMPLATE_DIR.mkdir(exist_ok=True)
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def _ensure_resolution_dir(resolution: str) -> Path:
    """Ensure a resolution subdirectory exists."""
    d = TEMPLATE_DIR / resolution
    d.mkdir(exist_ok=True)
    return d


def _safe_resolve(path: Path, parent: Path) -> bool:
    """Check that resolved path is within parent directory."""
    try:
        return path.resolve().parent == parent.resolve()
    except Exception:
        return False


class TemplateService:
    """Template image management with MD5 caching and resolution subdirectories."""

    def __init__(self):
        # cache key: "resolution/filename" → { md5, mtime, size }
        self._md5_cache: dict[str, dict] = {}

    def _iter_templates(self, resolution: str = None):
        """Iterate template files. If resolution given, includes that subdirectory
        plus 'default' as fallback (resolution-specific wins on duplicate names).
        Otherwise iterates all resolution subdirectories."""
        if resolution:
            dirs = [TEMPLATE_DIR / resolution, TEMPLATE_DIR / "default"]
        else:
            dirs = [d for d in TEMPLATE_DIR.iterdir() if d.is_dir()]
        seen = set()
        for subdir in dirs:
            if not subdir.is_dir():
                continue
            for f in sorted(subdir.iterdir()):
                if f.suffix.lower() in ALLOWED_EXTENSIONS and f.is_file():
                    if f.name not in seen:
                        seen.add(f.name)
                        yield f, subdir.name

    def list_templates(self, resolution: str = None) -> list[dict]:
        """List template images with metadata. Optionally filter by resolution."""
        templates = []
        for f, res in self._iter_templates(resolution):
            stat = f.stat()
            cache_key = f"{res}/{f.name}"
            cached = self._md5_cache.get(cache_key)
            if cached and cached["mtime"] == stat.st_mtime and cached["size"] == stat.st_size:
                md5 = cached["md5"]
            else:
                md5 = hashlib.md5(f.read_bytes()).hexdigest()
                self._md5_cache[cache_key] = {
                    "md5": md5,
                    "mtime": stat.st_mtime,
                    "size": stat.st_size,
                }
            templates.append({
                "filename": f.name,
                "size": stat.st_size,
                "md5": md5,
                "resolution": res,
            })
        return templates

    def get_template_path(self, filename: str, resolution: str = "default") -> Optional[Path]:
        """Get template file path. Looks in resolution subdirectory first, then 'default' fallback."""
        # Try resolution-specific first
        if resolution:
            filepath = TEMPLATE_DIR / resolution / filename
            if filepath.exists() and _safe_resolve(filepath, TEMPLATE_DIR / resolution):
                return filepath
        # Fall back to default
        filepath = TEMPLATE_DIR / "default" / filename
        if filepath.exists() and _safe_resolve(filepath, TEMPLATE_DIR / "default"):
            return filepath
        return None

    def delete_template(self, filename: str, resolution: str = "default") -> bool:
        """Delete a template file."""
        filepath = TEMPLATE_DIR / resolution / filename
        if not filepath.exists():
            return False
        if not _safe_resolve(filepath, TEMPLATE_DIR / resolution):
            return False
        filepath.unlink()
        self._md5_cache.pop(f"{resolution}/{filename}", None)
        return True

    def save_template(self, filename: str, content: bytes, resolution: str = "default") -> Path:
        """Save template to resolution subdirectory."""
        _ensure_resolution_dir(resolution)
        dest = TEMPLATE_DIR / resolution / filename
        if not _safe_resolve(dest, TEMPLATE_DIR / resolution):
            raise ValueError("Path traversal detected")
        dest.write_bytes(content)
        self._md5_cache.pop(f"{resolution}/{filename}", None)
        return dest


template_service = TemplateService()
```

## app/database.py

```python
"""Database engine, session factory, and FastAPI dependency."""
import os
import logging
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker, Session

from app.db_models import Base

logger = logging.getLogger(__name__)

SERVER_DIR = Path(__file__).parent.parent
DEFAULT_DB_PATH = SERVER_DIR / "app" / "data" / "dy_auto.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

# SQLite needs check_same_thread=False for FastAPI's multi-threaded request handling
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


def _migrate_add_columns():
    """Add missing columns to existing SQLite tables (safe to call repeatedly)."""
    if not DATABASE_URL.startswith("sqlite"):
        return
    insp = inspect(engine)
    with engine.begin() as conn:
        for table_name, table in Base.metadata.tables.items():
            if table_name not in insp.get_table_names():
                continue
            existing = {col["name"] for col in insp.get_columns(table_name)}
            for col in table.columns:
                if col.name not in existing:
                    col_type = col.type.compile(engine.dialect)
                    nullable = "NULL" if col.nullable else "NOT NULL"
                    default = ""
                    if col.default is not None:
                        default_sql = col.default.arg
                        if isinstance(default_sql, bool):
                            default = f" DEFAULT {1 if default_sql else 0}"
                        elif isinstance(default_sql, str):
                            default = f" DEFAULT '{default_sql}'"
                        elif isinstance(default_sql, (int, float)):
                            default = f" DEFAULT {default_sql}"
                        elif isinstance(default_sql, (list, dict)):
                            import json as _json
                            default = f" DEFAULT '{_json.dumps(default_sql)}'"
                    sql = f"ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type} {nullable}{default}"
                    logger.info(f"Migration: {sql}")
                    conn.execute(text(sql))


def _seed_admin_user():
    """Create default admin user from env vars if users table is empty (idempotent)."""
    import os as _os
    import bcrypt as _bcrypt
    from app.db_models import User

    with SessionLocal() as db:
        if db.query(User).count() == 0:
            username = _os.getenv("ADMIN_USERNAME", "admin")
            password = _os.getenv("ADMIN_PASSWORD", "admin123")
            pw_hash = _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()
            db.add(User(username=username, password_hash=pw_hash, role="admin", nickname="管理员"))
            db.commit()
            logger.info("Seeded default admin user: %s", username)


def _seed_selector_descriptions():
    """Populate empty description fields for known action names (idempotent)."""
    from app.db_models import UISelector

    descriptions = {
        "back_btn": "返回按钮",
        "open_app": "打开抖音 App",
        "video_comment_btn": "视频评论入口按钮（点击打开评论面板）",
        "video_comment_input": "视频评论输入框（需先点击弹出键盘）",
        "search_tab": "搜索标签页入口",
        "search_input": "搜索输入框",
        "search_button": "搜索按钮",
        "search_suggestion": "搜索建议词",
        "search_suggestion_list": "搜索联想词列表容器",
        "search_video_tab": "搜索结果-视频标签页",
        "search_video_list": "搜索结果-视频列表容器",
        "video_tab": "视频标签页",
        "video_author_avatar": "视频作者头像（点击进入主页）",
        "sort_button": "排序按钮",
        "sort_latest": "最新排序选项",
        "sort_most_liked": "最多点赞排序选项",
        "sort_default": "默认排序选项",
        "like_button": "点赞按钮",
        "follow_button": "关注按钮",
        "comment_input": "评论输入框",
        "comment_submit": "评论提交按钮",
        "comment_reply_button": "评论回复按钮",
        "comment_reply_input": "评论回复输入框",
        "comment_reply_submit": "评论回复提交按钮",
        "comment_list": "评论列表容器",
        "comment_text": "评论内容文本",
        "comment_author": "评论作者昵称",
        "comment_time": "评论发布时间",
        "comment_like_count": "评论点赞数",
        "comment_author_avatar": "评论作者头像",
        "message_button": "私信按钮",
        "dm_input": "私信输入框",
        "dm_send": "私信发送按钮",
        "profile_more": "个人主页更多菜单",
    }

    with SessionLocal() as db:
        updated = 0
        for sel in db.query(UISelector).filter(
            (UISelector.description == "") | (UISelector.description.is_(None))
        ).all():
            desc = descriptions.get(sel.action_name, "")
            if desc:
                sel.description = desc
                updated += 1
        if updated:
            db.commit()
            logger.info(f"Seeded {updated} selector descriptions")


def init_db():
    """Create all tables. Called once at startup.

    Runs alembic migrations first, then create_all as safety net for any tables
    not yet captured by migrations. Both are idempotent.
    """
    # Ensure data directory exists for SQLite
    if DATABASE_URL.startswith("sqlite"):
        Path(DATABASE_URL.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)

    # Try alembic migrations first
    try:
        from alembic.config import Config
        from alembic import command
        alembic_ini = SERVER_DIR / "alembic.ini"
        if alembic_ini.exists():
            alembic_cfg = Config(str(alembic_ini))
            command.upgrade(alembic_cfg, "head")
            logger.info("Alembic migrations applied")
    except Exception as e:
        logger.warning("Alembic migration skipped: %s", e)

    # Safety net: create_all for any tables not in migrations
    Base.metadata.create_all(bind=engine)
    _migrate_add_columns()
    _seed_admin_user()
    _seed_selector_descriptions()


def get_db():
    """FastAPI dependency — yields a DB session per request, auto-closes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

## app/seed.py

```python
"""Seed database from YAML config files. Idempotent — safe to run multiple times."""
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.db_models import Account, SensitiveWord, UISelector, PromptTemplate
from app.config import load_accounts_config, load_selectors_config


def seed_accounts(db: Session) -> int:
    """Import accounts from accounts.yaml. Skips existing (by id)."""
    accounts = load_accounts_config()
    added = 0
    for acc in accounts:
        existing = db.query(Account).filter(Account.id == acc["id"]).first()
        if existing:
            continue
        db.add(Account(
            id=acc["id"],
            nickname=acc.get("nickname", ""),
            douyin_id=acc.get("douyin_id", ""),
            group=acc.get("group", "default"),
            status=acc.get("status", "active"),
            daily_limits=acc.get("daily_limits", {
                "likes": 50, "comments": 20, "follows": 20, "dms": 10, "replies": 15,
            }),
        ))
        added += 1
    db.commit()
    return added


def seed_selectors(db: Session) -> tuple[int, int]:
    """Import selectors from selectors.yaml. Returns (added, updated) counts.

    Only updates strategies if YAML version is higher than the existing version.
    This prevents seed from overwriting manual edits made via the API.
    """
    version, selectors = load_selectors_config()
    added = 0
    updated = 0
    for sel in selectors:
        existing = db.query(UISelector).filter(
            UISelector.action_name == sel["action_name"],
            UISelector.platform_version == sel.get("platform_version", "default"),
        ).first()
        if existing:
            # Only update if YAML version is higher (prevents overwriting manual edits)
            if version > existing.version:
                existing.strategies = sel["strategies"]
                existing.version = version
                updated += 1
            continue
        db.add(UISelector(
            action_name=sel["action_name"],
            platform_version=sel.get("platform_version", "default"),
            strategies=sel["strategies"],
            version=version,
        ))
        added += 1
    db.commit()
    return added, updated


def seed_prompt_templates(db: Session) -> int:
    """Create default prompt template if none exist."""
    existing = db.query(PromptTemplate).first()
    if existing:
        return 0

    default_content = {
        "identity": {
            "role": "「健康生活指南」视角，像一个靠谱的健康科普评论者",
            "constraints": [
                "不是医生，不做诊断，不保证疗效",
                "讨论的是日常饮食、生活习惯，不是治疗方案",
            ],
        },
        "disabledWords": "治愈 / 根治 / 治好 / 疗效保证 / 包好 / 替代药物 / 停药 / 不用吃药 /\n医生 / 我是医生 / 专家 / 我是专家 / 保证有效 / 百分百 / 100% / 神药",
        "semanticGuide": {
            "mission": "这条评论背后是不是一个\"有真实健康需求的人\"",
            "highValueSignals": [
                "提及具体病症/症状：糖尿病、高血压、失眠、便秘、湿气、痛风、关节痛、脱发、过敏、胃病、颈椎、腰椎等",
                "提及具体药物/治疗方式：胰岛素、降压药、降糖药、中药、艾灸、针灸、推拿、拔罐、理疗等",
                "询问\"能不能好/会不会好转\"：有转机不、能恢复吗、还能好吗、有救吗 → 透露出正在经历这个病",
                "询问\"是不是得一直/一辈子\"：是不是得用一辈子、离不开吗、要一直吃吗 → 已在用药，想摆脱依赖",
                "询问\"有什么讲究/注意/忌口\"：有啥讲究、要注意什么、能吃吗、有什么禁忌 → 已在管理这个病",
                "自述症状/经历：\"最近总是…\"、\"我XX已经…年了\"、\"每次…都…\"、\"XX太痛苦了\" → 患者本人或家属",
                "负面情绪+病症信息：\"试了好多方法都不行\"、\"XX反复发作烦死了\" → 高价值截流点",
            ],
            "lowValueSignals": [
                "泛泛而谈无具体内容：\"有道理\"、\"学到了\"、\"不错\"、\"支持\"",
                "纯表情/灌水/刷存在感：\"哈哈哈\"、\"第一\"、\"来了\"、\"打卡\"",
                "只问价格不提任何病症：\"多少钱\"、\"贵吗\" → 可能只是比价",
                "无具体健康信息的空洞提问：\"有用吗\"、\"真的假的\"、\"效果怎么样\" → 信息量为零",
            ],
            "keyExamples": [
                "\"胰岛素是不是得用一辈子呀\" → 具体药物+询问长期性 → 真实糖尿病患者 → 高价值",
                "\"胰岛素使用真的离不开？\" → 具体药物+询问依赖性 → 真实患者在寻求摆脱 → 高价值",
                "\"有转机不\" → 询问好转可能性 → 正在经历病痛 → 高价值",
                "\"胰岛素使用有啥讲究呢\" → 具体药物+寻求指导 → 已在用药，想优化 → 高价值",
                "\"这个有用吗\" → 无具体病名/药名/症状 → 纯路人 → 低价值",
                "\"多少钱\" → 只问价格无病症 → 可能是比价 → 低价值",
            ],
        },
        "analysis": {
            "intents": [
                "consult_intent: 针对具体健康问题的咨询，评论中包含病症/药物/症状/治疗方式",
                "buy_intent: 明确求购，\"怎么买？\"、\"多少钱？\"、\"求链接\"、\"在哪里买\"",
                "compare_intent: 对比选项，\"这个和XX比哪个好？\"",
                "meaningless: 无信息量，纯表情、灌水 — 直接 0 分",
            ],
            "sentiments": [
                "positive (正向): 赞赏、感谢、认同",
                "negative (负向): 抱怨、痛苦、失望 — 如果同时提及病症，是高价值截流点",
                "neutral (中立): 客观提问、陈述",
            ],
            "scoringRules": [
                "consult_intent: 45分 | buy_intent: 50分 | compare_intent: 40分 | meaningless: 0分",
                "negative情感（含病症信息）: +20分 | positive情感: +10分 | neutral: 0分",
                "specific_condition (提及具体病症/药物/症状): +15分",
                "price敏感: +10分 | urgency > 7: +10分",
                "is_bot / is_competitor: 直接 0 分",
            ],
            "replyRules": [
                "目的：回复要吸引对方注意、建立信任、引发进一步交流的意愿",
                "自然接住对方评论，给一条针对性的实用小建议，暗示你在这方面有经验",
                "像健康科普博主回复粉丝一样自然，避免\"亲/亲亲/宝\"等营销口吻",
                "中老年用户居多，不用年轻化网络梗",
                "单条不超过 40 字，信息密度高但不啰嗦",
                "严禁以\"同感\"、\"我也是\"、\"确实\"、\"说得好\"开头 — 每条开头句式必须不同",
                "开头多样化：直接回应问题、给出新角度、反问引发思考、补充对方没说的点",
            ],
            "replyExample": {
                "good": "饭前喝点稀释的苹果水对胃比较温和，可以试试看",
                "bad": "我也是这么觉得的",
            },
            "tiers": {
                "strong_buy": "对方询价/求购，分享使用经验或提出建议",
                "health_consult": "对方健康咨询，从饮食/运动/习惯角度切入",
                "patient_self": "对方自述患者，从家人经历切入，禁止\"我也是\"开头",
                "other": "自然接话，禁止\"同感\"切入",
            },
        },
        "videoComment": {
            "context": "你是一个抖音健康科普博主，正在浏览健康/养生类短视频。你需要在视频下方写一条评论，这条评论会被其他观看此视频的用户看到。",
            "goal": "这条评论就是你的广告位。目标是让看到评论的人觉得你懂行、可信，从而点进你的主页或产生咨询意向。",
            "rules": [
                "吸引注意：开头用提问、反常识观点、或点出视频没说透的细节来抓住眼球",
                "暗示专业：结合视频内容给出一个具体的小知识点或实用建议，让人感觉你懂",
                "引发好奇：留一点没说尽的感觉，让人想进一步了解（但不直接引导私信）",
                "15-40字，口语化但信息密度高",
                "严禁禁用词：治愈/根治/治好/疗效保证/替代药物/停药/医生/专家",
                "严禁直接营销：不带链接、不加微信、不说\"私信我\"、不说\"找我\"",
                "不要以「同感」「我也是」「确实」「说得好」开头 — 太像路人",
            ],
        },
        "dmOpener": {
            "context": "你是一个关心家人健康的普通人，在抖音私信一位对相关话题感兴趣的陌生网友。",
            "identity": {
                "role": "「健康生活指南」视角，像一个靠谱的健康科普账号",
                "constraints": [
                    "不是医生，不是产品顾问，不做诊断，不保证疗效",
                    "讨论的是日常饮食、生活习惯，不是治疗方案",
                ],
            },
            "goal": "自然地接住对方的评论，给出一条实用的生活小建议，不卖货、不留联系方式。以「针对对方评论的实用建议」为切口，不要像客服。",
            "style": [
                "像健康科普博主给建议一样自然，避免\"亲/亲亲/宝\"营销口吻",
                "中老年用户居多，不用年轻化网络梗",
                "单条不超过 50 字，一次只说一件事",
            ],
            "tierTones": {
                "strong_buy": "不报价不发链接，先柔和确认需求背景",
                "health_consult": "以\"我家里也有这种情况，正好一起交流\"切入",
                "patient_self": "先共情，绝不第一条就推销",
                "other": "以\"看到你评论，我这边也关心\"切入",
            },
        },
        "dmStages": {
            "qualifying": {"name": "了解需求", "goal": "只问不卖。确认对方真实场景：本人还是家人、什么情况、日常习惯。每次只问一个问题，不盘问。", "style": "像健康顾问了解情况，朴素具体。共情对方处境。单条 ≤ 50 字。", "maxTokens": 150},
            "nurturing": {"name": "信任培育", "goal": "给出日常饮食/生活习惯的实用建议。用\"可以试试\"\"建议\"\"若想…\"等客观句式。绝不用\"医生说\"\"专家建议\"。仍不卖货不提产品。", "style": "细节感优先：具体做法 > 笼统道理。单条 ≤ 50 字。", "maxTokens": 200},
            "converting": {"name": "转化引导", "goal": "对方释放成交信号。不报价不发链接。确认诉求，表明\"稍后有朋友详细对接\"，让对方愿意等。留一个温和的 gatekeeper 问题。", "style": "语气诚恳不催促。禁止承诺价格/折扣。单条 ≤ 60 字。", "maxTokens": 150},
            "follow_up": {"name": "唤回", "goal": "极其轻量地问一句，不追问不卖货。可以以具体生活场景切入，不是\"在吗/怎么没回\"。单次只发一条。", "style": "语气平和没压迫感。单条 ≤ 40 字。自然，不像群发。", "maxTokens": 120},
        },
        "localFilter": {
            "exclude": [
                "游戏", "电竞", "王者荣耀", "原神", "吃鸡", "英雄联盟",
                "汽车", "改装", "二手车", "驾照", "科目",
                "编程", "python", "java", "代码", "程序员",
                "美妆", "口红", "粉底", "眼影", "护肤",
                "穿搭", "潮牌", "aj", "球鞋", "aj1",
                "装修", "硬装", "软装", "瓷砖", "地板",
                "股票", "基金", "a股", "k线", "涨停",
                "追星", "饭圈", "爱豆", "应援",
            ],
            "include": [
                "养生", "保健", "中医", "食疗", "营养", "运动", "健身",
                "心理", "睡眠", "失眠", "减肥", "瘦身", "排毒",
                "气血", "经络", "穴位", "艾灸", "拔罐", "推拿",
                "食补", "药膳", "茶饮", "枸杞", "红枣",
                "瑜伽", "太极", "跑步", "拉伸", "有氧",
                "血压", "血糖", "血脂", "胆固醇", "尿酸",
                "肠胃", "便秘", "湿气", "上火", "感冒",
                "免疫力", "抗衰老", "胶原蛋白", "维c", "维生素",
                "慢病", "亚健康", "调理", "体质", "寒凉",
                "大健康", "健康管理", "体重管理",
            ],
        },
    }

    db.add(PromptTemplate(
        name="health-default",
        industry="health",
        description="大健康行业默认提示词模板",
        content=default_content,
        version=1,
    ))
    db.commit()
    return 1


def seed_sensitive_words(db: Session) -> int:
    """Load default sensitive words from YAML config."""
    words_path = Path(__file__).parent.parent / "config" / "sensitive_words.yaml"
    if not words_path.exists():
        return 0
    with open(words_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    words = data.get("words", [])
    added = 0
    for word in words:
        existing = db.query(SensitiveWord).filter(SensitiveWord.word == word).first()
        if not existing:
            db.add(SensitiveWord(word=word))
            added += 1
    db.commit()
    return added


def seed_all():
    """Run all seed operations. Call at startup."""
    init_db()
    db = SessionLocal()
    try:
        acc_count = seed_accounts(db)
        sel_added, sel_updated = seed_selectors(db)
        tmpl_count = seed_prompt_templates(db)
        words_added = seed_sensitive_words(db)
        print(f"Seed complete: {acc_count} accounts added, {sel_added} selectors added, {sel_updated} selectors updated, {tmpl_count} prompt templates added, {words_added} sensitive words added")
    finally:
        db.close()


if __name__ == "__main__":
    seed_all()
```

## app/ws_manager.py

```python
"""WebSocket connection manager for pairing push notifications."""
from fastapi import WebSocket
import asyncio


class PairWSManager:
    """Manages WebSocket connections for pairing: devices waiting + admin subscribers."""

    def __init__(self):
        # Device connections: pairing_token → WebSocket
        self._device_connections: dict[str, WebSocket] = {}
        # Admin connections: user_id → set of WebSockets
        self._admin_connections: dict[str, set[WebSocket]] = {}
        # Device status connections: device_id → WebSocket
        self._device_status_connections: dict[str, WebSocket] = {}
        # Heartbeat memory cache: device_id → datetime
        self._device_last_seen: dict[str, object] = {}

    # --- Device side (waiting for approval) ---

    async def register_device(self, token: str, ws: WebSocket):
        await ws.accept()
        self._device_connections[token] = ws

    def unregister_device(self, token: str):
        self._device_connections.pop(token, None)

    async def notify_device(self, token: str, data: dict):
        """Push result to the waiting device, then close."""
        ws = self._device_connections.pop(token, None)
        if ws:
            try:
                await ws.send_json(data)
                await ws.close()
            except Exception:
                pass

    # --- Admin side (subscribing to events) ---

    async def register_admin(self, ws: WebSocket, user_id: str = ""):
        await ws.accept()
        self._admin_connections.setdefault(user_id, set()).add(ws)

    def unregister_admin(self, ws: WebSocket):
        for user_id, wss in list(self._admin_connections.items()):
            wss.discard(ws)
            if not wss:
                del self._admin_connections[user_id]

    async def broadcast_to_admins(self, data: dict, user_ids: list[str] = None):
        """Broadcast event to admin clients. If user_ids given, only to those users."""
        dead = []
        items = self._admin_connections.items()
        for user_id, wss in items:
            if user_ids is not None and user_id not in user_ids:
                continue
            for ws in list(wss):
                try:
                    await ws.send_json(data)
                except Exception:
                    dead.append((user_id, ws))
        for user_id, ws in dead:
            wss = self._admin_connections.get(user_id)
            if wss:
                wss.discard(ws)
                if not wss:
                    del self._admin_connections[user_id]

    async def broadcast_channel_progress(self, channel_id: str, stats: dict):
        """Push channel progress event to admin WS connections."""
        await self.broadcast_to_admins({
            "event": "channel_progress",
            "channel_id": channel_id,
            **stats,
        })

    async def broadcast_channel_completed(self, channel_id: str):
        """Push channel completed event to admin WS connections."""
        await self.broadcast_to_admins({
            "event": "channel_completed",
            "channel_id": channel_id,
        })

    # --- Heartbeat memory cache (avoids DB write on every ping) ---

    def record_heartbeat(self, device_id: str, seen_at):
        """Record heartbeat in memory. Caller flushes to DB periodically."""
        self._device_last_seen[device_id] = seen_at

    def get_last_seen(self, device_id: str):
        """Get the in-memory last seen time, or None."""
        return self._device_last_seen.get(device_id)

    def drain_heartbeats(self) -> dict[str, object]:
        """Atomically swap out all in-memory heartbeats for DB flush."""
        heartbeats = self._device_last_seen
        self._device_last_seen = {}
        return heartbeats

    # --- Device status connections (persistent WS for online/offline) ---

    async def register_device_status(self, device_id: str, ws: WebSocket):
        """Register a device's persistent status connection.
        Caller must have already accepted the WebSocket before calling this.
        """
        # 先替换再关旧连接：旧连接的 finally 块检查时会发现已不是活跃连接，跳过离线标记
        old = self._device_status_connections.get(device_id)
        self._device_status_connections[device_id] = ws
        if old:
            try:
                await old.close()
            except Exception:
                pass

    def unregister_device_status(self, device_id: str):
        """Remove device status connection (device disconnected)."""
        self._device_status_connections.pop(device_id, None)

    def is_device_online(self, device_id: str) -> bool:
        """Check if device has an active status connection."""
        return device_id in self._device_status_connections

    async def send_to_device(self, device_id: str, data: dict) -> bool:
        """Push a message to a specific device. Returns True if sent."""
        ws = self._device_status_connections.get(device_id)
        if not ws:
            return False
        try:
            await ws.send_json(data)
            return True
        except Exception:
            self._device_status_connections.pop(device_id, None)
            return False

    async def disconnect_device(self, device_id: str) -> bool:
        """Forcefully close a device's status WebSocket connection.

        Returns True if a connection was found and closed.
        The device's onClosing handler will detect the disconnect and
        the server-side ws_device_status handler will mark it offline.
        """
        ws = self._device_status_connections.pop(device_id, None)
        if not ws:
            return False
        try:
            await ws.close(code=4002, reason="Admin forced disconnect")
        except Exception:
            pass
        return True

    async def broadcast_to_devices(self, data: dict):
        """Broadcast a message to all connected devices."""
        dead = []
        for device_id, ws in self._device_status_connections.items():
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(device_id)
        for device_id in dead:
            self._device_status_connections.pop(device_id, None)

    # --- Backward compat aliases ---

    async def register(self, token: str, ws: WebSocket):
        await self.register_device(token, ws)

    def unregister(self, token: str):
        self.unregister_device(token)

    async def notify(self, token: str, data: dict):
        await self.notify_device(token, data)

    def has_connection(self, token: str) -> bool:
        return token in self._device_connections


pair_ws_manager = PairWSManager()
```

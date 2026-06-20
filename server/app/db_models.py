"""SQLAlchemy ORM models — database persistence layer."""
from datetime import datetime, timezone

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text, Boolean,
    JSON, ForeignKey, UniqueConstraint, Index, Table,
    func,
)
from sqlalchemy.orm import relationship

from app.db.models.device_operations import DevicePairRequest
from app.db.models.content_collection import ContentTemplate, SensitiveWord
from app.db.models.system_configuration import SystemSetting


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
    lease_id = Column(String(36), nullable=True, default=None)

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
    retry_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    completed_at = Column(DateTime, nullable=True)

    channel = relationship("Channel", back_populates="items")
    account = relationship("Account")
    device = relationship("Device")
    task = relationship("Task")


class StatsEvent(Base):
    """Idempotent stats event — each operation recorded once by composite key."""
    __tablename__ = "stats_events"
    __table_args__ = (
        UniqueConstraint("task_id", "device_id", "event_type", "target_id", "op_index",
                         name="uq_stats_event_idempotent"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False, index=True)
    device_id = Column(String(36), ForeignKey("devices.id"), nullable=False)
    account_id = Column(String(36), ForeignKey("accounts.id"), nullable=False)
    event_type = Column(String(30), nullable=False)
    target_id = Column(String(200), nullable=False)
    op_index = Column(Integer, nullable=False, default=0)
    count = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())


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
    source_comment_content = Column(Text, nullable=True)  # 触发用户采集的入口评论内容
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
    anchors = relationship("CharacterAnchor", back_populates="character", cascade="all, delete-orphan")


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
    anchors = relationship("SceneAnchor", back_populates="scene", cascade="all, delete-orphan")


class CharacterAnchor(Base):
    __tablename__ = "character_anchors"
    __table_args__ = (
        UniqueConstraint("character_id", "reference_slot", name="uq_character_anchor_slot"),
        Index("idx_character_anchors_character_id", "character_id"),
        Index("idx_character_anchors_status", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    character_id = Column(String(36), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False, default="")
    reference_slot = Column(String(80), nullable=False, default="avatar_front_url")
    base_prompt = Column(Text, nullable=False, default="")
    anchor_image_url = Column(Text, nullable=True)
    seed = Column(Integer, nullable=True)
    ref_mode = Column(String(80), nullable=False, default="character_face")
    provider_options_json = Column(JSON, nullable=True, default=dict)
    status = Column(String(30), nullable=False, default="draft")
    metadata_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    character = relationship("Character", back_populates="anchors")


class SceneAnchor(Base):
    __tablename__ = "scene_anchors"
    __table_args__ = (
        UniqueConstraint("scene_id", "reference_slot", name="uq_scene_anchor_slot"),
        Index("idx_scene_anchors_scene_id", "scene_id"),
        Index("idx_scene_anchors_status", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    scene_id = Column(String(36), ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False)
    scene_name = Column(String(100), nullable=False, default="")
    reference_slot = Column(String(80), nullable=False, default="reference_wideshot_url")
    environment_prompt = Column(Text, nullable=False, default="")
    anchor_image_url = Column(Text, nullable=True)
    seed = Column(Integer, nullable=True)
    ref_mode = Column(String(80), nullable=False, default="scene_environment")
    provider_options_json = Column(JSON, nullable=True, default=dict)
    status = Column(String(30), nullable=False, default="draft")
    metadata_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    scene = relationship("Scene", back_populates="anchors")


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


class ProductionPlan(Base):
    __tablename__ = "production_plans"

    id = Column(String(36), primary_key=True, default=_uuid)
    series_id = Column(String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(30), nullable=False, default="draft")
    active_version = Column(Integer, nullable=False, default=1)
    target_total_duration_seconds = Column(Integer, nullable=False, default=0)
    budget_limit = Column(Float, nullable=True)
    current_cost = Column(Float, nullable=False, default=0.0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        Index("idx_production_plans_series_id", "series_id"),
        Index("idx_production_plans_status", "status"),
    )


class ProductionPlanVersion(Base):
    __tablename__ = "production_plan_versions"
    __table_args__ = (
        UniqueConstraint("plan_id", "version", name="uq_production_plan_version"),
        Index("idx_production_plan_versions_plan_id", "plan_id"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    style_lock_json = Column(JSON, nullable=True, default=dict)
    model_config_snapshot_json = Column(JSON, nullable=True, default=dict)
    prompt_policy_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())


class ProductionEpisode(Base):
    __tablename__ = "production_episodes"
    __table_args__ = (
        UniqueConstraint("plan_id", "episode_id", name="uq_production_episode_plan_episode"),
        Index("idx_production_episodes_plan_id", "plan_id"),
        Index("idx_production_episodes_episode_id", "episode_id"),
        Index("idx_production_episodes_status", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False)
    order_index = Column(Integer, nullable=False, default=0)
    status = Column(String(30), nullable=False, default="planned")
    target_duration_seconds = Column(Integer, nullable=False, default=0)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class ProductionScene(Base):
    __tablename__ = "production_scenes"
    __table_args__ = (
        UniqueConstraint("episode_plan_id", "scene_id", name="uq_production_scene_episode_scene"),
        Index("idx_production_scenes_episode_plan_id", "episode_plan_id"),
        Index("idx_production_scenes_status", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    episode_plan_id = Column(String(36), ForeignKey("production_episodes.id", ondelete="CASCADE"), nullable=False)
    scene_id = Column(String(100), nullable=False)
    order_index = Column(Integer, nullable=False, default=0)
    status = Column(String(30), nullable=False, default="planned")
    location_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class ProductionShot(Base):
    __tablename__ = "production_shots"
    __table_args__ = (
        UniqueConstraint("scene_plan_id", "shot_id", name="uq_production_shot_scene_shot"),
        Index("idx_production_shots_scene_plan_id", "scene_plan_id"),
        Index("idx_production_shots_status", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    scene_plan_id = Column(String(36), ForeignKey("production_scenes.id", ondelete="CASCADE"), nullable=False)
    shot_id = Column(String(100), nullable=False)
    order_index = Column(Integer, nullable=False, default=0)
    status = Column(String(30), nullable=False, default="planned")
    character_ids = Column(JSON, nullable=False, default=list)
    action = Column(Text, nullable=False, default="")
    emotion = Column(String(50), nullable=True)
    shot_type = Column(String(50), nullable=False, default="medium")
    duration_seconds = Column(Float, nullable=False, default=5.0)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class ProductionSegment(Base):
    __tablename__ = "production_segments"
    __table_args__ = (
        UniqueConstraint("shot_plan_id", "segment_id", "version", name="uq_production_segment_version"),
        Index("idx_production_segments_shot_plan_id", "shot_plan_id"),
        Index("idx_production_segments_previous_segment_id", "previous_segment_id"),
        Index("idx_production_segments_status", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    shot_plan_id = Column(String(36), ForeignKey("production_shots.id", ondelete="CASCADE"), nullable=False)
    previous_segment_id = Column(String(36), ForeignKey("production_segments.id", ondelete="SET NULL"), nullable=True)
    segment_id = Column(String(100), nullable=False)
    order_index = Column(Integer, nullable=False, default=0)
    status = Column(String(30), nullable=False, default="planned")
    duration_seconds = Column(Float, nullable=False, default=5.0)
    continuity_mode = Column(String(50), nullable=False, default="narrative_cut")
    version = Column(Integer, nullable=False, default=1)
    previous_end_frame_url = Column(Text, nullable=True)
    expected_end_state = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    image_prompt = Column(Text, nullable=False, default="")
    video_prompt = Column(Text, nullable=False, default="")
    narration = Column(Text, nullable=True)
    reference_roles_json = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class ProductionJob(Base):
    __tablename__ = "production_jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_production_jobs_idempotency_key"),
        Index("idx_production_jobs_plan_id", "plan_id"),
        Index("idx_production_jobs_target", "target_type", "target_id"),
        Index("idx_production_jobs_status", "status"),
        Index("idx_production_jobs_plan_status_resume", "plan_id", "status", "resume_status"),
        Index("idx_production_jobs_plan_stage_status", "plan_id", "stage", "status"),
        Index("idx_production_jobs_stage_created_at", "stage", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False)
    target_type = Column(String(30), nullable=False)
    target_id = Column(String(36), nullable=False)
    stage = Column(String(80), nullable=False)
    status = Column(String(30), nullable=False, default="queued")
    provider_task_id = Column(String(120), nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    retry_after = Column(DateTime, nullable=True)
    lease_id = Column(String(80), nullable=True)
    leased_until = Column(DateTime, nullable=True)
    priority = Column(Integer, nullable=False, default=100)
    scheduled_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_code = Column(String(80), nullable=True)
    error_message = Column(Text, nullable=True)
    retryable = Column(Boolean, nullable=False, default=True)
    idempotency_key = Column(String(200), nullable=False)
    resume_status = Column(String(30), nullable=True)
    blocked_reason = Column(String(120), nullable=True)
    paused_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class ProviderStageTask(Base):
    __tablename__ = "provider_stage_tasks"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_provider_stage_tasks_idempotency"),
        Index("idx_provider_stage_tasks_run_stage_status", "run_id", "stage", "status"),
        Index("idx_provider_stage_tasks_plan_stage_status", "plan_id", "stage", "status"),
        Index("idx_provider_stage_tasks_target", "target_type", "target_id"),
        Index("idx_provider_stage_tasks_provider_task_id", "provider_task_id"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    run_id = Column(String(36), ForeignKey("video_production_runs.id", ondelete="CASCADE"), nullable=False)
    plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(String(36), ForeignKey("production_jobs.id", ondelete="SET NULL"), nullable=True)
    target_type = Column(String(30), nullable=False)
    target_id = Column(String(36), nullable=False)
    stage = Column(String(40), nullable=False)
    provider = Column(String(80), nullable=False)
    model_name = Column(String(120), nullable=False)
    request_hash = Column(String(64), nullable=False)
    idempotency_key = Column(String(220), nullable=False)
    status = Column(String(40), nullable=False, default="reserved")
    provider_task_id = Column(String(160), nullable=True)
    external_task_id = Column(String(160), nullable=True)
    error_code = Column(String(80), nullable=True)
    error_message = Column(Text, nullable=True)
    response_summary_json = Column(JSON, nullable=True, default=dict)
    submitted_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class ProviderCostReservation(Base):
    __tablename__ = "provider_cost_reservations"
    __table_args__ = (
        UniqueConstraint(
            "provider_stage_task_id",
            name="uq_provider_cost_reservation_stage_task",
        ),
        Index("idx_provider_cost_reservations_plan_status", "plan_id", "status"),
        Index("idx_provider_cost_reservations_expires", "expires_at", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False)
    provider_stage_task_id = Column(
        String(36),
        ForeignKey("provider_stage_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    status = Column(String(40), nullable=False, default="active_unsubmitted")
    estimated_cost = Column(Float, nullable=False, default=0.0)
    reserved_cost = Column(Float, nullable=False, default=0.0)
    actual_cost = Column(Float, nullable=True)
    currency = Column(String(10), nullable=False, default="CNY")
    units_json = Column(JSON, nullable=True, default=dict)
    expires_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    settled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class ProductionCostEvent(Base):
    __tablename__ = "production_cost_events"
    __table_args__ = (
        Index("idx_production_cost_events_plan_id", "plan_id"),
        Index("idx_production_cost_events_episode_plan_id", "episode_plan_id"),
        Index("idx_production_cost_events_segment_id", "segment_id"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False)
    episode_plan_id = Column(String(36), ForeignKey("production_episodes.id", ondelete="SET NULL"), nullable=True)
    segment_id = Column(String(36), ForeignKey("production_segments.id", ondelete="SET NULL"), nullable=True)
    stage = Column(String(40), nullable=False)
    model_config_id = Column(String(36), nullable=True)
    config_version = Column(Integer, nullable=False, default=1)
    provider_task_id = Column(String(120), nullable=True)
    provider = Column(String(50), nullable=False, default="")
    model_name = Column(String(100), nullable=False, default="")
    estimated_cost = Column(Float, nullable=False, default=0.0)
    actual_cost = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), nullable=False, default="CNY")
    units_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())


class AgencyExpertInvocation(Base):
    __tablename__ = "agency_expert_invocations"
    __table_args__ = (
        Index("idx_agency_invocations_series_created", "series_id", "created_at"),
        Index("idx_agency_invocations_series_run_stage", "series_id", "run_id", "stage"),
        Index("idx_agency_invocations_run_stage_created", "run_id", "stage", "created_at"),
        Index("idx_agency_invocations_pipeline_stage_created", "pipeline_run_id", "stage", "created_at"),
        Index("idx_agency_invocations_plan_episode_stage", "production_plan_id", "production_episode_id", "stage"),
        Index("idx_agency_invocations_expert_result_created", "expert_id", "result_status", "created_at"),
        Index("idx_agency_invocations_error_created", "error_code", "created_at"),
        Index("idx_agency_invocations_idempotency", "idempotency_key", unique=True),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    idempotency_key = Column(String(160), nullable=False)
    attempt = Column(Integer, nullable=False, default=1)
    retry_of_invocation_id = Column(
        String(36),
        ForeignKey("agency_expert_invocations.id", ondelete="SET NULL"),
        nullable=True,
    )
    series_id = Column(String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True)
    run_id = Column(String(36), ForeignKey("video_production_runs.id", ondelete="SET NULL"), nullable=True)
    production_plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="SET NULL"), nullable=True)
    production_episode_id = Column(String(36), ForeignKey("production_episodes.id", ondelete="SET NULL"), nullable=True)
    production_segment_id = Column(String(36), ForeignKey("production_segments.id", ondelete="SET NULL"), nullable=True)
    pipeline_run_id = Column(String(36), ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True)
    stage = Column(String(40), nullable=False)
    expert_id = Column(String(80), nullable=False)
    role = Column(String(20), nullable=False)
    execution_status = Column(String(20), nullable=False, default="queued")
    result_status = Column(String(20), nullable=False, default="pending")
    input_summary_json = Column(JSON, nullable=True, default=dict)
    output_summary_json = Column(JSON, nullable=True, default=dict)
    evidence_json = Column(JSON, nullable=True, default=list)
    source_repo = Column(String(120), nullable=False, default="jnMetaCode/agency-agents-zh")
    source_commit = Column(String(80), nullable=False, default="")
    source_path = Column(String(240), nullable=False, default="")
    source_sha256 = Column(String(64), nullable=False, default="")
    model_config_snapshot_json = Column(JSON, nullable=True, default=dict)
    token_usage_json = Column(JSON, nullable=True, default=dict)
    duration_ms = Column(Integer, nullable=False, default=0)
    error_code = Column(String(80), nullable=True)
    error_message = Column(Text, nullable=True)
    repair_action = Column(Text, nullable=True)
    repair_route = Column(Text, nullable=True)
    repair_target_type = Column(String(80), nullable=True)
    repair_target_ids_json = Column(JSON, nullable=True, default=list)
    retry_scope = Column(String(80), nullable=True)
    created_at = Column(DateTime, nullable=False, default=bj_now)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)


class AgencyCreativePatch(Base):
    __tablename__ = "agency_creative_patches"
    __table_args__ = (
        Index("idx_agency_creative_patches_series_created", "series_id", "created_at"),
        Index("idx_agency_creative_patches_run_status", "run_id", "status"),
        Index("idx_agency_creative_patches_invocation", "source_invocation_id"),
        Index("idx_agency_creative_patches_target_status", "target_type", "target_id", "status"),
        Index("idx_agency_creative_patches_plan_stage_status", "production_plan_id", "stage", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    series_id = Column(String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True)
    run_id = Column(String(36), ForeignKey("video_production_runs.id", ondelete="SET NULL"), nullable=True)
    production_plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="SET NULL"), nullable=True)
    production_episode_id = Column(String(36), ForeignKey("production_episodes.id", ondelete="SET NULL"), nullable=True)
    production_segment_id = Column(String(36), ForeignKey("production_segments.id", ondelete="SET NULL"), nullable=True)
    source_invocation_id = Column(String(36), ForeignKey("agency_expert_invocations.id", ondelete="SET NULL"), nullable=True)
    stage = Column(String(40), nullable=False)
    expert_id = Column(String(80), nullable=False, default="")
    patch_type = Column(String(40), nullable=False)
    target_type = Column(String(40), nullable=False)
    target_id = Column(String(100), nullable=False)
    title = Column(String(200), nullable=False, default="")
    reason = Column(Text, nullable=False, default="")
    before_json = Column(JSON, nullable=False, default=dict)
    after_json = Column(JSON, nullable=False, default=dict)
    status = Column(String(30), nullable=False, default="proposed")
    priority = Column(String(20), nullable=False, default="normal")
    reviewer_user_id = Column(String(36), nullable=True)
    applied_at = Column(DateTime, nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class AITextArtifact(Base):
    __tablename__ = "ai_text_artifacts"
    __table_args__ = (
        UniqueConstraint("target_type", "target_id", "artifact_type", "version", name="uq_ai_text_artifact_version"),
        Index("idx_ai_text_artifacts_series_type_status", "series_id", "artifact_type", "status"),
        Index("idx_ai_text_artifacts_episode_type_status", "episode_id", "artifact_type", "status"),
        Index("idx_ai_text_artifacts_target_type", "target_type", "target_id", "artifact_type"),
        Index("idx_ai_text_artifacts_parent", "parent_artifact_id"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    series_id = Column(String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True)
    run_id = Column(String(36), ForeignKey("video_production_runs.id", ondelete="SET NULL"), nullable=True)
    production_plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="SET NULL"), nullable=True)
    target_type = Column(String(80), nullable=False)
    target_id = Column(String(120), nullable=False)
    artifact_type = Column(String(80), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    status = Column(String(30), nullable=False, default="review_pending")
    source_type = Column(String(30), nullable=False, default="ai")
    parent_artifact_id = Column(String(36), ForeignKey("ai_text_artifacts.id", ondelete="SET NULL"), nullable=True)
    input_json = Column(JSON, nullable=True, default=dict)
    content_json = Column(JSON, nullable=True, default=dict)
    content_text = Column(Text, nullable=True)
    model_trace_json = Column(JSON, nullable=True, default=dict)
    review_trace_json = Column(JSON, nullable=True, default=dict)
    consumer_trace_json = Column(JSON, nullable=True, default=dict)
    created_by = Column(String(36), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    approved_at = Column(DateTime, nullable=True)
    superseded_at = Column(DateTime, nullable=True)
    stale_reason = Column(Text, nullable=True)


class AITextArtifactConsumer(Base):
    __tablename__ = "ai_text_artifact_consumers"
    __table_args__ = (
        Index("idx_ai_text_artifact_consumers_artifact", "artifact_id"),
        Index("idx_ai_text_artifact_consumers_consumer", "consumer_type", "consumer_id"),
        Index("idx_ai_text_artifact_consumers_run", "run_id"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    artifact_id = Column(String(36), ForeignKey("ai_text_artifacts.id", ondelete="CASCADE"), nullable=False)
    consumer_type = Column(String(80), nullable=False)
    consumer_id = Column(String(120), nullable=False)
    series_id = Column(String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True)
    run_id = Column(String(36), ForeignKey("video_production_runs.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    metadata_json = Column(JSON, nullable=True, default=dict)


class ProductionAuditEvent(Base):
    __tablename__ = "production_audit_events"
    __table_args__ = (
        Index("idx_production_audit_events_run_id", "run_id"),
        Index("idx_production_audit_events_plan_id", "production_plan_id"),
        Index("idx_production_audit_events_segment_id", "production_segment_id"),
        Index("idx_production_audit_events_type", "event_type"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    event_type = Column(String(80), nullable=False)
    run_id = Column(String(36), ForeignKey("video_production_runs.id", ondelete="SET NULL"), nullable=True)
    production_plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="SET NULL"), nullable=True)
    production_episode_id = Column(String(36), ForeignKey("production_episodes.id", ondelete="SET NULL"), nullable=True)
    production_segment_id = Column(String(36), ForeignKey("production_segments.id", ondelete="SET NULL"), nullable=True)
    provider_task_id = Column(String(120), nullable=True)
    actor_user_id = Column(String(36), nullable=True)
    actor_role = Column(String(40), nullable=True)
    payload_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())


class VideoCollection(Base):
    __tablename__ = "video_collections"

    id = Column(String(36), primary_key=True, default=_uuid)
    series_id = Column(String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(30), nullable=False, default="draft")
    included_episode_ids = Column(JSON, nullable=False, default=list)
    duration_seconds = Column(Float, nullable=False, default=0.0)
    video_url = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        Index("idx_video_collections_series_id", "series_id"),
        Index("idx_video_collections_status", "status"),
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


class EpisodeScript(Base):
    __tablename__ = "episode_scripts"
    __table_args__ = (
        Index("idx_episode_scripts_series_episode", "series_id", "episode_id"),
        Index("idx_episode_scripts_pipeline_run", "pipeline_run_id"),
        Index("idx_episode_scripts_status", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    series_id = Column(String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False)
    pipeline_run_id = Column(String(36), ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True)
    source_prompt = Column(Text, nullable=False)
    tags_json = Column(JSON, nullable=True, default=list)
    target_duration_seconds = Column(Integer, nullable=False, default=60)
    status = Column(String(30), nullable=False, default="draft")
    agency_trace_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class ScriptDramaticBeat(Base):
    __tablename__ = "script_dramatic_beats"
    __table_args__ = (
        UniqueConstraint("script_id", "order_index", name="uq_script_dramatic_beat_order"),
        Index("idx_script_dramatic_beats_script_id", "script_id"),
        Index("idx_script_dramatic_beats_type", "beat_type"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    script_id = Column(String(36), ForeignKey("episode_scripts.id", ondelete="CASCADE"), nullable=False)
    order_index = Column(Integer, nullable=False)
    beat_type = Column(String(40), nullable=False)
    emotional_value = Column(String(40), nullable=False)
    plot_summary = Column(Text, nullable=False)


class ScriptSceneOutline(Base):
    __tablename__ = "script_scene_outlines"
    __table_args__ = (
        UniqueConstraint("script_id", "scene_number", name="uq_script_scene_outline_number"),
        Index("idx_script_scene_outlines_script_id", "script_id"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    script_id = Column(String(36), ForeignKey("episode_scripts.id", ondelete="CASCADE"), nullable=False)
    scene_number = Column(Integer, nullable=False)
    dramatic_beat_type = Column(String(40), nullable=False)
    location = Column(String(160), nullable=False)
    characters_json = Column(JSON, nullable=True, default=list)
    conflict = Column(Text, nullable=False)
    emotional_turn = Column(Text, nullable=False)
    visual_mandate = Column(Text, nullable=False)


class ScriptVisualShot(Base):
    __tablename__ = "script_visual_shots"
    __table_args__ = (
        UniqueConstraint("script_id", "shot_number", name="uq_script_visual_shot_number"),
        Index("idx_script_visual_shots_script_id", "script_id"),
        Index("idx_script_visual_shots_scene", "script_id", "scene_number"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    script_id = Column(String(36), ForeignKey("episode_scripts.id", ondelete="CASCADE"), nullable=False)
    shot_number = Column(Integer, nullable=False)
    scene_number = Column(Integer, nullable=False)
    beat_type = Column(String(40), nullable=False)
    narration = Column(Text, nullable=False)
    visual_prompt = Column(Text, nullable=False)
    video_prompt = Column(Text, nullable=False)
    duration = Column(Float, nullable=False)


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


class VideoProductionRun(Base):
    """One staged automated production attempt for an episode."""
    __tablename__ = "video_production_runs"

    id = Column(String(36), primary_key=True, default=_uuid)
    series_id = Column(String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(40), nullable=False, default="draft")
    current_stage = Column(String(40), nullable=False, default="draft")
    run_type = Column(String(40), nullable=False, default="legacy_episode_run")
    pixelle_stage_task_id = Column(String(100), nullable=True)
    production_plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="SET NULL"), nullable=True)
    production_episode_id = Column(String(36), ForeignKey("production_episodes.id", ondelete="SET NULL"), nullable=True)
    production_link_status = Column(String(30), nullable=False, default="legacy_unlinked")
    storyboard_json = Column(JSON, nullable=True, default=dict)
    model_trace_json = Column(JSON, nullable=True, default=dict)
    edit_manifest_json = Column(JSON, nullable=True, default=dict)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        Index("idx_video_production_runs_series_episode", "series_id", "episode_id"),
        Index("idx_video_production_runs_status", "status"),
        Index("idx_video_production_runs_type", "run_type"),
        Index("idx_video_production_runs_production_links", "production_plan_id", "production_episode_id"),
        Index("idx_video_production_runs_link_status", "production_link_status"),
    )


class VideoProductionAsset(Base):
    """Intermediate or final asset created by staged production."""
    __tablename__ = "video_production_assets"

    id = Column(String(36), primary_key=True, default=_uuid)
    run_id = Column(String(36), ForeignKey("video_production_runs.id", ondelete="CASCADE"), nullable=False)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False)
    frame_id = Column(String(100), nullable=False)
    asset_type = Column(String(30), nullable=False)
    stage = Column(String(40), nullable=False)
    url = Column(Text, nullable=True)
    local_path = Column(Text, nullable=True)
    thumbnail_url = Column(Text, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    metadata_json = Column(JSON, nullable=True, default=dict)
    status = Column(String(40), nullable=False, default="generated")
    pixelle_task_id = Column(String(100), nullable=True)
    production_segment_id = Column(String(36), ForeignKey("production_segments.id", ondelete="SET NULL"), nullable=True)
    production_shot_id = Column(String(36), ForeignKey("production_shots.id", ondelete="SET NULL"), nullable=True)
    target_type = Column(String(30), nullable=True)
    target_id = Column(String(36), nullable=True)
    provider_task_id = Column(String(120), nullable=True)
    provider_stage_task_id = Column(String(36), ForeignKey("provider_stage_tasks.id", ondelete="SET NULL"), nullable=True)
    prompt_hash = Column(String(64), nullable=True)
    storage_path = Column(Text, nullable=True)
    source_url = Column(Text, nullable=True)
    storage_error_json = Column(JSON, nullable=True, default=dict)
    provider_response_summary_json = Column(JSON, nullable=True, default=dict)
    is_latest = Column(Boolean, nullable=False, default=True)
    source_version = Column(Integer, nullable=False, default=1)
    copy_status = Column(String(30), nullable=False, default="registered")
    checksum = Column(String(120), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        Index("idx_video_assets_run_stage", "run_id", "stage"),
        Index("idx_video_assets_run_frame", "run_id", "frame_id"),
        Index("idx_video_assets_status", "status"),
        Index("idx_video_assets_production_segment", "production_segment_id"),
        Index("idx_video_assets_production_shot", "production_shot_id"),
        Index("idx_video_assets_target", "target_type", "target_id"),
        Index("idx_video_assets_provider_stage_task", "provider_stage_task_id"),
        Index("idx_video_assets_segment_latest", "production_segment_id", "asset_type", "is_latest"),
        UniqueConstraint("run_id", "frame_id", "asset_type", "version", name="uq_video_asset_version"),
    )


class VideoReviewRecord(Base):
    """AI or human review decision for a production asset."""
    __tablename__ = "video_review_records"

    id = Column(String(36), primary_key=True, default=_uuid)
    asset_id = Column(String(36), ForeignKey("video_production_assets.id", ondelete="CASCADE"), nullable=False)
    run_id = Column(String(36), ForeignKey("video_production_runs.id", ondelete="CASCADE"), nullable=False)
    review_type = Column(String(20), nullable=False)
    status = Column(String(30), nullable=False)
    score = Column(Float, nullable=True)
    criteria_json = Column(JSON, nullable=True, default=list)
    issues_json = Column(JSON, nullable=True, default=list)
    reviewer_user_id = Column(String(36), nullable=True)
    reviewer_role = Column(String(40), nullable=True)
    action = Column(String(40), nullable=True)
    model_trace_json = Column(JSON, nullable=True, default=dict)
    asset_snapshot_json = Column(JSON, nullable=True, default=dict)
    model_trace_summary_json = Column(JSON, nullable=True, default=dict)
    comment = Column(Text, nullable=True)
    target_type = Column(String(30), nullable=True)
    target_id = Column(String(36), nullable=True)
    production_segment_id = Column(String(36), ForeignKey("production_segments.id", ondelete="SET NULL"), nullable=True)
    asset_version = Column(Integer, nullable=True)
    is_latest_asset_review = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    __table_args__ = (
        Index("idx_video_review_asset", "asset_id"),
        Index("idx_video_review_run", "run_id"),
        Index("idx_video_review_status", "status"),
        Index("idx_video_review_target_version", "target_type", "target_id", "asset_version"),
    )


class ImageProductionPolicyVersion(Base):
    __tablename__ = "image_production_policy_versions"

    id = Column(String(36), primary_key=True, default=_uuid)
    policy_type = Column(String(30), nullable=False)
    name = Column(String(120), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    snapshot_json = Column(JSON, nullable=False, default=dict)
    status = Column(String(30), nullable=False, default="active")
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        UniqueConstraint("policy_type", "name", "version", name="uq_image_policy_version"),
        Index("idx_image_policy_versions_type_status", "policy_type", "status"),
    )


class ImageProductionStrategy(Base):
    __tablename__ = "image_production_strategies"

    id = Column(String(36), primary_key=True, default=_uuid)
    slug = Column(String(120), nullable=False)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    destination_role = Column(String(80), nullable=False)
    supported_modes_json = Column(JSON, nullable=False, default=list)
    default_model_id = Column(String(36), ForeignKey("ai_models.id", ondelete="SET NULL"), nullable=True)
    fallback_model_ids_json = Column(JSON, nullable=False, default=list)
    common_parameters_json = Column(JSON, nullable=False, default=dict)
    provider_options_json = Column(JSON, nullable=False, default=dict)
    review_policy_version_id = Column(String(36), ForeignKey("image_production_policy_versions.id", ondelete="SET NULL"), nullable=True)
    cost_policy_version_id = Column(String(36), ForeignKey("image_production_policy_versions.id", ondelete="SET NULL"), nullable=True)
    capacity_policy_version_id = Column(String(36), ForeignKey("image_production_policy_versions.id", ondelete="SET NULL"), nullable=True)
    ab_test_policy_version_id = Column(String(36), ForeignKey("image_production_policy_versions.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(30), nullable=False, default="active")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        UniqueConstraint("slug", name="uq_image_strategy_slug"),
        Index("idx_image_strategies_role_status", "destination_role", "status"),
        Index("idx_image_strategies_status_updated", "status", "updated_at"),
    )


class ImageProductionStrategyVersion(Base):
    __tablename__ = "image_production_strategy_versions"

    id = Column(String(36), primary_key=True, default=_uuid)
    strategy_id = Column(String(36), ForeignKey("image_production_strategies.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    snapshot_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    __table_args__ = (
        UniqueConstraint("strategy_id", "version", name="uq_image_strategy_version"),
        Index("idx_image_strategy_versions_strategy", "strategy_id"),
    )


class ImageSelectionPreview(Base):
    __tablename__ = "image_selection_previews"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    strategy_id = Column(String(36), ForeignKey("image_production_strategies.id", ondelete="SET NULL"), nullable=True)
    strategy_version = Column(Integer, nullable=True)
    mode = Column(String(40), nullable=False)
    destination_role = Column(String(80), nullable=True)
    model_id = Column(String(36), nullable=True)
    selected_model_id = Column(String(36), nullable=True)
    request_hash = Column(String(64), nullable=False)
    response_json = Column(JSON, nullable=False, default=dict)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    __table_args__ = (
        Index("idx_image_selection_previews_hash", "request_hash"),
        Index("idx_image_selection_previews_expires", "expires_at"),
        Index("idx_image_selection_previews_user_created", "user_id", "created_at"),
    )


class ImageCreationTask(Base):
    __tablename__ = "image_creation_tasks"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    idempotency_key = Column(String(160), nullable=True)
    request_hash = Column(String(64), nullable=True)
    mode = Column(String(40), nullable=False)
    output_mode = Column(String(20), nullable=False, default="single")
    capability_key = Column(String(80), nullable=False)
    status = Column(String(30), nullable=False, default="queued")
    series_id = Column(String(36), ForeignKey("series.id", ondelete="SET NULL"), nullable=True)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True)
    prompt = Column(Text, nullable=False)
    negative_prompt = Column(Text, nullable=True)
    source_type = Column(String(40), nullable=True)
    source = Column(String(40), nullable=True)
    source_url = Column(Text, nullable=True)
    source_asset_id = Column(String(36), nullable=True)
    reference_images_json = Column(JSON, nullable=True, default=list)
    destination_role = Column(String(60), nullable=True)
    destination_context_json = Column(JSON, nullable=True, default=dict)
    size = Column(String(30), nullable=True)
    count = Column(Integer, nullable=False, default=1)
    output_format = Column(String(20), nullable=True)
    response_format = Column(String(20), nullable=True)
    watermark = Column(Boolean, nullable=True)
    provider_options_json = Column(JSON, nullable=True, default=dict)
    estimated_cost_json = Column(JSON, nullable=True, default=dict)
    cost_status = Column(String(30), nullable=False, default="not_estimated")
    requires_cost_confirmation = Column(Boolean, nullable=False, default=False)
    storage_status = Column(String(30), nullable=False, default="pending")
    model_scene_key = Column(String(80), nullable=True)
    model_scene = Column(String(80), nullable=True)
    provider = Column(String(80), nullable=True)
    model_id = Column(String(120), nullable=True)
    provider_task_id = Column(String(120), nullable=True)
    external_task_id = Column(String(120), nullable=True)
    progress = Column(Float, nullable=False, default=0.0)
    target_count = Column(Integer, nullable=False, default=1)
    completed_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    review_policy = Column(String(40), nullable=True)
    selected_asset_id = Column(String(36), nullable=True)
    selected_asset_version = Column(Integer, nullable=True)
    strategy_id = Column(String(36), ForeignKey("image_production_strategies.id", ondelete="SET NULL"), nullable=True)
    strategy_version = Column(Integer, nullable=True)
    strategy_snapshot_json = Column(JSON, nullable=True, default=dict)
    selection_explanation_json = Column(JSON, nullable=True, default=dict)
    selection_preview_id = Column(String(36), ForeignKey("image_selection_previews.id", ondelete="SET NULL"), nullable=True)
    selection_preview_request_hash = Column(String(64), nullable=True)
    fallback_trace_json = Column(JSON, nullable=True, default=dict)
    queue_job_id = Column(String(36), nullable=True)
    capacity_lease_id = Column(String(80), nullable=True)
    ab_test_group_id = Column(String(36), nullable=True)
    model_trace_json = Column(JSON, nullable=True, default=dict)
    pixelle_payload_json = Column(JSON, nullable=True, default=dict)
    request_json = Column(JSON, nullable=True, default=dict)
    provider_response_json = Column(JSON, nullable=True, default=dict)
    pixelle_task_id = Column(String(120), nullable=True)
    partial_results_json = Column(JSON, nullable=True, default=list)
    usage_json = Column(JSON, nullable=True, default=dict)
    error_code = Column(String(80), nullable=True)
    error_message = Column(Text, nullable=True)
    repair_action = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_image_task_idempotency_key"),
        UniqueConstraint("pixelle_task_id", name="uq_image_task_pixelle_task_id"),
        Index("idx_image_tasks_user", "user_id"),
        Index("idx_image_tasks_status", "status"),
        Index("idx_image_tasks_status_created", "status", "created_at"),
        Index("idx_image_tasks_series_episode", "series_id", "episode_id"),
        Index("idx_image_tasks_model_capability", "model_scene_key", "capability_key"),
        Index("idx_image_tasks_created", "created_at"),
        Index("idx_image_tasks_strategy", "strategy_id", "strategy_version"),
        Index("idx_image_tasks_selection_preview", "selection_preview_id"),
    )


class ImageCreationAsset(Base):
    __tablename__ = "image_creation_assets"

    id = Column(String(36), primary_key=True, default=_uuid)
    task_id = Column(String(36), ForeignKey("image_creation_tasks.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    series_id = Column(String(36), ForeignKey("series.id", ondelete="SET NULL"), nullable=True)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True)
    asset_type = Column(String(30), nullable=False, default="image")
    asset_kind = Column(String(30), nullable=True)
    url = Column(Text, nullable=True)
    local_path = Column(Text, nullable=True)
    storage_path = Column(Text, nullable=True)
    thumbnail_url = Column(Text, nullable=True)
    mime_type = Column(String(80), nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    seed = Column(String(120), nullable=True)
    prompt = Column(Text, nullable=True)
    checksum = Column(String(120), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    status = Column(String(40), nullable=False, default="review_pending")
    version = Column(Integer, nullable=False, default=1)
    source_asset_id = Column(String(36), nullable=True)
    source_url = Column(Text, nullable=True)
    reference_images_json = Column(JSON, nullable=True, default=list)
    slot_key = Column(String(160), nullable=False, default="default")
    group_id = Column(String(80), nullable=True)
    group_index = Column(Integer, nullable=True)
    destination_role = Column(String(60), nullable=True)
    destination_context_json = Column(JSON, nullable=True, default=dict)
    downstream_usage_json = Column(JSON, nullable=True, default=list)
    provider_error_json = Column(JSON, nullable=True, default=dict)
    provider_task_id = Column(String(120), nullable=True)
    pixelle_task_id = Column(String(120), nullable=True)
    model_scene = Column(String(80), nullable=True)
    provider = Column(String(80), nullable=True)
    model_id = Column(String(120), nullable=True)
    variant_index = Column(Integer, nullable=True)
    prompt_hash = Column(String(64), nullable=True)
    is_latest = Column(Boolean, nullable=False, default=True)
    is_selected = Column(Boolean, nullable=False, default=False)
    audit_status = Column(String(30), nullable=True)
    ai_score = Column(Float, nullable=True)
    ai_report_json = Column(JSON, nullable=True, default=dict)
    manual_review_status = Column(String(30), nullable=True)
    metadata_json = Column(JSON, nullable=True, default=dict)
    storage_status = Column(String(30), nullable=False, default="persisted")
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        UniqueConstraint("task_id", "slot_key", "version", name="uq_image_asset_slot_version"),
        Index(
            "uq_image_asset_canonical_slot_version",
            "task_id",
            func.coalesce(group_id, slot_key, "default"),
            func.coalesce(group_index, -1),
            "version",
            unique=True,
        ),
        Index("idx_image_assets_task", "task_id"),
        Index("idx_image_assets_task_version", "task_id", "version"),
        Index("idx_image_assets_status", "status"),
        Index("idx_image_assets_audit_status", "audit_status"),
        Index("idx_image_assets_destination", "destination_role"),
        Index("idx_image_assets_series_episode", "series_id", "episode_id"),
        Index("idx_image_assets_group", "group_id", "group_index"),
        Index("idx_image_assets_source", "source_asset_id"),
        Index("idx_image_assets_latest", "is_latest"),
    )


class ImageProductionCostEvent(Base):
    __tablename__ = "image_production_cost_events"

    id = Column(String(36), primary_key=True, default=_uuid)
    event_key = Column(String(220), nullable=False)
    task_id = Column(String(36), ForeignKey("image_creation_tasks.id", ondelete="CASCADE"), nullable=False)
    asset_id = Column(String(36), ForeignKey("image_creation_assets.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String(30), nullable=False)
    stage = Column(String(40), nullable=False, default="image_generation")
    strategy_id = Column(String(36), nullable=True)
    strategy_version = Column(Integer, nullable=True)
    model_id = Column(String(120), nullable=True)
    provider = Column(String(80), nullable=True)
    provider_task_id = Column(String(120), nullable=True)
    estimated_cost = Column(Float, nullable=False, default=0.0)
    actual_cost = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), nullable=False, default="CNY")
    units_json = Column(JSON, nullable=True, default=dict)
    estimate_source = Column(String(40), nullable=False, default="policy")
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    __table_args__ = (
        UniqueConstraint("event_key", name="uq_image_cost_event_key"),
        Index("idx_image_cost_events_task", "task_id"),
        Index("idx_image_cost_events_event_type", "event_type"),
        Index("idx_image_cost_events_strategy", "strategy_id", "strategy_version"),
        Index("idx_image_cost_events_created", "created_at"),
    )


class ImageProductionAbGroup(Base):
    __tablename__ = "image_production_ab_groups"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    idempotency_key = Column(String(160), nullable=True)
    source_request_hash = Column(String(80), nullable=False)
    prompt_snapshot_json = Column(JSON, nullable=False, default=dict)
    cost_confirmation_json = Column(JSON, nullable=True, default=dict)
    winner_attempt_id = Column(String(36), nullable=True)
    decision_json = Column(JSON, nullable=True, default=dict)
    status = Column(String(30), nullable=False, default="running")
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_image_ab_group_idempotency_key"),
        Index("idx_image_ab_groups_status", "status"),
        Index("idx_image_ab_groups_created", "created_at"),
        Index("idx_image_ab_groups_winner", "winner_attempt_id"),
    )


class ImageProductionAbAttempt(Base):
    __tablename__ = "image_production_ab_attempts"

    id = Column(String(36), primary_key=True, default=_uuid)
    group_id = Column(String(36), ForeignKey("image_production_ab_groups.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(String(36), ForeignKey("image_creation_tasks.id", ondelete="SET NULL"), nullable=True)
    strategy_id = Column(String(36), nullable=False)
    strategy_version = Column(Integer, nullable=False)
    model_id = Column(String(120), nullable=True)
    status = Column(String(30), nullable=False, default="creating")
    metrics_snapshot_json = Column(JSON, nullable=True, default=dict)
    human_decision_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        UniqueConstraint("group_id", "strategy_id", "strategy_version", name="uq_image_ab_attempt_strategy"),
        Index("idx_image_ab_attempts_group", "group_id"),
        Index("idx_image_ab_attempts_task", "task_id"),
        Index("idx_image_ab_attempts_status", "status"),
    )


class ImageProductionMetric(Base):
    __tablename__ = "image_production_metrics"

    id = Column(String(36), primary_key=True, default=_uuid)
    strategy_id = Column(String(36), nullable=False)
    strategy_version = Column(Integer, nullable=False)
    model_id = Column(String(120), nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    failure_count = Column(Integer, nullable=False, default=0)
    ai_pass_count = Column(Integer, nullable=False, default=0)
    human_pass_count = Column(Integer, nullable=False, default=0)
    repaint_count = Column(Integer, nullable=False, default=0)
    average_latency_seconds = Column(Float, nullable=False, default=0.0)
    average_cost_amount = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), nullable=False, default="CNY")
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        Index(
            "uq_image_metric_strategy_version_model",
            "strategy_id",
            "strategy_version",
            func.coalesce(model_id, "__strategy__"),
            unique=True,
        ),
        Index("idx_image_metrics_strategy", "strategy_id", "strategy_version"),
        Index("idx_image_metrics_updated", "updated_at"),
    )


class ImageCreationReviewRecord(Base):
    __tablename__ = "image_creation_review_records"

    id = Column(String(36), primary_key=True, default=_uuid)
    asset_id = Column(String(36), ForeignKey("image_creation_assets.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(String(36), ForeignKey("image_creation_tasks.id", ondelete="CASCADE"), nullable=False)
    review_type = Column(String(20), nullable=False)
    reviewer_type = Column(String(20), nullable=True)
    status = Column(String(30), nullable=False)
    action = Column(String(40), nullable=True)
    score = Column(Float, nullable=True)
    criteria_json = Column(JSON, nullable=True, default=list)
    issues_json = Column(JSON, nullable=True, default=list)
    report_json = Column(JSON, nullable=True, default=dict)
    reviewer_user_id = Column(String(36), nullable=True)
    model_trace_json = Column(JSON, nullable=True, default=dict)
    comment = Column(Text, nullable=True)
    asset_version = Column(Integer, nullable=False, default=1)
    is_latest_asset_review = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    __table_args__ = (
        Index("idx_image_review_asset", "asset_id"),
        Index("idx_image_review_task", "task_id"),
        Index("idx_image_review_status", "status"),
        Index("idx_image_review_latest", "asset_id", "asset_version", "is_latest_asset_review"),
        Index(
            "uq_image_review_latest_asset_version",
            "asset_id",
            "asset_version",
            unique=True,
            sqlite_where=is_latest_asset_review.is_(True),
            postgresql_where=is_latest_asset_review.is_(True),
        ),
    )

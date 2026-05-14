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
    strategies = Column(JSON, nullable=False)  # list of {type, value, x_percent, y_percent, priority}
    version = Column(Integer, nullable=False, default=1)
    enabled = Column(Boolean, nullable=False, default=True)
    category = Column(String(50), nullable=True, default=None, index=True)
    purpose = Column(String(20), nullable=False, default="locate")  # locate | extract
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
    comments = Column(Integer, nullable=False, default=0)
    follows = Column(Integer, nullable=False, default=0)
    dms = Column(Integer, nullable=False, default=0)
    replies = Column(Integer, nullable=False, default=0)
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
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())


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

"""Content collection ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship


class ContentTemplate(Base):
    __tablename__ = "content_templates"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False, default="comment")
    body = Column(Text, nullable=False)
    variables = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class SensitiveWord(Base):
    __tablename__ = "sensitive_words"

    id = Column(String(36), primary_key=True, default=_uuid)
    word = Column(String(100), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())


class RepliedComment(Base):
    """Comment reply dedupe row."""
    __tablename__ = "replied_comments"

    content_hash = Column(String(64), primary_key=True)
    author = Column(String(200), nullable=False)
    text = Column(Text, nullable=False)
    replied_by_device = Column(String(36), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())


class DMSequence(Base):
    """DM sequence template."""
    __tablename__ = "dm_sequences"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    messages = Column(JSON, nullable=False)
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

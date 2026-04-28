"""SQLAlchemy ORM models — database persistence layer."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Integer, DateTime, Text, Boolean,
    JSON, ForeignKey, UniqueConstraint,
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
        "likes": 50, "comments": 20, "follows": 20, "dms": 10, "replies": 15,
    })
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    tasks = relationship("Task", back_populates="account")


class Device(Base):
    __tablename__ = "devices"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    ip = Column(String(50), nullable=True)
    status = Column(String(20), nullable=False, default="offline")  # online, offline, maintenance
    bound_account_id = Column(String(36), ForeignKey("accounts.id"), nullable=True)
    proxy_config = Column(JSON, nullable=True)  # {"type":"http","host":"...","port":8080,"username":"...","password":"..."}
    os_version = Column(String(50), nullable=True)
    app_version = Column(String(20), nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    tasks = relationship("Task", back_populates="device")


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
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    account = relationship("Account", back_populates="tasks")
    device = relationship("Device", back_populates="tasks")


class UISelector(Base):
    __tablename__ = "ui_selectors"

    id = Column(String(36), primary_key=True, default=_uuid)
    action_name = Column(String(100), nullable=False, index=True)
    platform_version = Column(String(50), nullable=False, default="default")
    strategies = Column(JSON, nullable=False)  # list of {type, value, x_percent, y_percent, priority}
    version = Column(Integer, nullable=False, default=1)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


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
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    account = relationship("Account")


class ContentTemplate(Base):
    __tablename__ = "content_templates"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False, default="comment")  # comment, dm, reply
    body = Column(Text, nullable=False)
    variables = Column(JSON, nullable=False, default=list)  # ["keyword", "username", "video_title"]
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class SensitiveWord(Base):
    __tablename__ = "sensitive_words"

    id = Column(String(36), primary_key=True, default=_uuid)
    word = Column(String(100), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

"""Account operations ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship


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

"""Account operations ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
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

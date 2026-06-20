"""Account operations ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Text
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

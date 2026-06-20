"""Reporting ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship


class DailyStats(Base):
    __tablename__ = "daily_stats"
    __table_args__ = (
        UniqueConstraint("account_id", "date", name="uq_daily_stats_account_date"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    account_id = Column(String(36), ForeignKey("accounts.id"), nullable=False, index=True)
    date = Column(String(10), nullable=False, index=True)
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


class StatsEvent(Base):
    """Idempotent stats event."""
    __tablename__ = "stats_events"
    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "device_id",
            "event_type",
            "target_id",
            "op_index",
            name="uq_stats_event_idempotent",
        ),
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

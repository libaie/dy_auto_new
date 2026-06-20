"""Video production ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text


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

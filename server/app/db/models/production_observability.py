"""Production observability ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, JSON, String


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

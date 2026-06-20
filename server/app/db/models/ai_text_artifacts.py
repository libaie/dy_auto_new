"""AI text artifact ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint


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

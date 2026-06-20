"""Script pipeline ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(String(36), primary_key=True, default=_uuid)
    series_id = Column(String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True)
    mode = Column(String(20), nullable=False, default="step_by_step")
    model_ids = Column(JSON, nullable=True, default=dict)
    layers_json = Column(JSON, nullable=True, default=dict)
    current_layer = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="pending")
    error_log = Column(Text, nullable=True)
    actual_cost_so_far = Column(Float, nullable=True, default=0.0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    __table_args__ = (Index("idx_pipeline_runs_series_id", "series_id"),)

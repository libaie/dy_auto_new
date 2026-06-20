"""Agency operations ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text

class AgencyExpertInvocation(Base):
    __tablename__ = "agency_expert_invocations"
    __table_args__ = (
        Index("idx_agency_invocations_series_created", "series_id", "created_at"),
        Index("idx_agency_invocations_series_run_stage", "series_id", "run_id", "stage"),
        Index("idx_agency_invocations_run_stage_created", "run_id", "stage", "created_at"),
        Index("idx_agency_invocations_pipeline_stage_created", "pipeline_run_id", "stage", "created_at"),
        Index("idx_agency_invocations_plan_episode_stage", "production_plan_id", "production_episode_id", "stage"),
        Index("idx_agency_invocations_expert_result_created", "expert_id", "result_status", "created_at"),
        Index("idx_agency_invocations_error_created", "error_code", "created_at"),
        Index("idx_agency_invocations_idempotency", "idempotency_key", unique=True),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    idempotency_key = Column(String(160), nullable=False)
    attempt = Column(Integer, nullable=False, default=1)
    retry_of_invocation_id = Column(
        String(36),
        ForeignKey("agency_expert_invocations.id", ondelete="SET NULL"),
        nullable=True,
    )
    series_id = Column(String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True)
    run_id = Column(String(36), ForeignKey("video_production_runs.id", ondelete="SET NULL"), nullable=True)
    production_plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="SET NULL"), nullable=True)
    production_episode_id = Column(String(36), ForeignKey("production_episodes.id", ondelete="SET NULL"), nullable=True)
    production_segment_id = Column(String(36), ForeignKey("production_segments.id", ondelete="SET NULL"), nullable=True)
    pipeline_run_id = Column(String(36), ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True)
    stage = Column(String(40), nullable=False)
    expert_id = Column(String(80), nullable=False)
    role = Column(String(20), nullable=False)
    execution_status = Column(String(20), nullable=False, default="queued")
    result_status = Column(String(20), nullable=False, default="pending")
    input_summary_json = Column(JSON, nullable=True, default=dict)
    output_summary_json = Column(JSON, nullable=True, default=dict)
    evidence_json = Column(JSON, nullable=True, default=list)
    source_repo = Column(String(120), nullable=False, default="jnMetaCode/agency-agents-zh")
    source_commit = Column(String(80), nullable=False, default="")
    source_path = Column(String(240), nullable=False, default="")
    source_sha256 = Column(String(64), nullable=False, default="")
    model_config_snapshot_json = Column(JSON, nullable=True, default=dict)
    token_usage_json = Column(JSON, nullable=True, default=dict)
    duration_ms = Column(Integer, nullable=False, default=0)
    error_code = Column(String(80), nullable=True)
    error_message = Column(Text, nullable=True)
    repair_action = Column(Text, nullable=True)
    repair_route = Column(Text, nullable=True)
    repair_target_type = Column(String(80), nullable=True)
    repair_target_ids_json = Column(JSON, nullable=True, default=list)
    retry_scope = Column(String(80), nullable=True)
    created_at = Column(DateTime, nullable=False, default=bj_now)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)


class AgencyCreativePatch(Base):
    __tablename__ = "agency_creative_patches"
    __table_args__ = (
        Index("idx_agency_creative_patches_series_created", "series_id", "created_at"),
        Index("idx_agency_creative_patches_run_status", "run_id", "status"),
        Index("idx_agency_creative_patches_invocation", "source_invocation_id"),
        Index("idx_agency_creative_patches_target_status", "target_type", "target_id", "status"),
        Index("idx_agency_creative_patches_plan_stage_status", "production_plan_id", "stage", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    series_id = Column(String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True)
    run_id = Column(String(36), ForeignKey("video_production_runs.id", ondelete="SET NULL"), nullable=True)
    production_plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="SET NULL"), nullable=True)
    production_episode_id = Column(String(36), ForeignKey("production_episodes.id", ondelete="SET NULL"), nullable=True)
    production_segment_id = Column(String(36), ForeignKey("production_segments.id", ondelete="SET NULL"), nullable=True)
    source_invocation_id = Column(String(36), ForeignKey("agency_expert_invocations.id", ondelete="SET NULL"), nullable=True)
    stage = Column(String(40), nullable=False)
    expert_id = Column(String(80), nullable=False, default="")
    patch_type = Column(String(40), nullable=False)
    target_type = Column(String(40), nullable=False)
    target_id = Column(String(100), nullable=False)
    title = Column(String(200), nullable=False, default="")
    reason = Column(Text, nullable=False, default="")
    before_json = Column(JSON, nullable=False, default=dict)
    after_json = Column(JSON, nullable=False, default=dict)
    status = Column(String(30), nullable=False, default="proposed")
    priority = Column(String(20), nullable=False, default="normal")
    reviewer_user_id = Column(String(36), nullable=True)
    applied_at = Column(DateTime, nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

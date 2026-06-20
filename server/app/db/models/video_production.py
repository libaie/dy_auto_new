"""Video production ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint


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


class ProductionPlanVersion(Base):
    __tablename__ = "production_plan_versions"
    __table_args__ = (
        UniqueConstraint("plan_id", "version", name="uq_production_plan_version"),
        Index("idx_production_plan_versions_plan_id", "plan_id"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    style_lock_json = Column(JSON, nullable=True, default=dict)
    model_config_snapshot_json = Column(JSON, nullable=True, default=dict)
    prompt_policy_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())


class ProductionEpisode(Base):
    __tablename__ = "production_episodes"
    __table_args__ = (
        UniqueConstraint("plan_id", "episode_id", name="uq_production_episode_plan_episode"),
        Index("idx_production_episodes_plan_id", "plan_id"),
        Index("idx_production_episodes_episode_id", "episode_id"),
        Index("idx_production_episodes_status", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False)
    order_index = Column(Integer, nullable=False, default=0)
    status = Column(String(30), nullable=False, default="planned")
    target_duration_seconds = Column(Integer, nullable=False, default=0)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class ProductionScene(Base):
    __tablename__ = "production_scenes"
    __table_args__ = (
        UniqueConstraint("episode_plan_id", "scene_id", name="uq_production_scene_episode_scene"),
        Index("idx_production_scenes_episode_plan_id", "episode_plan_id"),
        Index("idx_production_scenes_status", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    episode_plan_id = Column(String(36), ForeignKey("production_episodes.id", ondelete="CASCADE"), nullable=False)
    scene_id = Column(String(100), nullable=False)
    order_index = Column(Integer, nullable=False, default=0)
    status = Column(String(30), nullable=False, default="planned")
    location_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class ProductionShot(Base):
    __tablename__ = "production_shots"
    __table_args__ = (
        UniqueConstraint("scene_plan_id", "shot_id", name="uq_production_shot_scene_shot"),
        Index("idx_production_shots_scene_plan_id", "scene_plan_id"),
        Index("idx_production_shots_status", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    scene_plan_id = Column(String(36), ForeignKey("production_scenes.id", ondelete="CASCADE"), nullable=False)
    shot_id = Column(String(100), nullable=False)
    order_index = Column(Integer, nullable=False, default=0)
    status = Column(String(30), nullable=False, default="planned")
    character_ids = Column(JSON, nullable=False, default=list)
    action = Column(Text, nullable=False, default="")
    emotion = Column(String(50), nullable=True)
    shot_type = Column(String(50), nullable=False, default="medium")
    duration_seconds = Column(Float, nullable=False, default=5.0)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class ProductionSegment(Base):
    __tablename__ = "production_segments"
    __table_args__ = (
        UniqueConstraint("shot_plan_id", "segment_id", "version", name="uq_production_segment_version"),
        Index("idx_production_segments_shot_plan_id", "shot_plan_id"),
        Index("idx_production_segments_previous_segment_id", "previous_segment_id"),
        Index("idx_production_segments_status", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    shot_plan_id = Column(String(36), ForeignKey("production_shots.id", ondelete="CASCADE"), nullable=False)
    previous_segment_id = Column(String(36), ForeignKey("production_segments.id", ondelete="SET NULL"), nullable=True)
    segment_id = Column(String(100), nullable=False)
    order_index = Column(Integer, nullable=False, default=0)
    status = Column(String(30), nullable=False, default="planned")
    duration_seconds = Column(Float, nullable=False, default=5.0)
    continuity_mode = Column(String(50), nullable=False, default="narrative_cut")
    version = Column(Integer, nullable=False, default=1)
    previous_end_frame_url = Column(Text, nullable=True)
    expected_end_state = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    image_prompt = Column(Text, nullable=False, default="")
    video_prompt = Column(Text, nullable=False, default="")
    narration = Column(Text, nullable=True)
    reference_roles_json = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class ProductionJob(Base):
    __tablename__ = "production_jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_production_jobs_idempotency_key"),
        Index("idx_production_jobs_plan_id", "plan_id"),
        Index("idx_production_jobs_target", "target_type", "target_id"),
        Index("idx_production_jobs_status", "status"),
        Index("idx_production_jobs_plan_status_resume", "plan_id", "status", "resume_status"),
        Index("idx_production_jobs_plan_stage_status", "plan_id", "stage", "status"),
        Index("idx_production_jobs_stage_created_at", "stage", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False)
    target_type = Column(String(30), nullable=False)
    target_id = Column(String(36), nullable=False)
    stage = Column(String(80), nullable=False)
    status = Column(String(30), nullable=False, default="queued")
    provider_task_id = Column(String(120), nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    retry_after = Column(DateTime, nullable=True)
    lease_id = Column(String(80), nullable=True)
    leased_until = Column(DateTime, nullable=True)
    priority = Column(Integer, nullable=False, default=100)
    scheduled_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_code = Column(String(80), nullable=True)
    error_message = Column(Text, nullable=True)
    retryable = Column(Boolean, nullable=False, default=True)
    idempotency_key = Column(String(200), nullable=False)
    resume_status = Column(String(30), nullable=True)
    blocked_reason = Column(String(120), nullable=True)
    paused_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class VideoProductionRun(Base):
    """One staged automated production attempt for an episode."""
    __tablename__ = "video_production_runs"

    id = Column(String(36), primary_key=True, default=_uuid)
    series_id = Column(String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(40), nullable=False, default="draft")
    current_stage = Column(String(40), nullable=False, default="draft")
    run_type = Column(String(40), nullable=False, default="legacy_episode_run")
    pixelle_stage_task_id = Column(String(100), nullable=True)
    production_plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="SET NULL"), nullable=True)
    production_episode_id = Column(String(36), ForeignKey("production_episodes.id", ondelete="SET NULL"), nullable=True)
    production_link_status = Column(String(30), nullable=False, default="legacy_unlinked")
    storyboard_json = Column(JSON, nullable=True, default=dict)
    model_trace_json = Column(JSON, nullable=True, default=dict)
    edit_manifest_json = Column(JSON, nullable=True, default=dict)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        Index("idx_video_production_runs_series_episode", "series_id", "episode_id"),
        Index("idx_video_production_runs_status", "status"),
        Index("idx_video_production_runs_type", "run_type"),
        Index("idx_video_production_runs_production_links", "production_plan_id", "production_episode_id"),
        Index("idx_video_production_runs_link_status", "production_link_status"),
    )


class VideoProductionAsset(Base):
    """Intermediate or final asset created by staged production."""
    __tablename__ = "video_production_assets"

    id = Column(String(36), primary_key=True, default=_uuid)
    run_id = Column(String(36), ForeignKey("video_production_runs.id", ondelete="CASCADE"), nullable=False)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False)
    frame_id = Column(String(100), nullable=False)
    asset_type = Column(String(30), nullable=False)
    stage = Column(String(40), nullable=False)
    url = Column(Text, nullable=True)
    local_path = Column(Text, nullable=True)
    thumbnail_url = Column(Text, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    metadata_json = Column(JSON, nullable=True, default=dict)
    status = Column(String(40), nullable=False, default="generated")
    pixelle_task_id = Column(String(100), nullable=True)
    production_segment_id = Column(String(36), ForeignKey("production_segments.id", ondelete="SET NULL"), nullable=True)
    production_shot_id = Column(String(36), ForeignKey("production_shots.id", ondelete="SET NULL"), nullable=True)
    target_type = Column(String(30), nullable=True)
    target_id = Column(String(36), nullable=True)
    provider_task_id = Column(String(120), nullable=True)
    provider_stage_task_id = Column(String(36), ForeignKey("provider_stage_tasks.id", ondelete="SET NULL"), nullable=True)
    prompt_hash = Column(String(64), nullable=True)
    storage_path = Column(Text, nullable=True)
    source_url = Column(Text, nullable=True)
    storage_error_json = Column(JSON, nullable=True, default=dict)
    provider_response_summary_json = Column(JSON, nullable=True, default=dict)
    is_latest = Column(Boolean, nullable=False, default=True)
    source_version = Column(Integer, nullable=False, default=1)
    copy_status = Column(String(30), nullable=False, default="registered")
    checksum = Column(String(120), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        Index("idx_video_assets_run_stage", "run_id", "stage"),
        Index("idx_video_assets_run_frame", "run_id", "frame_id"),
        Index("idx_video_assets_status", "status"),
        Index("idx_video_assets_production_segment", "production_segment_id"),
        Index("idx_video_assets_production_shot", "production_shot_id"),
        Index("idx_video_assets_target", "target_type", "target_id"),
        Index("idx_video_assets_provider_stage_task", "provider_stage_task_id"),
        Index("idx_video_assets_segment_latest", "production_segment_id", "asset_type", "is_latest"),
        UniqueConstraint("run_id", "frame_id", "asset_type", "version", name="uq_video_asset_version"),
    )


class ProviderStageTask(Base):
    __tablename__ = "provider_stage_tasks"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_provider_stage_tasks_idempotency"),
        Index("idx_provider_stage_tasks_run_stage_status", "run_id", "stage", "status"),
        Index("idx_provider_stage_tasks_plan_stage_status", "plan_id", "stage", "status"),
        Index("idx_provider_stage_tasks_target", "target_type", "target_id"),
        Index("idx_provider_stage_tasks_provider_task_id", "provider_task_id"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    run_id = Column(String(36), ForeignKey("video_production_runs.id", ondelete="CASCADE"), nullable=False)
    plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(String(36), ForeignKey("production_jobs.id", ondelete="SET NULL"), nullable=True)
    target_type = Column(String(30), nullable=False)
    target_id = Column(String(36), nullable=False)
    stage = Column(String(40), nullable=False)
    provider = Column(String(80), nullable=False)
    model_name = Column(String(120), nullable=False)
    request_hash = Column(String(64), nullable=False)
    idempotency_key = Column(String(220), nullable=False)
    status = Column(String(40), nullable=False, default="reserved")
    provider_task_id = Column(String(160), nullable=True)
    external_task_id = Column(String(160), nullable=True)
    error_code = Column(String(80), nullable=True)
    error_message = Column(Text, nullable=True)
    response_summary_json = Column(JSON, nullable=True, default=dict)
    submitted_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class ProviderCostReservation(Base):
    __tablename__ = "provider_cost_reservations"
    __table_args__ = (
        UniqueConstraint(
            "provider_stage_task_id",
            name="uq_provider_cost_reservation_stage_task",
        ),
        Index("idx_provider_cost_reservations_plan_status", "plan_id", "status"),
        Index("idx_provider_cost_reservations_expires", "expires_at", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False)
    provider_stage_task_id = Column(
        String(36),
        ForeignKey("provider_stage_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    status = Column(String(40), nullable=False, default="active_unsubmitted")
    estimated_cost = Column(Float, nullable=False, default=0.0)
    reserved_cost = Column(Float, nullable=False, default=0.0)
    actual_cost = Column(Float, nullable=True)
    currency = Column(String(10), nullable=False, default="CNY")
    units_json = Column(JSON, nullable=True, default=dict)
    expires_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    settled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class ProductionCostEvent(Base):
    __tablename__ = "production_cost_events"
    __table_args__ = (
        Index("idx_production_cost_events_plan_id", "plan_id"),
        Index("idx_production_cost_events_episode_plan_id", "episode_plan_id"),
        Index("idx_production_cost_events_segment_id", "segment_id"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False)
    episode_plan_id = Column(String(36), ForeignKey("production_episodes.id", ondelete="SET NULL"), nullable=True)
    segment_id = Column(String(36), ForeignKey("production_segments.id", ondelete="SET NULL"), nullable=True)
    stage = Column(String(40), nullable=False)
    model_config_id = Column(String(36), nullable=True)
    config_version = Column(Integer, nullable=False, default=1)
    provider_task_id = Column(String(120), nullable=True)
    provider = Column(String(50), nullable=False, default="")
    model_name = Column(String(100), nullable=False, default="")
    estimated_cost = Column(Float, nullable=False, default=0.0)
    actual_cost = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), nullable=False, default="CNY")
    units_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())


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

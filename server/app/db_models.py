"""SQLAlchemy ORM models — database persistence layer."""
from datetime import datetime, timezone

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text, Boolean,
    JSON, ForeignKey, UniqueConstraint, Index,
    func,
)

from app.db.models.ai_text_artifacts import AITextArtifact, AITextArtifactConsumer
from app.db.models.ai_video_series import Episode, Series, series_characters, series_scenes
from app.db.models.account_operations import (
    Account,
    AccountGroup,
    AccountGroupMember,
    ChainInstance,
    ChainTemplate,
    Channel,
    ChannelItem,
)
from app.db.models.device_operations import Device, DevicePairRequest
from app.db.models.content_collection import (
    CollectedComment,
    CollectedUser,
    ContentTemplate,
    Conversation,
    DMSequence,
    RepliedComment,
    SensitiveWord,
)
from app.db.models.creative_library import (
    Character,
    CharacterAnchor,
    ReferenceCategory,
    ReferenceData,
    Scene,
    SceneAnchor,
)
from app.db.models.identity_access import User
from app.db.models.image_production import (
    ImageSelectionPreview,
    ImageProductionCostEvent,
    ImageProductionMetric,
    ImageProductionPolicyVersion,
    ImageProductionStrategy,
    ImageProductionStrategyVersion,
)
from app.db.models.model_configuration import AIModel
from app.db.models.prompt_management import PromptTemplate
from app.db.models.production_observability import ProductionAuditEvent
from app.db.models.quality_audit import AuditReport
from app.db.models.reporting import DailyStats, StatsEvent
from app.db.models.script_pipeline import (
    EpisodeScript,
    PipelineRun,
    ScriptDramaticBeat,
    ScriptSceneOutline,
    ScriptVisualShot,
)
from app.db.models.selector_management import UISelector
from app.db.models.system_configuration import SystemSetting
from app.db.models.task_operations import Task
from app.db.models.video_library import GeneratedVideo
from app.db.models.video_production import (
    ProviderCostReservation,
    ProviderStageTask,
    ProductionCostEvent,
    ProductionEpisode,
    ProductionJob,
    ProductionPlan,
    ProductionPlanVersion,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    VideoCollection,
    VideoProductionAsset,
    VideoProductionRun,
    VideoReviewRecord,
)

# ==== 多模型系列生成系统 ====


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


class ImageCreationTask(Base):
    __tablename__ = "image_creation_tasks"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    idempotency_key = Column(String(160), nullable=True)
    request_hash = Column(String(64), nullable=True)
    mode = Column(String(40), nullable=False)
    output_mode = Column(String(20), nullable=False, default="single")
    capability_key = Column(String(80), nullable=False)
    status = Column(String(30), nullable=False, default="queued")
    series_id = Column(String(36), ForeignKey("series.id", ondelete="SET NULL"), nullable=True)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True)
    prompt = Column(Text, nullable=False)
    negative_prompt = Column(Text, nullable=True)
    source_type = Column(String(40), nullable=True)
    source = Column(String(40), nullable=True)
    source_url = Column(Text, nullable=True)
    source_asset_id = Column(String(36), nullable=True)
    reference_images_json = Column(JSON, nullable=True, default=list)
    destination_role = Column(String(60), nullable=True)
    destination_context_json = Column(JSON, nullable=True, default=dict)
    size = Column(String(30), nullable=True)
    count = Column(Integer, nullable=False, default=1)
    output_format = Column(String(20), nullable=True)
    response_format = Column(String(20), nullable=True)
    watermark = Column(Boolean, nullable=True)
    provider_options_json = Column(JSON, nullable=True, default=dict)
    estimated_cost_json = Column(JSON, nullable=True, default=dict)
    cost_status = Column(String(30), nullable=False, default="not_estimated")
    requires_cost_confirmation = Column(Boolean, nullable=False, default=False)
    storage_status = Column(String(30), nullable=False, default="pending")
    model_scene_key = Column(String(80), nullable=True)
    model_scene = Column(String(80), nullable=True)
    provider = Column(String(80), nullable=True)
    model_id = Column(String(120), nullable=True)
    provider_task_id = Column(String(120), nullable=True)
    external_task_id = Column(String(120), nullable=True)
    progress = Column(Float, nullable=False, default=0.0)
    target_count = Column(Integer, nullable=False, default=1)
    completed_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    review_policy = Column(String(40), nullable=True)
    selected_asset_id = Column(String(36), nullable=True)
    selected_asset_version = Column(Integer, nullable=True)
    strategy_id = Column(String(36), ForeignKey("image_production_strategies.id", ondelete="SET NULL"), nullable=True)
    strategy_version = Column(Integer, nullable=True)
    strategy_snapshot_json = Column(JSON, nullable=True, default=dict)
    selection_explanation_json = Column(JSON, nullable=True, default=dict)
    selection_preview_id = Column(String(36), ForeignKey("image_selection_previews.id", ondelete="SET NULL"), nullable=True)
    selection_preview_request_hash = Column(String(64), nullable=True)
    fallback_trace_json = Column(JSON, nullable=True, default=dict)
    queue_job_id = Column(String(36), nullable=True)
    capacity_lease_id = Column(String(80), nullable=True)
    ab_test_group_id = Column(String(36), nullable=True)
    model_trace_json = Column(JSON, nullable=True, default=dict)
    pixelle_payload_json = Column(JSON, nullable=True, default=dict)
    request_json = Column(JSON, nullable=True, default=dict)
    provider_response_json = Column(JSON, nullable=True, default=dict)
    pixelle_task_id = Column(String(120), nullable=True)
    partial_results_json = Column(JSON, nullable=True, default=list)
    usage_json = Column(JSON, nullable=True, default=dict)
    error_code = Column(String(80), nullable=True)
    error_message = Column(Text, nullable=True)
    repair_action = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_image_task_idempotency_key"),
        UniqueConstraint("pixelle_task_id", name="uq_image_task_pixelle_task_id"),
        Index("idx_image_tasks_user", "user_id"),
        Index("idx_image_tasks_status", "status"),
        Index("idx_image_tasks_status_created", "status", "created_at"),
        Index("idx_image_tasks_series_episode", "series_id", "episode_id"),
        Index("idx_image_tasks_model_capability", "model_scene_key", "capability_key"),
        Index("idx_image_tasks_created", "created_at"),
        Index("idx_image_tasks_strategy", "strategy_id", "strategy_version"),
        Index("idx_image_tasks_selection_preview", "selection_preview_id"),
    )


class ImageCreationAsset(Base):
    __tablename__ = "image_creation_assets"

    id = Column(String(36), primary_key=True, default=_uuid)
    task_id = Column(String(36), ForeignKey("image_creation_tasks.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    series_id = Column(String(36), ForeignKey("series.id", ondelete="SET NULL"), nullable=True)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True)
    asset_type = Column(String(30), nullable=False, default="image")
    asset_kind = Column(String(30), nullable=True)
    url = Column(Text, nullable=True)
    local_path = Column(Text, nullable=True)
    storage_path = Column(Text, nullable=True)
    thumbnail_url = Column(Text, nullable=True)
    mime_type = Column(String(80), nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    seed = Column(String(120), nullable=True)
    prompt = Column(Text, nullable=True)
    checksum = Column(String(120), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    status = Column(String(40), nullable=False, default="review_pending")
    version = Column(Integer, nullable=False, default=1)
    source_asset_id = Column(String(36), nullable=True)
    source_url = Column(Text, nullable=True)
    reference_images_json = Column(JSON, nullable=True, default=list)
    slot_key = Column(String(160), nullable=False, default="default")
    group_id = Column(String(80), nullable=True)
    group_index = Column(Integer, nullable=True)
    destination_role = Column(String(60), nullable=True)
    destination_context_json = Column(JSON, nullable=True, default=dict)
    downstream_usage_json = Column(JSON, nullable=True, default=list)
    provider_error_json = Column(JSON, nullable=True, default=dict)
    provider_task_id = Column(String(120), nullable=True)
    pixelle_task_id = Column(String(120), nullable=True)
    model_scene = Column(String(80), nullable=True)
    provider = Column(String(80), nullable=True)
    model_id = Column(String(120), nullable=True)
    variant_index = Column(Integer, nullable=True)
    prompt_hash = Column(String(64), nullable=True)
    is_latest = Column(Boolean, nullable=False, default=True)
    is_selected = Column(Boolean, nullable=False, default=False)
    audit_status = Column(String(30), nullable=True)
    ai_score = Column(Float, nullable=True)
    ai_report_json = Column(JSON, nullable=True, default=dict)
    manual_review_status = Column(String(30), nullable=True)
    metadata_json = Column(JSON, nullable=True, default=dict)
    storage_status = Column(String(30), nullable=False, default="persisted")
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        UniqueConstraint("task_id", "slot_key", "version", name="uq_image_asset_slot_version"),
        Index(
            "uq_image_asset_canonical_slot_version",
            "task_id",
            func.coalesce(group_id, slot_key, "default"),
            func.coalesce(group_index, -1),
            "version",
            unique=True,
        ),
        Index("idx_image_assets_task", "task_id"),
        Index("idx_image_assets_task_version", "task_id", "version"),
        Index("idx_image_assets_status", "status"),
        Index("idx_image_assets_audit_status", "audit_status"),
        Index("idx_image_assets_destination", "destination_role"),
        Index("idx_image_assets_series_episode", "series_id", "episode_id"),
        Index("idx_image_assets_group", "group_id", "group_index"),
        Index("idx_image_assets_source", "source_asset_id"),
        Index("idx_image_assets_latest", "is_latest"),
    )


class ImageProductionAbGroup(Base):
    __tablename__ = "image_production_ab_groups"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    idempotency_key = Column(String(160), nullable=True)
    source_request_hash = Column(String(80), nullable=False)
    prompt_snapshot_json = Column(JSON, nullable=False, default=dict)
    cost_confirmation_json = Column(JSON, nullable=True, default=dict)
    winner_attempt_id = Column(String(36), nullable=True)
    decision_json = Column(JSON, nullable=True, default=dict)
    status = Column(String(30), nullable=False, default="running")
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_image_ab_group_idempotency_key"),
        Index("idx_image_ab_groups_status", "status"),
        Index("idx_image_ab_groups_created", "created_at"),
        Index("idx_image_ab_groups_winner", "winner_attempt_id"),
    )


class ImageProductionAbAttempt(Base):
    __tablename__ = "image_production_ab_attempts"

    id = Column(String(36), primary_key=True, default=_uuid)
    group_id = Column(String(36), ForeignKey("image_production_ab_groups.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(String(36), ForeignKey("image_creation_tasks.id", ondelete="SET NULL"), nullable=True)
    strategy_id = Column(String(36), nullable=False)
    strategy_version = Column(Integer, nullable=False)
    model_id = Column(String(120), nullable=True)
    status = Column(String(30), nullable=False, default="creating")
    metrics_snapshot_json = Column(JSON, nullable=True, default=dict)
    human_decision_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        UniqueConstraint("group_id", "strategy_id", "strategy_version", name="uq_image_ab_attempt_strategy"),
        Index("idx_image_ab_attempts_group", "group_id"),
        Index("idx_image_ab_attempts_task", "task_id"),
        Index("idx_image_ab_attempts_status", "status"),
    )


class ImageCreationReviewRecord(Base):
    __tablename__ = "image_creation_review_records"

    id = Column(String(36), primary_key=True, default=_uuid)
    asset_id = Column(String(36), ForeignKey("image_creation_assets.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(String(36), ForeignKey("image_creation_tasks.id", ondelete="CASCADE"), nullable=False)
    review_type = Column(String(20), nullable=False)
    reviewer_type = Column(String(20), nullable=True)
    status = Column(String(30), nullable=False)
    action = Column(String(40), nullable=True)
    score = Column(Float, nullable=True)
    criteria_json = Column(JSON, nullable=True, default=list)
    issues_json = Column(JSON, nullable=True, default=list)
    report_json = Column(JSON, nullable=True, default=dict)
    reviewer_user_id = Column(String(36), nullable=True)
    model_trace_json = Column(JSON, nullable=True, default=dict)
    comment = Column(Text, nullable=True)
    asset_version = Column(Integer, nullable=False, default=1)
    is_latest_asset_review = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    __table_args__ = (
        Index("idx_image_review_asset", "asset_id"),
        Index("idx_image_review_task", "task_id"),
        Index("idx_image_review_status", "status"),
        Index("idx_image_review_latest", "asset_id", "asset_version", "is_latest_asset_review"),
        Index(
            "uq_image_review_latest_asset_version",
            "asset_id",
            "asset_version",
            unique=True,
            sqlite_where=is_latest_asset_review.is_(True),
            postgresql_where=is_latest_asset_review.is_(True),
        ),
    )

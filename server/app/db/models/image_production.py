"""Image production ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func


class ImageProductionPolicyVersion(Base):
    __tablename__ = "image_production_policy_versions"

    id = Column(String(36), primary_key=True, default=_uuid)
    policy_type = Column(String(30), nullable=False)
    name = Column(String(120), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    snapshot_json = Column(JSON, nullable=False, default=dict)
    status = Column(String(30), nullable=False, default="active")
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        UniqueConstraint("policy_type", "name", "version", name="uq_image_policy_version"),
        Index("idx_image_policy_versions_type_status", "policy_type", "status"),
    )


class ImageProductionStrategy(Base):
    __tablename__ = "image_production_strategies"

    id = Column(String(36), primary_key=True, default=_uuid)
    slug = Column(String(120), nullable=False)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    destination_role = Column(String(80), nullable=False)
    supported_modes_json = Column(JSON, nullable=False, default=list)
    default_model_id = Column(String(36), ForeignKey("ai_models.id", ondelete="SET NULL"), nullable=True)
    fallback_model_ids_json = Column(JSON, nullable=False, default=list)
    common_parameters_json = Column(JSON, nullable=False, default=dict)
    provider_options_json = Column(JSON, nullable=False, default=dict)
    review_policy_version_id = Column(String(36), ForeignKey("image_production_policy_versions.id", ondelete="SET NULL"), nullable=True)
    cost_policy_version_id = Column(String(36), ForeignKey("image_production_policy_versions.id", ondelete="SET NULL"), nullable=True)
    capacity_policy_version_id = Column(String(36), ForeignKey("image_production_policy_versions.id", ondelete="SET NULL"), nullable=True)
    ab_test_policy_version_id = Column(String(36), ForeignKey("image_production_policy_versions.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(30), nullable=False, default="active")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        UniqueConstraint("slug", name="uq_image_strategy_slug"),
        Index("idx_image_strategies_role_status", "destination_role", "status"),
        Index("idx_image_strategies_status_updated", "status", "updated_at"),
    )


class ImageProductionStrategyVersion(Base):
    __tablename__ = "image_production_strategy_versions"

    id = Column(String(36), primary_key=True, default=_uuid)
    strategy_id = Column(String(36), ForeignKey("image_production_strategies.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    snapshot_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    __table_args__ = (
        UniqueConstraint("strategy_id", "version", name="uq_image_strategy_version"),
        Index("idx_image_strategy_versions_strategy", "strategy_id"),
    )


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


class ImageSelectionPreview(Base):
    __tablename__ = "image_selection_previews"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    strategy_id = Column(String(36), ForeignKey("image_production_strategies.id", ondelete="SET NULL"), nullable=True)
    strategy_version = Column(Integer, nullable=True)
    mode = Column(String(40), nullable=False)
    destination_role = Column(String(80), nullable=True)
    model_id = Column(String(36), nullable=True)
    selected_model_id = Column(String(36), nullable=True)
    request_hash = Column(String(64), nullable=False)
    response_json = Column(JSON, nullable=False, default=dict)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    __table_args__ = (
        Index("idx_image_selection_previews_hash", "request_hash"),
        Index("idx_image_selection_previews_expires", "expires_at"),
        Index("idx_image_selection_previews_user_created", "user_id", "created_at"),
    )


class ImageProductionCostEvent(Base):
    __tablename__ = "image_production_cost_events"

    id = Column(String(36), primary_key=True, default=_uuid)
    event_key = Column(String(220), nullable=False)
    task_id = Column(String(36), ForeignKey("image_creation_tasks.id", ondelete="CASCADE"), nullable=False)
    asset_id = Column(String(36), ForeignKey("image_creation_assets.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String(30), nullable=False)
    stage = Column(String(40), nullable=False, default="image_generation")
    strategy_id = Column(String(36), nullable=True)
    strategy_version = Column(Integer, nullable=True)
    model_id = Column(String(120), nullable=True)
    provider = Column(String(80), nullable=True)
    provider_task_id = Column(String(120), nullable=True)
    estimated_cost = Column(Float, nullable=False, default=0.0)
    actual_cost = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), nullable=False, default="CNY")
    units_json = Column(JSON, nullable=True, default=dict)
    estimate_source = Column(String(40), nullable=False, default="policy")
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    __table_args__ = (
        UniqueConstraint("event_key", name="uq_image_cost_event_key"),
        Index("idx_image_cost_events_task", "task_id"),
        Index("idx_image_cost_events_event_type", "event_type"),
        Index("idx_image_cost_events_strategy", "strategy_id", "strategy_version"),
        Index("idx_image_cost_events_created", "created_at"),
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


class ImageProductionMetric(Base):
    __tablename__ = "image_production_metrics"

    id = Column(String(36), primary_key=True, default=_uuid)
    strategy_id = Column(String(36), nullable=False)
    strategy_version = Column(Integer, nullable=False)
    model_id = Column(String(120), nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    failure_count = Column(Integer, nullable=False, default=0)
    ai_pass_count = Column(Integer, nullable=False, default=0)
    human_pass_count = Column(Integer, nullable=False, default=0)
    repaint_count = Column(Integer, nullable=False, default=0)
    average_latency_seconds = Column(Float, nullable=False, default=0.0)
    average_cost_amount = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), nullable=False, default="CNY")
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        Index(
            "uq_image_metric_strategy_version_model",
            "strategy_id",
            "strategy_version",
            func.coalesce(model_id, "__strategy__"),
            unique=True,
        ),
        Index("idx_image_metrics_strategy", "strategy_id", "strategy_version"),
        Index("idx_image_metrics_updated", "updated_at"),
    )

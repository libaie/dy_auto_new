"""SQLAlchemy ORM models — database persistence layer."""
from datetime import datetime, timezone

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text, Boolean,
    JSON, ForeignKey, UniqueConstraint, Index, Table,
    func,
)
from sqlalchemy.orm import relationship

from app.db.models.ai_text_artifacts import AITextArtifact, AITextArtifactConsumer
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
from app.db.models.video_library import GeneratedVideo
from app.db.models.video_production import VideoCollection


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


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=_uuid)
    type = Column(String(30), nullable=False)  # nurture, search_comment, search_like, search_dm, reply_comment
    account_id = Column(String(36), ForeignKey("accounts.id"), nullable=False)
    device_id = Column(String(36), ForeignKey("devices.id"), nullable=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    params = Column(JSON, nullable=False, default=dict)
    status = Column(String(20), nullable=False, default="pending")  # pending, running, completed, failed, cancelled
    result = Column(JSON, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    scheduled_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    chain_instance_id = Column(String(36), ForeignKey("chain_instances.id"), nullable=True)
    step_order = Column(Integer, nullable=True)
    lease_id = Column(String(36), nullable=True, default=None)

    account = relationship("Account", back_populates="tasks")
    device = relationship("Device", back_populates="tasks")
    chain_instance = relationship("ChainInstance", back_populates="tasks")


class AccountGroup(Base):
    __tablename__ = "account_groups"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(500), nullable=True, default="")
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    members = relationship("AccountGroupMember", back_populates="group", cascade="all, delete-orphan")


class AccountGroupMember(Base):
    __tablename__ = "account_group_members"
    __table_args__ = (
        UniqueConstraint("group_id", "account_id", name="uq_group_account"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    group_id = Column(String(36), ForeignKey("account_groups.id", ondelete="CASCADE"), nullable=False)
    account_id = Column(String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    group = relationship("AccountGroup", back_populates="members")
    account = relationship("Account")


class ChainTemplate(Base):
    __tablename__ = "chain_templates"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True, default="")
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    steps = Column(JSON, nullable=False)  # [{step_order, type, label, params}, ...]
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    instances = relationship("ChainInstance", back_populates="template")


class ChainInstance(Base):
    __tablename__ = "chain_instances"

    id = Column(String(36), primary_key=True, default=_uuid)
    template_id = Column(String(36), ForeignKey("chain_templates.id", ondelete="RESTRICT"), nullable=False)
    account_id = Column(String(36), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False)
    device_id = Column(String(36), ForeignKey("devices.id"), nullable=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    current_step = Column(Integer, nullable=False, default=1)
    total_steps = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending, running, completed, failed, cancelled
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    template = relationship("ChainTemplate", back_populates="instances")
    account = relationship("Account")
    device = relationship("Device")
    tasks = relationship("Task", back_populates="chain_instance")


class Channel(Base):
    __tablename__ = "channels"

    id = Column(String(36), primary_key=True, default=_uuid)
    group_id = Column(String(36), ForeignKey("account_groups.id", ondelete="RESTRICT"), nullable=False)
    task_type = Column(String(30), nullable=False)  # search_comment, search_like, search_dm, reply_comment
    status = Column(String(20), nullable=False, default="active")  # active, paused, completed, cancelled
    account_mode = Column(String(20), nullable=False, default="round_robin")  # single_account, round_robin
    account_id = Column(String(36), ForeignKey("accounts.id"), nullable=True)  # single_account mode
    params_template = Column(JSON, nullable=False, default=dict)
    cooldown_seconds = Column(Integer, nullable=False, default=300)
    delay_range = Column(JSON, nullable=False, default=lambda: [3000, 8000])
    max_keywords = Column(Integer, nullable=False, default=500)
    current_account_index = Column(Integer, nullable=False, default=0)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    completed_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    group = relationship("AccountGroup")
    account = relationship("Account")
    items = relationship("ChannelItem", back_populates="channel", cascade="all, delete-orphan")


class ChannelItem(Base):
    __tablename__ = "channel_items"
    __table_args__ = (
        Index("ix_channel_items_channel_status", "channel_id", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    channel_id = Column(String(36), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    keyword = Column(String(200), nullable=False)
    account_id = Column(String(36), ForeignKey("accounts.id"), nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending, assigned, completed, failed, skipped
    assigned_device_id = Column(String(36), ForeignKey("devices.id"), nullable=True)
    assigned_at = Column(DateTime, nullable=True)  # for stale recovery
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=True)
    queue_position = Column(Integer, nullable=False, default=0)
    retry_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    completed_at = Column(DateTime, nullable=True)

    channel = relationship("Channel", back_populates="items")
    account = relationship("Account")
    device = relationship("Device")
    task = relationship("Task")


# ==== 多模型系列生成系统 ====

class Series(Base):
    __tablename__ = "series"

    id = Column(String(36), primary_key=True, default=_uuid)
    title = Column(String(200), nullable=False)
    logline = Column(Text, nullable=True)
    genre = Column(String(50), nullable=False, default="drama")
    total_episodes = Column(Integer, nullable=False, default=30)
    target_duration = Column(Integer, nullable=False, default=90)
    mode = Column(String(20), nullable=False, default="step_by_step")
    pilot_first = Column(Boolean, nullable=False, default=True)
    story_bible_json = Column(JSON, nullable=True, default=dict)
    status = Column(String(20), nullable=False, default="draft")
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    episodes = relationship("Episode", back_populates="series")
    characters = relationship("Character", secondary="series_characters", back_populates="series_list")
    scenes = relationship("Scene", secondary="series_scenes", back_populates="series_list")


# M2M: reverse relationships (lazy only, back_populates resolved at mapper configure time)
Character.series_list = relationship("Series", secondary="series_characters", back_populates="characters", lazy="noload")
Scene.series_list = relationship("Series", secondary="series_scenes", back_populates="scenes", lazy="noload")

series_characters = Table("series_characters", Base.metadata,
    Column("series_id", String(36), ForeignKey("series.id"), primary_key=True),
    Column("character_id", String(36), ForeignKey("characters.id"), primary_key=True),
)

series_scenes = Table("series_scenes", Base.metadata,
    Column("series_id", String(36), ForeignKey("series.id"), primary_key=True),
    Column("scene_id", String(36), ForeignKey("scenes.id"), primary_key=True),
)


class Episode(Base):
    __tablename__ = "episodes"

    id = Column(String(36), primary_key=True, default=_uuid)
    series_id = Column(String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    episode_number = Column(Integer, nullable=False)
    title = Column(String(200), nullable=True)
    script_json = Column(JSON, nullable=True, default=dict)
    storyboard_json = Column(JSON, nullable=True, default=dict)
    video_url = Column(Text, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    cost_so_far = Column(Float, nullable=True, default=0.0)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    series = relationship("Series", back_populates="episodes")
    __table_args__ = (
        UniqueConstraint("series_id", "episode_number"),
        Index("idx_episodes_series_id", "series_id"),
    )


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


class VideoReviewRecord(Base):
    """AI or human review decision for a production asset."""
    __tablename__ = "video_review_records"

    id = Column(String(36), primary_key=True, default=_uuid)
    asset_id = Column(String(36), ForeignKey("video_production_assets.id", ondelete="CASCADE"), nullable=False)
    run_id = Column(String(36), ForeignKey("video_production_runs.id", ondelete="CASCADE"), nullable=False)
    review_type = Column(String(20), nullable=False)
    status = Column(String(30), nullable=False)
    score = Column(Float, nullable=True)
    criteria_json = Column(JSON, nullable=True, default=list)
    issues_json = Column(JSON, nullable=True, default=list)
    reviewer_user_id = Column(String(36), nullable=True)
    reviewer_role = Column(String(40), nullable=True)
    action = Column(String(40), nullable=True)
    model_trace_json = Column(JSON, nullable=True, default=dict)
    asset_snapshot_json = Column(JSON, nullable=True, default=dict)
    model_trace_summary_json = Column(JSON, nullable=True, default=dict)
    comment = Column(Text, nullable=True)
    target_type = Column(String(30), nullable=True)
    target_id = Column(String(36), nullable=True)
    production_segment_id = Column(String(36), ForeignKey("production_segments.id", ondelete="SET NULL"), nullable=True)
    asset_version = Column(Integer, nullable=True)
    is_latest_asset_review = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    __table_args__ = (
        Index("idx_video_review_asset", "asset_id"),
        Index("idx_video_review_run", "run_id"),
        Index("idx_video_review_status", "status"),
        Index("idx_video_review_target_version", "target_type", "target_id", "asset_version"),
    )


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

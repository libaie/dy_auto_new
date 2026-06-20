"""Video production ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint


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

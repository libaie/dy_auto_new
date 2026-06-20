"""Script pipeline ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint


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


class EpisodeScript(Base):
    __tablename__ = "episode_scripts"
    __table_args__ = (
        Index("idx_episode_scripts_series_episode", "series_id", "episode_id"),
        Index("idx_episode_scripts_pipeline_run", "pipeline_run_id"),
        Index("idx_episode_scripts_status", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    series_id = Column(String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False)
    pipeline_run_id = Column(String(36), ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True)
    source_prompt = Column(Text, nullable=False)
    tags_json = Column(JSON, nullable=True, default=list)
    target_duration_seconds = Column(Integer, nullable=False, default=60)
    status = Column(String(30), nullable=False, default="draft")
    agency_trace_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class ScriptDramaticBeat(Base):
    __tablename__ = "script_dramatic_beats"
    __table_args__ = (
        UniqueConstraint("script_id", "order_index", name="uq_script_dramatic_beat_order"),
        Index("idx_script_dramatic_beats_script_id", "script_id"),
        Index("idx_script_dramatic_beats_type", "beat_type"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    script_id = Column(String(36), ForeignKey("episode_scripts.id", ondelete="CASCADE"), nullable=False)
    order_index = Column(Integer, nullable=False)
    beat_type = Column(String(40), nullable=False)
    emotional_value = Column(String(40), nullable=False)
    plot_summary = Column(Text, nullable=False)


class ScriptSceneOutline(Base):
    __tablename__ = "script_scene_outlines"
    __table_args__ = (
        UniqueConstraint("script_id", "scene_number", name="uq_script_scene_outline_number"),
        Index("idx_script_scene_outlines_script_id", "script_id"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    script_id = Column(String(36), ForeignKey("episode_scripts.id", ondelete="CASCADE"), nullable=False)
    scene_number = Column(Integer, nullable=False)
    dramatic_beat_type = Column(String(40), nullable=False)
    location = Column(String(160), nullable=False)
    characters_json = Column(JSON, nullable=True, default=list)
    conflict = Column(Text, nullable=False)
    emotional_turn = Column(Text, nullable=False)
    visual_mandate = Column(Text, nullable=False)


class ScriptVisualShot(Base):
    __tablename__ = "script_visual_shots"
    __table_args__ = (
        UniqueConstraint("script_id", "shot_number", name="uq_script_visual_shot_number"),
        Index("idx_script_visual_shots_script_id", "script_id"),
        Index("idx_script_visual_shots_scene", "script_id", "scene_number"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    script_id = Column(String(36), ForeignKey("episode_scripts.id", ondelete="CASCADE"), nullable=False)
    shot_number = Column(Integer, nullable=False)
    scene_number = Column(Integer, nullable=False)
    beat_type = Column(String(40), nullable=False)
    narration = Column(Text, nullable=False)
    visual_prompt = Column(Text, nullable=False)
    video_prompt = Column(Text, nullable=False)
    duration = Column(Float, nullable=False)

"""AI video series ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid
from app.db.models.ai_text_artifacts import AITextArtifact, AITextArtifactConsumer
from app.db.models.creative_library import Character, Scene
from app.db.models.production_observability import ProductionAuditEvent
from app.db.models.script_pipeline import EpisodeScript, PipelineRun

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship


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


Character.series_list = relationship("Series", secondary="series_characters", back_populates="characters", lazy="noload")
Scene.series_list = relationship("Series", secondary="series_scenes", back_populates="scenes", lazy="noload")

series_characters = Table(
    "series_characters",
    Base.metadata,
    Column("series_id", String(36), ForeignKey("series.id"), primary_key=True),
    Column("character_id", String(36), ForeignKey("characters.id"), primary_key=True),
)

series_scenes = Table(
    "series_scenes",
    Base.metadata,
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


_LEGACY_NAMES = {
    "ProductionEpisode",
    "ProductionJob",
    "ProductionPlan",
    "ProductionPlanVersion",
    "ProductionScene",
    "ProductionSegment",
    "ProductionShot",
    "VideoProductionRun",
}


def __getattr__(name):
    if name in _LEGACY_NAMES:
        from importlib import import_module

        video_production = import_module("app.db.models.video_production")
        value = getattr(video_production, name)
        globals()[name] = value
        return value
    raise AttributeError(name)


__all__ = [
    "Base",
    "series_characters",
    "series_scenes",
    "AITextArtifact",
    "AITextArtifactConsumer",
    "Episode",
    "EpisodeScript",
    "PipelineRun",
    "ProductionAuditEvent",
    "ProductionEpisode",
    "ProductionJob",
    "ProductionPlan",
    "ProductionPlanVersion",
    "ProductionScene",
    "ProductionSegment",
    "ProductionShot",
    "Series",
    "VideoProductionRun",
]

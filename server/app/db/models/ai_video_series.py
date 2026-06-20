"""AI video series ORM compatibility facade."""

from app.db.models.ai_text_artifacts import AITextArtifact, AITextArtifactConsumer
from app.db_models import (
    Base,
    series_characters,
    series_scenes,
    Episode,
    EpisodeScript,
    ProductionAuditEvent,
    ProductionEpisode,
    ProductionJob,
    ProductionPlan,
    ProductionPlanVersion,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    Series,
    VideoProductionRun,
)

__all__ = [
    "Base",
    "series_characters",
    "series_scenes",
    "AITextArtifact",
    "AITextArtifactConsumer",
    "Episode",
    "EpisodeScript",
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

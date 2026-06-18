from app.db_models import (
    AITextArtifact,
    AITextArtifactConsumer,
    Base,
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
    series_characters,
    series_scenes,
)


def test_ai_video_series_model_facade_reexports_legacy_classes():
    from app.db.models import ai_video_series as models

    assert models.AITextArtifact is AITextArtifact
    assert models.AITextArtifactConsumer is AITextArtifactConsumer
    assert models.Base is Base
    assert models.Episode is Episode
    assert models.EpisodeScript is EpisodeScript
    assert models.ProductionAuditEvent is ProductionAuditEvent
    assert models.ProductionEpisode is ProductionEpisode
    assert models.ProductionJob is ProductionJob
    assert models.ProductionPlan is ProductionPlan
    assert models.ProductionPlanVersion is ProductionPlanVersion
    assert models.ProductionScene is ProductionScene
    assert models.ProductionSegment is ProductionSegment
    assert models.ProductionShot is ProductionShot
    assert models.Series is Series
    assert models.VideoProductionRun is VideoProductionRun
    assert models.series_characters is series_characters
    assert models.series_scenes is series_scenes


def test_ai_video_series_model_facade_uses_one_metadata_object():
    from app.db.models import ai_video_series as models

    assert models.Series.metadata is Base.metadata
    assert models.Episode.metadata is Base.metadata
    assert models.VideoProductionRun.metadata is Base.metadata
    assert "series" in Base.metadata.tables
    assert "episodes" in Base.metadata.tables
    assert "video_production_runs" in Base.metadata.tables

from pathlib import Path

from app.db.models import (
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
SERVER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]


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
    assert models.Series.__module__ == "app.db.models.ai_video_series"
    assert models.Episode.__module__ == "app.db.models.ai_video_series"


def test_ai_video_series_model_facade_uses_one_metadata_object():
    from app.db.models import ai_video_series as models

    assert models.Series.metadata is Base.metadata
    assert models.Episode.metadata is Base.metadata
    assert models.VideoProductionRun.metadata is Base.metadata
    assert "series" in Base.metadata.tables
    assert "episodes" in Base.metadata.tables
    assert "video_production_runs" in Base.metadata.tables


def test_base_is_owned_by_app_db_base():
    from app.db.base import Base as SharedBase
    from app.db.models import Base as LegacyBase

    assert SharedBase is LegacyBase


def test_db_models_reexports_ai_video_series_facade_names():
    import app.db.models as legacy
    from app.db.models import ai_video_series as models

    for name in models.__all__:
        assert getattr(legacy, name) is getattr(models, name)


def test_ai_video_series_model_boundary_imports_in_clean_process():
    import subprocess
    import sys

    code = (
        "from app.db.models.ai_video_series import ProductionJob, Series; "
        "import app.db.models as legacy; "
        "assert legacy.Series is Series; "
        "assert Series.__module__ == 'app.db.models.ai_video_series'; "
        "assert legacy.ProductionJob is ProductionJob"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr

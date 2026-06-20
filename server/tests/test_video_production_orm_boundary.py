import subprocess
import sys
from pathlib import Path

from app.db_models import (
    Base,
    ProductionEpisode as LegacyProductionEpisode,
    ProductionPlan as LegacyProductionPlan,
    ProductionPlanVersion as LegacyProductionPlanVersion,
    ProductionScene as LegacyProductionScene,
    ProductionSegment as LegacyProductionSegment,
    ProductionShot as LegacyProductionShot,
    VideoCollection as LegacyVideoCollection,
)


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_video_production_model_boundary_reexports_video_collection():
    from app.db.models.video_production import (
        ProductionEpisode,
        ProductionPlan,
        ProductionPlanVersion,
        ProductionScene,
        ProductionSegment,
        ProductionShot,
        VideoCollection,
    )

    assert ProductionEpisode is LegacyProductionEpisode
    assert ProductionPlan is LegacyProductionPlan
    assert ProductionPlanVersion is LegacyProductionPlanVersion
    assert ProductionScene is LegacyProductionScene
    assert ProductionSegment is LegacyProductionSegment
    assert ProductionShot is LegacyProductionShot
    assert VideoCollection is LegacyVideoCollection
    assert ProductionEpisode.metadata is Base.metadata
    assert ProductionPlan.metadata is Base.metadata
    assert ProductionPlanVersion.metadata is Base.metadata
    assert ProductionScene.metadata is Base.metadata
    assert ProductionSegment.metadata is Base.metadata
    assert ProductionShot.metadata is Base.metadata
    assert VideoCollection.metadata is Base.metadata
    assert ProductionEpisode.__module__ == "app.db.models.video_production"
    assert ProductionPlan.__module__ == "app.db.models.video_production"
    assert ProductionPlanVersion.__module__ == "app.db.models.video_production"
    assert ProductionScene.__module__ == "app.db.models.video_production"
    assert ProductionSegment.__module__ == "app.db.models.video_production"
    assert ProductionShot.__module__ == "app.db.models.video_production"
    assert "production_episodes" in Base.metadata.tables
    assert "production_plans" in Base.metadata.tables
    assert "production_plan_versions" in Base.metadata.tables
    assert "production_scenes" in Base.metadata.tables
    assert "production_segments" in Base.metadata.tables
    assert "production_shots" in Base.metadata.tables
    assert "video_collections" in Base.metadata.tables


def test_video_production_model_boundary_imports_in_clean_process():
    code = (
        "import app.db_models as legacy; "
        "from app.db.models.video_production import ProductionEpisode, ProductionPlan, ProductionPlanVersion, ProductionScene, ProductionSegment, ProductionShot, VideoCollection; "
        "assert legacy.ProductionEpisode is ProductionEpisode; "
        "assert legacy.ProductionPlan is ProductionPlan; "
        "assert legacy.ProductionPlanVersion is ProductionPlanVersion; "
        "assert legacy.ProductionScene is ProductionScene; "
        "assert legacy.ProductionSegment is ProductionSegment; "
        "assert legacy.ProductionShot is ProductionShot; "
        "assert legacy.VideoCollection is VideoCollection; "
        "assert ProductionEpisode.__module__ == 'app.db.models.video_production'; "
        "assert ProductionPlan.__module__ == 'app.db.models.video_production'; "
        "assert ProductionPlanVersion.__module__ == 'app.db.models.video_production'; "
        "assert ProductionScene.__module__ == 'app.db.models.video_production'; "
        "assert ProductionSegment.__module__ == 'app.db.models.video_production'; "
        "assert ProductionShot.__module__ == 'app.db.models.video_production'; "
        "assert 'production_episodes' in legacy.Base.metadata.tables; "
        "assert 'production_plans' in legacy.Base.metadata.tables; "
        "assert 'production_plan_versions' in legacy.Base.metadata.tables; "
        "assert 'production_scenes' in legacy.Base.metadata.tables; "
        "assert 'production_segments' in legacy.Base.metadata.tables; "
        "assert 'production_shots' in legacy.Base.metadata.tables; "
        "assert 'video_collections' in legacy.Base.metadata.tables"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr

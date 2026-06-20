import subprocess
import sys
from pathlib import Path

from app.db_models import (
    Base,
    ProviderCostReservation as LegacyProviderCostReservation,
    ProviderStageTask as LegacyProviderStageTask,
    ProductionCostEvent as LegacyProductionCostEvent,
    ProductionEpisode as LegacyProductionEpisode,
    ProductionJob as LegacyProductionJob,
    ProductionPlan as LegacyProductionPlan,
    ProductionPlanVersion as LegacyProductionPlanVersion,
    ProductionScene as LegacyProductionScene,
    ProductionSegment as LegacyProductionSegment,
    ProductionShot as LegacyProductionShot,
    VideoCollection as LegacyVideoCollection,
    VideoProductionAsset as LegacyVideoProductionAsset,
    VideoProductionRun as LegacyVideoProductionRun,
    VideoReviewRecord as LegacyVideoReviewRecord,
)


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_video_production_model_boundary_reexports_video_collection():
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

    assert ProviderCostReservation is LegacyProviderCostReservation
    assert ProviderStageTask is LegacyProviderStageTask
    assert ProductionCostEvent is LegacyProductionCostEvent
    assert ProductionEpisode is LegacyProductionEpisode
    assert ProductionJob is LegacyProductionJob
    assert ProductionPlan is LegacyProductionPlan
    assert ProductionPlanVersion is LegacyProductionPlanVersion
    assert ProductionScene is LegacyProductionScene
    assert ProductionSegment is LegacyProductionSegment
    assert ProductionShot is LegacyProductionShot
    assert VideoCollection is LegacyVideoCollection
    assert VideoProductionAsset is LegacyVideoProductionAsset
    assert VideoProductionRun is LegacyVideoProductionRun
    assert VideoReviewRecord is LegacyVideoReviewRecord
    assert ProviderCostReservation.metadata is Base.metadata
    assert ProviderStageTask.metadata is Base.metadata
    assert ProductionCostEvent.metadata is Base.metadata
    assert ProductionEpisode.metadata is Base.metadata
    assert ProductionJob.metadata is Base.metadata
    assert ProductionPlan.metadata is Base.metadata
    assert ProductionPlanVersion.metadata is Base.metadata
    assert ProductionScene.metadata is Base.metadata
    assert ProductionSegment.metadata is Base.metadata
    assert ProductionShot.metadata is Base.metadata
    assert VideoCollection.metadata is Base.metadata
    assert VideoProductionAsset.metadata is Base.metadata
    assert VideoProductionRun.metadata is Base.metadata
    assert VideoReviewRecord.metadata is Base.metadata
    assert ProviderCostReservation.__module__ == "app.db.models.video_production"
    assert ProviderStageTask.__module__ == "app.db.models.video_production"
    assert ProductionCostEvent.__module__ == "app.db.models.video_production"
    assert ProductionEpisode.__module__ == "app.db.models.video_production"
    assert ProductionJob.__module__ == "app.db.models.video_production"
    assert ProductionPlan.__module__ == "app.db.models.video_production"
    assert ProductionPlanVersion.__module__ == "app.db.models.video_production"
    assert ProductionScene.__module__ == "app.db.models.video_production"
    assert ProductionSegment.__module__ == "app.db.models.video_production"
    assert ProductionShot.__module__ == "app.db.models.video_production"
    assert VideoProductionAsset.__module__ == "app.db.models.video_production"
    assert VideoProductionRun.__module__ == "app.db.models.video_production"
    assert VideoReviewRecord.__module__ == "app.db.models.video_production"
    assert "provider_cost_reservations" in Base.metadata.tables
    assert "provider_stage_tasks" in Base.metadata.tables
    assert "production_cost_events" in Base.metadata.tables
    assert "production_episodes" in Base.metadata.tables
    assert "production_jobs" in Base.metadata.tables
    assert "production_plans" in Base.metadata.tables
    assert "production_plan_versions" in Base.metadata.tables
    assert "production_scenes" in Base.metadata.tables
    assert "production_segments" in Base.metadata.tables
    assert "production_shots" in Base.metadata.tables
    assert "video_production_assets" in Base.metadata.tables
    assert "video_production_runs" in Base.metadata.tables
    assert "video_review_records" in Base.metadata.tables
    assert "video_collections" in Base.metadata.tables


def test_video_production_model_boundary_imports_in_clean_process():
    code = (
        "import app.db_models as legacy; "
        "from app.db.models.video_production import ProviderCostReservation, ProviderStageTask, ProductionCostEvent, ProductionEpisode, ProductionJob, ProductionPlan, ProductionPlanVersion, ProductionScene, ProductionSegment, ProductionShot, VideoCollection, VideoProductionAsset, VideoProductionRun, VideoReviewRecord; "
        "assert legacy.ProviderCostReservation is ProviderCostReservation; "
        "assert legacy.ProviderStageTask is ProviderStageTask; "
        "assert legacy.ProductionCostEvent is ProductionCostEvent; "
        "assert legacy.ProductionEpisode is ProductionEpisode; "
        "assert legacy.ProductionJob is ProductionJob; "
        "assert legacy.ProductionPlan is ProductionPlan; "
        "assert legacy.ProductionPlanVersion is ProductionPlanVersion; "
        "assert legacy.ProductionScene is ProductionScene; "
        "assert legacy.ProductionSegment is ProductionSegment; "
        "assert legacy.ProductionShot is ProductionShot; "
        "assert legacy.VideoCollection is VideoCollection; "
        "assert legacy.VideoProductionAsset is VideoProductionAsset; "
        "assert legacy.VideoProductionRun is VideoProductionRun; "
        "assert legacy.VideoReviewRecord is VideoReviewRecord; "
        "assert ProviderCostReservation.__module__ == 'app.db.models.video_production'; "
        "assert ProviderStageTask.__module__ == 'app.db.models.video_production'; "
        "assert ProductionCostEvent.__module__ == 'app.db.models.video_production'; "
        "assert ProductionEpisode.__module__ == 'app.db.models.video_production'; "
        "assert ProductionJob.__module__ == 'app.db.models.video_production'; "
        "assert ProductionPlan.__module__ == 'app.db.models.video_production'; "
        "assert ProductionPlanVersion.__module__ == 'app.db.models.video_production'; "
        "assert ProductionScene.__module__ == 'app.db.models.video_production'; "
        "assert ProductionSegment.__module__ == 'app.db.models.video_production'; "
        "assert ProductionShot.__module__ == 'app.db.models.video_production'; "
        "assert VideoProductionAsset.__module__ == 'app.db.models.video_production'; "
        "assert VideoProductionRun.__module__ == 'app.db.models.video_production'; "
        "assert VideoReviewRecord.__module__ == 'app.db.models.video_production'; "
        "assert 'provider_cost_reservations' in legacy.Base.metadata.tables; "
        "assert 'provider_stage_tasks' in legacy.Base.metadata.tables; "
        "assert 'production_cost_events' in legacy.Base.metadata.tables; "
        "assert 'production_episodes' in legacy.Base.metadata.tables; "
        "assert 'production_jobs' in legacy.Base.metadata.tables; "
        "assert 'production_plans' in legacy.Base.metadata.tables; "
        "assert 'production_plan_versions' in legacy.Base.metadata.tables; "
        "assert 'production_scenes' in legacy.Base.metadata.tables; "
        "assert 'production_segments' in legacy.Base.metadata.tables; "
        "assert 'production_shots' in legacy.Base.metadata.tables; "
        "assert 'video_production_assets' in legacy.Base.metadata.tables; "
        "assert 'video_production_runs' in legacy.Base.metadata.tables; "
        "assert 'video_review_records' in legacy.Base.metadata.tables; "
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

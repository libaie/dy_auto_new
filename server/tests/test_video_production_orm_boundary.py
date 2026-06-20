import subprocess
import sys
from pathlib import Path

from app.db_models import Base, ProductionPlan as LegacyProductionPlan, VideoCollection as LegacyVideoCollection


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_video_production_model_boundary_reexports_video_collection():
    from app.db.models.video_production import ProductionPlan, VideoCollection

    assert ProductionPlan is LegacyProductionPlan
    assert VideoCollection is LegacyVideoCollection
    assert ProductionPlan.metadata is Base.metadata
    assert VideoCollection.metadata is Base.metadata
    assert ProductionPlan.__module__ == "app.db.models.video_production"
    assert "production_plans" in Base.metadata.tables
    assert "video_collections" in Base.metadata.tables


def test_video_production_model_boundary_imports_in_clean_process():
    code = (
        "import app.db_models as legacy; "
        "from app.db.models.video_production import ProductionPlan, VideoCollection; "
        "assert legacy.ProductionPlan is ProductionPlan; "
        "assert legacy.VideoCollection is VideoCollection; "
        "assert ProductionPlan.__module__ == 'app.db.models.video_production'; "
        "assert 'production_plans' in legacy.Base.metadata.tables; "
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

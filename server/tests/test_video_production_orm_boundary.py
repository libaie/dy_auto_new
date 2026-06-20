import subprocess
import sys
from pathlib import Path

from app.db_models import Base, VideoCollection as LegacyVideoCollection


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_video_production_model_boundary_reexports_video_collection():
    from app.db.models.video_production import VideoCollection

    assert VideoCollection is LegacyVideoCollection
    assert VideoCollection.metadata is Base.metadata
    assert "video_collections" in Base.metadata.tables


def test_video_production_model_boundary_imports_in_clean_process():
    code = (
        "import app.db_models as legacy; "
        "from app.db.models.video_production import VideoCollection; "
        "assert legacy.VideoCollection is VideoCollection; "
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

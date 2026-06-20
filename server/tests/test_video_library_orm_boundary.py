import subprocess
import sys
from pathlib import Path

from app.db.models import Base, GeneratedVideo as LegacyGeneratedVideo


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_video_library_model_boundary_reexports_generated_video():
    from app.db.models.video_library import GeneratedVideo

    assert GeneratedVideo is LegacyGeneratedVideo
    assert GeneratedVideo.metadata is Base.metadata
    assert "generated_videos" in Base.metadata.tables


def test_video_library_model_boundary_imports_in_clean_process():
    code = (
        "import app.db.models as legacy; "
        "from app.db.models.video_library import GeneratedVideo; "
        "assert legacy.GeneratedVideo is GeneratedVideo; "
        "assert 'generated_videos' in legacy.Base.metadata.tables"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr

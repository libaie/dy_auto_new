import subprocess
import sys
from pathlib import Path

from app.db.models import Base
from app.db.models import PipelineRun as LegacyPipelineRun


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_script_pipeline_model_boundary_reexports_pipeline_run():
    from app.db.models.script_pipeline import PipelineRun

    assert PipelineRun is LegacyPipelineRun
    assert PipelineRun.metadata is Base.metadata
    assert "pipeline_runs" in Base.metadata.tables


def test_script_pipeline_model_boundary_imports_in_clean_process():
    code = (
        "import app.db.models as legacy; "
        "from app.db.models.script_pipeline import PipelineRun; "
        "assert legacy.PipelineRun is PipelineRun; "
        "assert 'pipeline_runs' in legacy.Base.metadata.tables"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr

import subprocess
import sys
from pathlib import Path

from app.db.models import Base, Task as LegacyTask


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_task_operations_model_boundary_reexports_task_model():
    from app.db.models.task_operations import Task

    assert Task is LegacyTask
    assert Task.metadata is Base.metadata
    assert "tasks" in Base.metadata.tables


def test_task_operations_model_boundary_imports_in_clean_process():
    code = (
        "import app.db.models as legacy; "
        "from app.db.models.task_operations import Task; "
        "assert legacy.Task is Task; "
        "assert 'tasks' in legacy.Base.metadata.tables"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr

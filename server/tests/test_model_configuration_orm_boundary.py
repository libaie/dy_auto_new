import subprocess
import sys
from pathlib import Path

from app.db.models import AIModel as LegacyAIModel, Base


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_model_configuration_model_boundary_reexports_ai_model():
    from app.db.models.model_configuration import AIModel

    assert AIModel is LegacyAIModel
    assert AIModel.metadata is Base.metadata
    assert "ai_models" in Base.metadata.tables


def test_model_configuration_model_boundary_imports_in_clean_process():
    code = (
        "import app.db.models as legacy; "
        "from app.db.models.model_configuration import AIModel; "
        "assert legacy.AIModel is AIModel; "
        "assert 'ai_models' in legacy.Base.metadata.tables"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr

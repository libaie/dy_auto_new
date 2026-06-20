import subprocess
import sys
from pathlib import Path

from app.db.models import AITextArtifact as LegacyAITextArtifact
from app.db.models import AITextArtifactConsumer as LegacyAITextArtifactConsumer
from app.db.models import Base


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_ai_text_artifact_model_boundary_reexports_models():
    from app.db.models.ai_text_artifacts import AITextArtifact, AITextArtifactConsumer

    assert AITextArtifact is LegacyAITextArtifact
    assert AITextArtifactConsumer is LegacyAITextArtifactConsumer
    assert AITextArtifact.metadata is Base.metadata
    assert AITextArtifactConsumer.metadata is Base.metadata
    assert "ai_text_artifacts" in Base.metadata.tables
    assert "ai_text_artifact_consumers" in Base.metadata.tables


def test_ai_text_artifact_model_boundary_imports_in_clean_process():
    code = (
        "import app.db.models as legacy; "
        "from app.db.models.ai_text_artifacts import AITextArtifact, AITextArtifactConsumer; "
        "assert legacy.AITextArtifact is AITextArtifact; "
        "assert legacy.AITextArtifactConsumer is AITextArtifactConsumer; "
        "assert 'ai_text_artifacts' in legacy.Base.metadata.tables; "
        "assert 'ai_text_artifact_consumers' in legacy.Base.metadata.tables"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr

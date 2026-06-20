import subprocess
import sys
from pathlib import Path

from app.db_models import Base
from app.db_models import CharacterAnchor as LegacyCharacterAnchor
from app.db_models import SceneAnchor as LegacySceneAnchor


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_creative_library_model_boundary_reexports_anchor_models():
    from app.db.models.creative_library import CharacterAnchor, SceneAnchor

    assert CharacterAnchor is LegacyCharacterAnchor
    assert SceneAnchor is LegacySceneAnchor
    assert CharacterAnchor.metadata is Base.metadata
    assert SceneAnchor.metadata is Base.metadata
    assert "character_anchors" in Base.metadata.tables
    assert "scene_anchors" in Base.metadata.tables


def test_creative_library_model_boundary_imports_in_clean_process():
    code = (
        "import app.db_models as legacy; "
        "from app.db.models.creative_library import CharacterAnchor, SceneAnchor; "
        "assert legacy.CharacterAnchor is CharacterAnchor; "
        "assert legacy.SceneAnchor is SceneAnchor; "
        "assert 'character_anchors' in legacy.Base.metadata.tables; "
        "assert 'scene_anchors' in legacy.Base.metadata.tables"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr

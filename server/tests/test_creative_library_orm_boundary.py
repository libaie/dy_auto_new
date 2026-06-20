import subprocess
import sys
from pathlib import Path

from app.db_models import (
    Base,
    Character as LegacyCharacter,
    ReferenceCategory as LegacyReferenceCategory,
    ReferenceData as LegacyReferenceData,
    Scene as LegacyScene,
)


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_creative_library_model_boundary_reexports_reference_models():
    from app.db.models.creative_library import Character, ReferenceCategory, ReferenceData, Scene

    assert Character is LegacyCharacter
    assert ReferenceData is LegacyReferenceData
    assert ReferenceCategory is LegacyReferenceCategory
    assert Scene is LegacyScene
    assert Character.metadata is Base.metadata
    assert ReferenceData.metadata is Base.metadata
    assert ReferenceCategory.metadata is Base.metadata
    assert Scene.metadata is Base.metadata
    assert "characters" in Base.metadata.tables
    assert "reference_data" in Base.metadata.tables
    assert "reference_categories" in Base.metadata.tables
    assert "scenes" in Base.metadata.tables


def test_creative_library_model_boundary_imports_in_clean_process():
    code = (
        "import app.db_models as legacy; "
        "from app.db.models.creative_library import Character, ReferenceCategory, ReferenceData, Scene; "
        "assert legacy.Character is Character; "
        "assert legacy.ReferenceData is ReferenceData; "
        "assert legacy.ReferenceCategory is ReferenceCategory; "
        "assert legacy.Scene is Scene"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr

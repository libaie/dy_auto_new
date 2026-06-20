import subprocess
import sys
from pathlib import Path

from app.db_models import (
    Base,
    ReferenceCategory as LegacyReferenceCategory,
    ReferenceData as LegacyReferenceData,
)


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_creative_library_model_boundary_reexports_reference_models():
    from app.db.models.creative_library import ReferenceCategory, ReferenceData

    assert ReferenceData is LegacyReferenceData
    assert ReferenceCategory is LegacyReferenceCategory
    assert ReferenceData.metadata is Base.metadata
    assert ReferenceCategory.metadata is Base.metadata
    assert "reference_data" in Base.metadata.tables
    assert "reference_categories" in Base.metadata.tables


def test_creative_library_model_boundary_imports_in_clean_process():
    code = (
        "import app.db_models as legacy; "
        "from app.db.models.creative_library import ReferenceCategory, ReferenceData; "
        "assert legacy.ReferenceData is ReferenceData; "
        "assert legacy.ReferenceCategory is ReferenceCategory"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr

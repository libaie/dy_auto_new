import subprocess
import sys
from pathlib import Path

from app.db.models import Base, UISelector as LegacyUISelector


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_selector_management_model_boundary_reexports_ui_selector():
    from app.db.models.selector_management import UISelector

    assert UISelector is LegacyUISelector
    assert UISelector.metadata is Base.metadata
    assert "ui_selectors" in Base.metadata.tables


def test_selector_management_model_boundary_imports_in_clean_process():
    code = (
        "import app.db.models as legacy; "
        "from app.db.models.selector_management import UISelector; "
        "assert legacy.UISelector is UISelector; "
        "assert 'ui_selectors' in legacy.Base.metadata.tables"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr

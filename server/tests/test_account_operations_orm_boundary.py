import subprocess
import sys
from pathlib import Path

from app.db_models import Account as LegacyAccount
from app.db_models import Base


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_account_operations_model_boundary_reexports_account():
    from app.db.models.account_operations import Account

    assert Account is LegacyAccount
    assert Account.metadata is Base.metadata
    assert "accounts" in Base.metadata.tables


def test_account_operations_model_boundary_imports_in_clean_process():
    code = (
        "import app.db_models as legacy; "
        "from app.db.models.account_operations import Account; "
        "assert legacy.Account is Account; "
        "assert 'accounts' in legacy.Base.metadata.tables"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr

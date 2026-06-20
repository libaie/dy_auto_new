import subprocess
import sys
from pathlib import Path

from app.db.models import Base, User as LegacyUser


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_identity_access_model_boundary_reexports_user():
    from app.db.models.identity_access import User

    assert User is LegacyUser
    assert User.metadata is Base.metadata
    assert "users" in Base.metadata.tables


def test_identity_access_model_boundary_imports_in_clean_process():
    code = (
        "import app.db.models as legacy; "
        "from app.db.models.identity_access import User; "
        "assert legacy.User is User; "
        "assert 'users' in legacy.Base.metadata.tables"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr

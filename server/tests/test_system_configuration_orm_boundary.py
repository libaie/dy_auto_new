import subprocess
import sys
from pathlib import Path

from app.db_models import Base, SystemSetting as LegacySystemSetting


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_system_configuration_model_boundary_reexports_system_setting():
    from app.db.models.system_configuration import SystemSetting

    assert SystemSetting is LegacySystemSetting
    assert SystemSetting.metadata is Base.metadata
    assert "system_settings" in Base.metadata.tables


def test_system_configuration_model_boundary_imports_in_clean_process():
    code = (
        "import app.db_models as legacy; "
        "from app.db.models.system_configuration import SystemSetting; "
        "assert legacy.SystemSetting is SystemSetting; "
        "assert 'system_settings' in legacy.Base.metadata.tables"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr

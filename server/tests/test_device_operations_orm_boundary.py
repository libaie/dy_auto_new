import subprocess
import sys
from pathlib import Path

from app.db_models import Base, DevicePairRequest as LegacyDevicePairRequest


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_device_operations_model_boundary_reexports_device_pair_request():
    from app.db.models.device_operations import DevicePairRequest

    assert DevicePairRequest is LegacyDevicePairRequest
    assert DevicePairRequest.metadata is Base.metadata
    assert "device_pair_requests" in Base.metadata.tables


def test_device_operations_model_boundary_imports_in_clean_process():
    code = (
        "import app.db_models as legacy; "
        "from app.db.models.device_operations import DevicePairRequest; "
        "assert legacy.DevicePairRequest is DevicePairRequest; "
        "assert 'device_pair_requests' in legacy.Base.metadata.tables"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr

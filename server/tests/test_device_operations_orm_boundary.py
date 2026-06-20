import subprocess
import sys
from pathlib import Path

from app.db_models import Base, Device as LegacyDevice, DevicePairRequest as LegacyDevicePairRequest


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_device_operations_model_boundary_reexports_device_models():
    from app.db.models.device_operations import Device, DevicePairRequest

    assert Device is LegacyDevice
    assert DevicePairRequest is LegacyDevicePairRequest
    assert Device.metadata is Base.metadata
    for table_name in ("devices", "device_pair_requests"):
        assert table_name in Base.metadata.tables


def test_device_operations_model_boundary_imports_in_clean_process():
    code = (
        "import app.db_models as legacy; "
        "from app.db.models.device_operations import Device, DevicePairRequest; "
        "assert legacy.Device is Device; "
        "assert legacy.DevicePairRequest is DevicePairRequest; "
        "assert 'devices' in legacy.Base.metadata.tables; "
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

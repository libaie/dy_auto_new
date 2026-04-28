"""Device service tests."""
import pytest
from app.services.device_service import device_service


def test_register_new_device(db):
    result = device_service.register(
        db=db, device_id="dev-test-register", name="Test Device",
        os_version="Android 13", app_version="1.0.0",
    )
    assert result["device_id"] == "dev-test-register"
    assert result["name"] == "Test Device"


def test_register_existing_device_updates(db):
    device_service.register(db, "dev-reregister", "Old Name", "Android 12", "1.0.0")
    result = device_service.register(db, "dev-reregister", "New Name", "Android 13", "1.1.0")
    assert result["name"] == "New Name"


def test_update_heartbeat(db):
    device_service.register(db, "dev-hb-test", "HB Device", "Android 13", "1.0.0")
    device_service.update_heartbeat(db, "dev-hb-test")
    assert True


def test_update_heartbeat_unknown_device(db):
    device_service.update_heartbeat(db, "dev-unknown-hb")
    assert True


def test_get_device_status(db):
    device_service.register(db, "dev-status-test", "Status Device", "Android 13", "1.0.0")
    info = device_service.get_device_status(db, "dev-status-test")
    assert info is not None
    assert info["device_id"] == "dev-status-test"
    assert info["status"] == "online"
    assert "proxy_config" in info


def test_get_device_status_unknown(db):
    info = device_service.get_device_status(db, "dev-nonexistent")
    assert info is None


def test_set_offline_devices(db):
    """Devices without recent heartbeat get marked offline."""
    device_service.register(db, "dev-offline-test", "Offline Device")
    from app.db_models import Device
    from datetime import datetime, timezone, timedelta
    device = db.query(Device).filter(Device.id == "dev-offline-test").first()
    device.last_seen_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    db.commit()
    count = device_service.set_offline_devices(db, timeout_seconds=300)
    assert count >= 1
    info = device_service.get_device_status(db, "dev-offline-test")
    assert info["status"] == "offline"

"""Device-facing API endpoint tests."""
import io
import pytest
from fastapi.testclient import TestClient
from app.main import app
from tests.script_package_fixture import script_package

client = TestClient(app)
SECRET = "change-me-to-a-random-string"
HEADERS = {"X-Device-Secret": SECRET}


@pytest.fixture(autouse=True)
def isolate_script_service(tmp_path, monkeypatch):
    """Keep script upload/download endpoint tests out of the real server/scripts dir."""
    from app.services.script_service import script_service

    script_dir = tmp_path / "scripts"
    monkeypatch.setattr(script_service, "_script_dir", script_dir)
    monkeypatch.setattr(script_service, "_version_file", script_dir / "version.txt")


def test_script_version():
    resp = client.get("/api/device/script-version", headers=HEADERS)
    assert resp.status_code == 200
    assert "version" in resp.json()
    assert isinstance(resp.json()["version"], str)


def test_script_download_no_script():
    """Download endpoint returns 200 (if script exists from prior test) or 404."""
    resp = client.get("/api/device/script-download", headers=HEADERS)
    assert resp.status_code == 200 or resp.status_code == 404
    if resp.status_code == 200:
        assert len(resp.content) > 0


def test_script_upload_and_download():
    """Upload a script, then download it."""
    zip_content = script_package()
    resp = client.post("/api/device/script-upload",
        files={"file": ("device.zip", io.BytesIO(zip_content), "application/zip")},
        headers=HEADERS)
    assert resp.status_code == 200
    assert "version" in resp.json()
    dl_resp = client.get("/api/device/script-download", headers=HEADERS)
    assert dl_resp.status_code == 200
    assert len(dl_resp.content) > 0


def test_script_upload_rejects_incomplete_zip_without_advancing_version():
    transport = TestClient(app, raise_server_exceptions=False)
    old_version = transport.get("/api/device/script-version", headers=HEADERS).json()["version"]
    resp = transport.post("/api/device/script-upload",
        files={"file": ("device.zip", io.BytesIO(b"PK\x03\x04broken archive"), "application/zip")},
        headers=HEADERS)
    assert resp.status_code == 400
    assert resp.json()["detail"]
    assert transport.get("/api/device/script-version", headers=HEADERS).json()["version"] == old_version
    assert transport.get("/api/device/script-download", headers=HEADERS).status_code == 404


def test_script_upload_rejects_non_zip():
    resp = client.post("/api/device/script-upload",
        files={"file": ("test.txt", io.BytesIO(b"not a zip"), "text/plain")},
        headers=HEADERS)
    assert resp.status_code == 400


def test_script_version_requires_auth():
    resp = client.get("/api/device/script-version")
    assert resp.status_code == 401


def test_script_upload_rejects_oversized():
    """Files over 10MB should be rejected."""
    big_content = b"x" * (10 * 1024 * 1024 + 1)
    resp = client.post("/api/device/script-upload",
        files={"file": ("big.zip", io.BytesIO(big_content), "application/zip")},
        headers=HEADERS)
    assert resp.status_code == 400


def test_device_template_download_with_per_device_secret(db, tmp_path, monkeypatch):
    """Per-device auth should resolve device resolution and still fall back to default templates."""
    from app.db_models import Device
    from app.services import template_service as template_module

    monkeypatch.setattr(template_module, "TEMPLATE_DIR", tmp_path)
    template_module.template_service._md5_cache.clear()
    default_dir = tmp_path / "default"
    default_dir.mkdir()
    (default_dir / "sort_latest_test.jpg").write_bytes(b"jpg-bytes")

    db.add(Device(
        id="dev-template-test",
        name="Template Test",
        status="online",
        device_secret="template-secret",
        screen_resolution="1080x2340",
    ))
    db.commit()

    resp = client.get(
        "/api/device/templates/sort_latest_test.jpg",
        headers={"X-Device-Secret": "template-secret"},
    )

    assert resp.status_code == 200
    assert resp.content == b"jpg-bytes"


def test_register_device():
    resp = client.post("/api/device/register", json={
        "device_id": "dev-register-test", "name": "Test Phone",
        "os_version": "Android 13", "app_version": "1.0.0",
    }, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["device_id"] == "dev-register-test"
    assert data["status"] == "online"
    assert "config" in data
    assert "poll_interval" in data["config"]
    assert "anti_detect_config" in data["config"]


def test_register_device_requires_auth():
    resp = client.post("/api/device/register", json={
        "device_id": "dev-no-auth", "name": "Test",
    })
    assert resp.status_code == 401


def test_heartbeat_updates_device():
    client.post("/api/device/register", json={
        "device_id": "dev-hb-e2e", "name": "HB Test",
    }, headers=HEADERS)
    resp = client.post("/api/device/heartbeat",
        json={"device_id": "dev-hb-e2e"}, headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_poll_returns_proxy_config(db):
    """Poll response includes proxy config for registered device."""
    from app.db_models import Device
    device = Device(id="dev-proxy-test", name="Proxy Device", status="online")
    device.proxy_config = {"type": "http", "host": "proxy.test", "port": 8080}
    db.add(device)
    db.commit()

    resp = client.get("/api/device/poll",
        params={"device_id": "dev-proxy-test"}, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("proxy") is not None
    assert data["proxy"]["host"] == "proxy.test"


def test_device_task_dm_sequence_is_included_even_when_not_device_scoped(db):
    """A device must receive the full DM sequence referenced by its assigned task."""
    from app.db_models import Device, DMSequence, Task

    seq_id = "seq-owned-by-web-user"
    device_headers = {"X-Device-Secret": "dev-dm-seq-secret"}
    db.add(Device(
        id="dev-dm-seq-task",
        name="DM Seq Device",
        status="online",
        device_secret="dev-dm-seq-secret",
    ))
    db.add(DMSequence(
        id=seq_id,
        name="Owned Sequence",
        messages=[{"order": 1, "content": "base", "delay_ms": 100}],
        variants=[[{"order": 1, "content": "variant", "delay_ms": 100}]],
        user_id="web-user-1",
    ))
    db.add(Task(
        type="reply_comment",
        account_id="acc-001",
        device_id="dev-dm-seq-task",
        user_id=None,
        params={"keyword": "餐后血糖", "dm_sequence_id": seq_id},
        status="pending",
    ))
    db.commit()

    sync_resp = client.get("/api/dm-sequences/device/sync", headers=device_headers)
    assert sync_resp.status_code == 200
    assert any(s["id"] == seq_id for s in sync_resp.json()["dm_sequences"])

    poll_resp = client.get(
        "/api/device/poll",
        params={"device_id": "dev-dm-seq-task"},
        headers=device_headers,
    )
    assert poll_resp.status_code == 200
    poll_data = poll_resp.json()
    assert poll_data["task"]["params"]["dm_sequence_id"] == seq_id
    matched = [s for s in poll_data["dm_sequences"] if s["id"] == seq_id]
    assert matched
    assert matched[0]["variants"][0][0]["content"] == "variant"

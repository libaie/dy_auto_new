"""Device-facing API endpoint tests."""
import io
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
SECRET = "change-me-to-a-random-string"
HEADERS = {"X-Device-Secret": SECRET}


def test_script_version():
    resp = client.get("/api/device/script-version", headers=HEADERS)
    assert resp.status_code == 200
    assert "version" in resp.json()
    assert isinstance(resp.json()["version"], str)


def test_script_download_no_script():
    """When no script uploaded, returns 404."""
    resp = client.get("/api/device/script-download", headers=HEADERS)
    assert resp.status_code in (200, 404)


def test_script_upload_and_download():
    """Upload a script, then download it."""
    zip_content = b"PK\x03\x04fake zip content"
    resp = client.post("/api/device/script-upload",
        files={"file": ("device.zip", io.BytesIO(zip_content), "application/zip")},
        headers=HEADERS)
    assert resp.status_code == 200
    assert "version" in resp.json()
    dl_resp = client.get("/api/device/script-download", headers=HEADERS)
    assert dl_resp.status_code == 200
    assert len(dl_resp.content) > 0


def test_script_upload_rejects_non_zip():
    resp = client.post("/api/device/script-upload",
        files={"file": ("test.txt", io.BytesIO(b"not a zip"), "text/plain")},
        headers=HEADERS)
    assert resp.status_code == 400


def test_script_version_requires_auth():
    resp = client.get("/api/device/script-version")
    assert resp.status_code == 401


def test_register_device():
    resp = client.post("/api/device/register", json={
        "device_id": "dev-register-test", "name": "Test Phone",
        "os_version": "Android 13", "app_version": "1.0.0",
    }, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["device_id"] == "dev-register-test"
    assert data["status"] == "online"


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

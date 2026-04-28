"""Device CRUD API tests."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
SECRET = "change-me-to-a-random-string"
HEADERS = {"X-Device-Secret": SECRET}


def test_create_device():
    resp = client.post("/api/devices", json={
        "name": "测试设备",
        "ip": "192.168.1.100",
    }, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "测试设备"
    assert data["ip"] == "192.168.1.100"
    assert data["status"] == "offline"
    assert "id" in data


def test_list_devices():
    resp = client.get("/api/devices", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "devices" in data
    assert data["total"] >= 1


def test_get_device():
    create_resp = client.post("/api/devices", json={"name": "查询测试"}, headers=HEADERS)
    device_id = create_resp.json()["id"]

    resp = client.get(f"/api/devices/{device_id}", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["id"] == device_id


def test_get_nonexistent_device():
    resp = client.get("/api/devices/nonexistent-id", headers=HEADERS)
    assert resp.status_code == 404


def test_update_device():
    create_resp = client.post("/api/devices", json={"name": "更新前"}, headers=HEADERS)
    device_id = create_resp.json()["id"]

    resp = client.put(f"/api/devices/{device_id}", json={
        "name": "更新后",
        "status": "online",
        "proxy_config": {"type": "http", "host": "proxy.example.com", "port": 8080},
    }, headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["name"] == "更新后"
    assert resp.json()["status"] == "online"
    assert resp.json()["proxy_config"]["host"] == "proxy.example.com"


def test_delete_device():
    create_resp = client.post("/api/devices", json={"name": "删除测试"}, headers=HEADERS)
    device_id = create_resp.json()["id"]

    resp = client.delete(f"/api/devices/{device_id}", headers=HEADERS)
    assert resp.status_code == 200

    resp = client.get(f"/api/devices/{device_id}", headers=HEADERS)
    assert resp.status_code == 404


def test_auth_required():
    resp = client.get("/api/devices")
    assert resp.status_code == 401


def test_create_device_missing_name():
    resp = client.post("/api/devices", json={}, headers=HEADERS)
    assert resp.status_code == 422


def test_update_nonexistent_device():
    resp = client.put("/api/devices/nonexistent-id", json={"name": "x"}, headers=HEADERS)
    assert resp.status_code == 404


def test_delete_nonexistent_device():
    resp = client.delete("/api/devices/nonexistent-id", headers=HEADERS)
    assert resp.status_code == 404


def test_create_device_with_proxy():
    resp = client.post("/api/devices", json={
        "name": "proxy设备",
        "proxy_config": {"type": "http", "host": "proxy.example.com", "port": 8080},
    }, headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["proxy_config"]["host"] == "proxy.example.com"

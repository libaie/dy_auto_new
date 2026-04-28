"""Device API tests."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
SECRET = "change-me-to-a-random-string"
HEADERS = {"X-Device-Secret": SECRET}


def test_device_poll_no_task():
    resp = client.get("/api/device/poll", params={"device_id": "dev-test"}, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "selectors_version" in data


def test_device_poll_with_task():
    # Create a task first
    client.post("/api/tasks", json={
        "type": "nurture",
        "account_id": "acc-001",
        "params": {"duration": 5},
    }, headers=HEADERS)

    resp = client.get("/api/device/poll", params={"device_id": "dev-poll"}, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["task"] is not None
    assert data["task"]["type"] == "nurture"


def test_device_report():
    # Create + poll + report
    create_resp = client.post("/api/tasks", json={
        "type": "nurture",
        "account_id": "acc-001",
        "params": {"duration": 5},
    }, headers=HEADERS)
    task_id = create_resp.json()["id"]

    client.get("/api/device/poll", params={"device_id": "dev-report"}, headers=HEADERS)

    report_resp = client.post("/api/device/report", json={
        "task_id": task_id,
        "status": "completed",
        "result": {"success_count": 1},
    }, headers=HEADERS)
    assert report_resp.status_code == 200


def test_device_auth_required():
    resp = client.get("/api/device/poll", params={"device_id": "dev-test"})
    assert resp.status_code == 401

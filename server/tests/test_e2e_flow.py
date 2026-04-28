"""End-to-end integration test — DB-backed."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
SECRET = "change-me-to-a-random-string"
HEADERS = {"X-Device-Secret": SECRET}


def test_full_task_lifecycle():
    """Create -> poll -> report -> verify completed."""
    create_resp = client.post("/api/tasks", json={
        "type": "nurture", "account_id": "acc-001", "params": {"duration": 5},
    }, headers=HEADERS)
    task_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "pending"

    poll_resp = client.get("/api/device/poll", params={"device_id": "dev-e2e"}, headers=HEADERS)
    assert poll_resp.json()["task"]["id"] == task_id

    client.post("/api/device/report", json={
        "task_id": task_id, "status": "completed",
        "result": {"success_count": 3, "fail_count": 0, "details": "OK"},
    }, headers=HEADERS)

    detail = client.get(f"/api/tasks/{task_id}", headers=HEADERS).json()
    assert detail["status"] == "completed"
    assert detail["result"]["success_count"] == 3


def test_full_flow_with_failure_and_retry():
    """Create -> poll -> fail -> re-poll -> succeed."""
    create_resp = client.post("/api/tasks", json={
        "type": "nurture", "account_id": "acc-001", "params": {"duration": 10},
    }, headers=HEADERS)
    task_id = create_resp.json()["id"]

    client.get("/api/device/poll", params={"device_id": "dev-retry"}, headers=HEADERS)

    client.post("/api/device/report", json={
        "task_id": task_id, "status": "failed", "result": {"details": "error"},
    }, headers=HEADERS)

    detail = client.get(f"/api/tasks/{task_id}", headers=HEADERS).json()
    assert detail["status"] == "pending"

    poll2 = client.get("/api/device/poll", params={"device_id": "dev-retry2"}, headers=HEADERS).json()
    assert poll2["task"]["id"] == task_id

    client.post("/api/device/report", json={
        "task_id": task_id, "status": "completed", "result": {"success_count": 1},
    }, headers=HEADERS)

    final = client.get(f"/api/tasks/{task_id}", headers=HEADERS).json()
    assert final["status"] == "completed"


def test_selectors_endpoint():
    resp = client.get("/api/device/selectors", params={"version": 0}, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["changed"] is True
    assert data["version"] >= 1

    resp2 = client.get("/api/device/selectors", params={"version": data["version"]}, headers=HEADERS)
    assert resp2.json()["changed"] is False


def test_heartbeat():
    resp = client.post("/api/device/heartbeat", json={"device_id": "dev-test"}, headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_report_nonexistent_task():
    resp = client.post("/api/device/report", json={
        "task_id": "nonexistent-id",
        "status": "completed",
        "result": {},
    }, headers=HEADERS)
    assert resp.status_code == 404


def test_list_tasks_with_status_filter():
    resp = client.get("/api/tasks", params={"status": "pending"}, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "tasks" in data
    assert "total" in data
    for task in data["tasks"]:
        assert task["status"] == "pending"


def test_get_nonexistent_task():
    resp = client.get("/api/tasks/nonexistent-id", headers=HEADERS)
    assert resp.status_code == 404

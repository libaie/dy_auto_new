import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import DEVICE_SECRET

client = TestClient(app)


def test_device_poll_no_task():
    response = client.get(
        "/api/device/poll",
        params={"device_id": "dev-001"},
        headers={"X-Device-Secret": DEVICE_SECRET},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["task"] is None
    assert "selectors_version" in data


def test_device_poll_with_task():
    # 先创建一个任务
    client.post(
        "/api/tasks",
        json={"type": "nurture", "account_id": "acc-001", "params": {"duration": 30}},
        headers={"X-Device-Secret": DEVICE_SECRET},
    )

    response = client.get(
        "/api/device/poll",
        params={"device_id": "dev-001"},
        headers={"X-Device-Secret": DEVICE_SECRET},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["task"] is not None
    assert data["task"]["status"] == "running"


def test_device_report():
    # 创建任务并领取
    create_resp = client.post(
        "/api/tasks",
        json={"type": "nurture", "account_id": "acc-001", "params": {"duration": 30}},
        headers={"X-Device-Secret": DEVICE_SECRET},
    )
    task_id = create_resp.json()["id"]

    poll_resp = client.get(
        "/api/device/poll",
        params={"device_id": "dev-001"},
        headers={"X-Device-Secret": DEVICE_SECRET},
    )

    # 上报结果
    report_resp = client.post(
        "/api/device/report",
        json={
            "task_id": task_id,
            "status": "completed",
            "result": {"success_count": 1, "fail_count": 0},
        },
        headers={"X-Device-Secret": DEVICE_SECRET},
    )
    assert report_resp.status_code == 200
    assert report_resp.json()["status"] == "completed"


def test_device_auth_required():
    response = client.get("/api/device/poll", params={"device_id": "dev-001"})
    assert response.status_code == 401

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app


SECRET = "change-me-to-a-random-string"
HEADERS = {"X-Device-Secret": SECRET}


POLLING_REPORTING_ENDPOINTS = {
    "/api/device/poll": "app.domains.device_operations.polling.poll_tasks",
    "/api/device/progress": "app.domains.device_operations.reporting.report_progress",
    "/api/device/report": "app.domains.device_operations.reporting.report_result",
    "/api/device/stats/increment": "app.domains.device_operations.reporting.stats_increment",
    "/api/device/heartbeat": "app.domains.device_operations.reporting.heartbeat",
    "/api/device/risk-report": "app.domains.device_operations.reporting.report_risk",
}


def test_polling_and_reporting_routes_are_owned_by_domain_modules():
    assert {
        route.path: f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
        for route in app.routes
        if isinstance(route, APIRoute) and route.path in POLLING_REPORTING_ENDPOINTS
    } == POLLING_REPORTING_ENDPOINTS


def test_poll_no_task_response_shape():
    with TestClient(app) as client:
        response = client.get(
            "/api/device/poll",
            params={"device_id": "device-poll-shape"},
            headers=HEADERS,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["task"] is None
    assert "selectors_version" in data
    assert "prompt_templates_version" in data
    assert "anti_detect_config" in data
    assert "anti_detect_config_version" in data
    assert "device_config" in data
    assert "server_date" in data


def test_progress_stats_report_and_heartbeat_response_shapes(db):
    from app.db_models import Device, Task

    device_id = "device-reporting-shape"
    task_id = "task-reporting-shape"
    device_headers = {"X-Device-Secret": "reporting-shape-secret"}
    db.add(Device(
        id=device_id,
        name="Reporting Shape Phone",
        status="online",
        device_secret="reporting-shape-secret",
    ))
    db.add(Task(
        id=task_id,
        type="nurture",
        account_id="acc-001",
        device_id=device_id,
        params={"duration": 5},
        status="running",
    ))
    db.commit()

    with TestClient(app) as client:
        progress = client.post(
            "/api/device/progress",
            json={"task_id": task_id, "step": "step 1", "detail": "working", "progress": 0.5},
            headers=device_headers,
        )
        stats = client.post(
            "/api/device/stats/increment",
            json={
                "task_id": task_id,
                "account_id": "acc-001",
                "task_type": "nurture",
                "target_id": "target-one",
                "op_index": 1,
                "count": 1,
            },
            headers=device_headers,
        )
        heartbeat = client.post(
            "/api/device/heartbeat",
            json={"device_id": device_id},
            headers=device_headers,
        )
        report = client.post(
            "/api/device/report",
            json={"task_id": task_id, "status": "completed", "result": {"success_count": 1}},
            headers=device_headers,
        )

    assert progress.status_code == 200
    assert progress.json() == {"ok": True}

    assert stats.status_code == 200
    assert stats.json() == {"ok": True}

    assert heartbeat.status_code == 200
    assert heartbeat.json() == {"status": "ok", "device_id": device_id}

    assert report.status_code == 200
    assert report.json()["id"] == task_id
    assert report.json()["status"] == "completed"
    assert report.json()["result"] == {"success_count": 1}


def test_risk_report_unknown_account_response_shape():
    with TestClient(app) as client:
        response = client.post(
            "/api/device/risk-report",
            json={
                "account_id": "missing-risk-account",
                "risk_type": "captcha",
                "detail": {"reason": "shape test"},
            },
            headers=HEADERS,
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ignored", "account_status": "unknown"}

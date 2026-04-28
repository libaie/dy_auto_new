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


class TestGenerateContent:
    """Tests for POST /api/device/generate-content."""

    def test_generate_content_no_template(self):
        """Returns 404 when template doesn't exist."""
        resp = client.post("/api/device/generate-content", json={
            "template_id": "nonexistent",
            "context": {"keyword": "test"},
        }, headers=HEADERS)
        assert resp.status_code == 404

    def test_generate_content_no_api_key(self, db):
        """Returns 503 when AI_API_KEY is not set."""
        from app.services.content_service import content_service
        tpl = content_service.create_template(
            db, name="gen-test", body="关于{keyword}的评论",
            category="comment", variables=["keyword"],
        )
        resp = client.post("/api/device/generate-content", json={
            "template_id": tpl.id,
            "context": {"keyword": "美食"},
        }, headers=HEADERS)
        assert resp.status_code == 503

    def test_generate_content_requires_device_auth(self):
        """Device endpoint requires device secret."""
        resp = client.post("/api/device/generate-content", json={
            "template_id": "any",
            "context": {},
        })
        assert resp.status_code == 401

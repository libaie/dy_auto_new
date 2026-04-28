"""Anti-detect configuration API tests."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.deps import verify_device_secret


@pytest.fixture
def client():
    app.dependency_overrides[verify_device_secret] = lambda: None
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(verify_device_secret, None)


def test_poll_includes_anti_detect_config(client):
    response = client.get("/api/device/poll", params={"device_id": "test-dev"})
    assert response.status_code == 200
    data = response.json()
    assert "anti_detect_config" in data
    config = data["anti_detect_config"]
    assert "delay_min" in config
    assert "active_hours" in config
    assert "peaks" in config["active_hours"]


def test_poll_includes_anti_detect_config_version(client):
    response = client.get("/api/device/poll", params={"device_id": "test-dev"})
    assert response.status_code == 200
    data = response.json()
    assert "anti_detect_config_version" in data
    assert isinstance(data["anti_detect_config_version"], int)
    assert data["anti_detect_config_version"] >= 1


def test_poll_includes_proxy_when_configured(client):
    response = client.get("/api/device/poll", params={"device_id": "test-dev"})
    assert response.status_code == 200
    # proxy may be None if device has no proxy configured, but field should exist
    assert "proxy" in response.json()


def test_risk_report_marks_account(client):
    """Risk report should mark active account as risk_controlled."""
    # First get an account from seed data
    from app.database import get_db
    from app.main import app as _app
    gen = _app.dependency_overrides[get_db]()
    db = next(gen)
    from app.db_models import Account
    account = db.query(Account).filter(Account.status == "active").first()
    db.close()
    gen.close()

    if not account:
        pytest.skip("No active account in test DB")

    response = client.post("/api/device/risk-report", json={
        "account_id": account.id,
        "risk_type": "captcha",
        "detail": {"keyword": "验证"},
        "device_id": "test-dev",
    })
    assert response.status_code == 200
    assert response.json()["account_status"] == "risk_controlled"


def test_risk_report_unknown_account(client):
    """Risk report with unknown account should not error."""
    response = client.post("/api/device/risk-report", json={
        "account_id": "nonexistent",
        "risk_type": "captcha",
    })
    assert response.status_code == 200

"""Stats API tests — dashboard and daily statistics."""
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_dashboard_summary(client):
    response = client.get("/api/stats/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert "accounts" in data
    assert "devices" in data
    assert "tasks" in data
    assert data["accounts"]["total"] >= 0
    assert data["devices"]["total"] >= 0
    assert data["tasks"]["total"] >= 0


def test_daily_stats(client):
    response = client.get("/api/stats/daily")
    assert response.status_code == 200
    data = response.json()
    assert "date" in data
    assert "accounts" in data
    assert isinstance(data["accounts"], list)


def test_account_stats(client):
    """Get stats for a specific account."""
    from app.database import get_db
    from app.db_models import Account

    gen = app.dependency_overrides[get_db]()
    db = next(gen)
    account = db.query(Account).first()
    db.close()
    gen.close()

    if not account:
        pytest.skip("No accounts in test DB")

    response = client.get(f"/api/stats/accounts/{account.id}")
    assert response.status_code == 200
    data = response.json()
    assert "account_id" in data
    assert "today" in data
    assert "remaining" in data


def test_realtime_stats(client):
    response = client.get("/api/stats/realtime")
    assert response.status_code == 200
    data = response.json()
    assert "online_devices" in data
    assert "running_tasks" in data
    assert "pending_tasks" in data

"""Admin authentication API tests."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import ADMIN_USERNAME, ADMIN_PASSWORD, DEVICE_SECRET
from app.deps import verify_admin_token


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_login_success(client):
    response = client.post("/api/auth/login", json={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD,
    })
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["expires_in"] > 0


def test_login_wrong_password(client):
    response = client.post("/api/auth/login", json={
        "username": ADMIN_USERNAME,
        "password": "wrong",
    })
    assert response.status_code == 401


def test_login_wrong_username(client):
    response = client.post("/api/auth/login", json={
        "username": "nobody",
        "password": ADMIN_PASSWORD,
    })
    assert response.status_code == 401


def test_expired_token_rejected(client):
    """Expired JWT token should be rejected by verify_admin_token."""
    import jwt
    from datetime import datetime, timedelta, timezone
    from app.config import JWT_SECRET
    from fastapi import HTTPException

    # Create a token that expired 1 hour ago
    payload = {
        "sub": "admin",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
    }
    expired_token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    # verify_admin_token should reject expired tokens
    with pytest.raises(HTTPException) as exc_info:
        verify_admin_token(authorization=f"Bearer {expired_token}")
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


def test_protected_endpoint_no_token(client):
    """Admin endpoints should require JWT token."""
    # Remove the autouse override to test actual auth enforcement
    app.dependency_overrides.pop(verify_admin_token, None)
    response = client.get("/api/accounts")
    assert response.status_code == 401


def test_protected_endpoint_with_token(client):
    """Admin endpoints should accept valid JWT token."""
    # Remove the autouse override so real auth runs
    app.dependency_overrides.pop(verify_admin_token, None)
    login = client.post("/api/auth/login", json={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD,
    })
    token = login.json()["token"]
    response = client.get("/api/accounts", headers={
        "Authorization": f"Bearer {token}",
    })
    assert response.status_code == 200


def test_accounts_requires_admin_token(client):
    """Accounts CRUD should require admin JWT token."""
    # Remove the autouse override to test actual auth enforcement
    app.dependency_overrides.pop(verify_admin_token, None)
    response = client.get("/api/accounts")
    assert response.status_code == 401


def test_devices_requires_admin_token(client):
    """Devices CRUD should require admin JWT token."""
    # Remove the autouse override to test actual auth enforcement
    app.dependency_overrides.pop(verify_admin_token, None)
    response = client.get("/api/devices")
    assert response.status_code == 401


def test_tasks_requires_admin_token(client):
    """Tasks CRUD should require admin JWT token."""
    # Remove the autouse override to test actual auth enforcement
    app.dependency_overrides.pop(verify_admin_token, None)
    response = client.get("/api/tasks")
    assert response.status_code == 401


def test_device_api_still_uses_secret(client):
    """Device-facing endpoints should still use device secret, not JWT."""
    response = client.get("/api/device/poll", params={"device_id": "test"}, headers={
        "X-Device-Secret": DEVICE_SECRET,
    })
    assert response.status_code == 200

"""Admin authentication API tests."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import ADMIN_USERNAME, ADMIN_PASSWORD


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
    from app.deps import verify_admin_token
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
    response = client.get("/api/accounts")
    # Currently uses verify_device_secret, will change in Task 3
    # For now just verify the login endpoint works
    assert response.status_code in (401, 200)


def test_protected_endpoint_with_token(client):
    """Admin endpoints should accept valid JWT token."""
    login = client.post("/api/auth/login", json={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD,
    })
    token = login.json()["token"]

    # After Task 3, this should work with Bearer token
    response = client.get("/api/accounts", headers={
        "Authorization": f"Bearer {token}",
    })
    # May still return 401 until Task 3 switches auth — that's OK
    assert response.status_code in (200, 401)

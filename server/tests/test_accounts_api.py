"""Account CRUD API tests."""
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db, SessionLocal
from app.db_models import Base, engine

client = TestClient(app)
SECRET = "change-me-to-a-random-string"
HEADERS = {"X-Device-Secret": SECRET}


def setup_module(module):
    """Create tables before tests."""
    Base.metadata.create_all(bind=engine)


def test_create_account():
    resp = client.post("/api/accounts", json={
        "nickname": "测试账号",
        "douyin_id": "test_douyin_001",
        "group": "nurture",
    }, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["nickname"] == "测试账号"
    assert data["douyin_id"] == "test_douyin_001"
    assert data["group"] == "nurture"
    assert data["status"] == "active"
    assert "id" in data


def test_list_accounts():
    resp = client.get("/api/accounts", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "accounts" in data
    assert data["total"] >= 1


def test_get_account():
    # Create one first
    create_resp = client.post("/api/accounts", json={
        "nickname": "查询测试",
        "douyin_id": "test_query",
    }, headers=HEADERS)
    account_id = create_resp.json()["id"]

    resp = client.get(f"/api/accounts/{account_id}", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["id"] == account_id


def test_get_nonexistent_account():
    resp = client.get("/api/accounts/nonexistent-id", headers=HEADERS)
    assert resp.status_code == 404


def test_update_account():
    create_resp = client.post("/api/accounts", json={
        "nickname": "更新前",
        "douyin_id": "test_update",
    }, headers=HEADERS)
    account_id = create_resp.json()["id"]

    resp = client.put(f"/api/accounts/{account_id}", json={
        "nickname": "更新后",
        "status": "risk_controlled",
    }, headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["nickname"] == "更新后"
    assert resp.json()["status"] == "risk_controlled"


def test_delete_account():
    create_resp = client.post("/api/accounts", json={
        "nickname": "删除测试",
        "douyin_id": "test_delete",
    }, headers=HEADERS)
    account_id = create_resp.json()["id"]

    resp = client.delete(f"/api/accounts/{account_id}", headers=HEADERS)
    assert resp.status_code == 200

    # Verify deleted
    resp = client.get(f"/api/accounts/{account_id}", headers=HEADERS)
    assert resp.status_code == 404


def test_auth_required():
    resp = client.get("/api/accounts")
    assert resp.status_code == 401


def test_create_account_missing_nickname():
    resp = client.post("/api/accounts", json={}, headers=HEADERS)
    assert resp.status_code == 422  # Pydantic validation error


def test_update_nonexistent_account():
    resp = client.put("/api/accounts/nonexistent-id", json={"nickname": "x"}, headers=HEADERS)
    assert resp.status_code == 404


def test_delete_nonexistent_account():
    resp = client.delete("/api/accounts/nonexistent-id", headers=HEADERS)
    assert resp.status_code == 404

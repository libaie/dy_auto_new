"""Account CRUD API tests."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
SECRET = "change-me-to-a-random-string"
HEADERS = {"X-Device-Secret": SECRET}


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


def test_delete_account_soft():
    """DELETE sets status='deleted' (soft delete), does not hard-delete."""
    create_resp = client.post("/api/accounts", json={
        "nickname": "软删除测试",
        "douyin_id": "test_soft_delete",
    }, headers=HEADERS)
    account_id = create_resp.json()["id"]

    resp = client.delete(f"/api/accounts/{account_id}", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("deleted") is True

    # Verify still exists but with status='deleted' (requires include_deleted=true)
    get_resp = client.get(f"/api/accounts/{account_id}?include_deleted=true", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "deleted"

    # Default (include_deleted=false) returns 404 for deleted accounts
    get_resp2 = client.get(f"/api/accounts/{account_id}", headers=HEADERS)
    assert get_resp2.status_code == 404


def test_list_accounts_excludes_deleted():
    """LIST should exclude deleted accounts by default."""
    # Create and soft-delete one account
    create_resp = client.post("/api/accounts", json={
        "nickname": "要删除的", "douyin_id": "del_list_test",
    }, headers=HEADERS)
    deleted_id = create_resp.json()["id"]
    client.delete(f"/api/accounts/{deleted_id}", headers=HEADERS)

    # List accounts
    resp = client.get("/api/accounts", headers=HEADERS)
    assert resp.status_code == 200
    accounts = resp.json()["accounts"]
    deleted_ids = [a["id"] for a in accounts if a["id"] == deleted_id]
    assert len(deleted_ids) == 0  # deleted account not in list


def test_delete_account_cancels_pending_tasks():
    """Soft-deleting an account cancels its pending/running tasks."""
    from app.db.models import Task as DBTask

    # Create account
    create_resp = client.post("/api/accounts", json={
        "nickname": "任务取消测试", "douyin_id": "cancel_test",
    }, headers=HEADERS)
    account_id = create_resp.json()["id"]

    # Create some tasks for this account via the service
    from app.domains.task_operations.task_service import task_service
    from app.models import TaskType
    from app.database import get_db as _get_db
    db_gen = app.dependency_overrides[_get_db]()
    db_session = next(db_gen)
    task_service.create_task(db_session, TaskType.SEARCH_LIKE, account_id, {"keyword": "test"})
    task_service.create_task(db_session, TaskType.SEARCH_LIKE, account_id, {"keyword": "test2"})
    db_session.close()

    resp = client.delete(f"/api/accounts/{account_id}", headers=HEADERS)
    assert resp.status_code == 200

    # Verify tasks were cancelled
    db_session2 = next(app.dependency_overrides[_get_db]())
    pending = db_session2.query(DBTask).filter(
        DBTask.account_id == account_id,
        DBTask.status.in_(["pending", "running"]),
    ).all()
    assert len(pending) == 0
    # Tasks should be in terminal state
    cancelled = db_session2.query(DBTask).filter(
        DBTask.account_id == account_id,
        DBTask.status == "cancelled",
    ).all()
    assert len(cancelled) >= 2
    db_session2.close()


def test_delete_account_unbinds_devices():
    """Soft-deleting an account unbinds associated devices."""
    from app.db.models import Device as DBDevice
    from app.database import get_db as _get_db

    # Create account
    create_resp = client.post("/api/accounts", json={
        "nickname": "解绑设备测试", "douyin_id": "unbind_test",
    }, headers=HEADERS)
    account_id = create_resp.json()["id"]

    # Bind a device to this account
    db_gen = app.dependency_overrides[_get_db]()
    db_session = next(db_gen)
    device = DBDevice(id="dev-unbind-test", name="test-device", bound_account_id=account_id)
    db_session.add(device)
    db_session.commit()
    db_session.close()

    resp = client.delete(f"/api/accounts/{account_id}", headers=HEADERS)
    assert resp.status_code == 200

    # Verify device unbound
    db_session2 = next(app.dependency_overrides[_get_db]())
    dev = db_session2.query(DBDevice).filter(DBDevice.id == "dev-unbind-test").first()
    assert dev is not None
    assert dev.bound_account_id is None
    db_session2.close()


def test_auth_required():
    from app.deps import verify_admin_token
    app.dependency_overrides.pop(verify_admin_token, None)
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

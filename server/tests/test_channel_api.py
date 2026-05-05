"""Channel admin API endpoint tests."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.db_models import Account, AccountGroup, AccountGroupMember, Device, Channel, ChannelItem
from tests.conftest import setup_group

client = TestClient(app)


def test_create_channel_api(db):
    setup_group(db, group_id="grp-ch-api-001", account_ids=["acc-ch01-a", "acc-ch01-b"])
    resp = client.post("/api/channels", json={
        "group_id": "grp-ch-api-001",
        "task_type": "search_comment",
        "account_mode": "single_account",
        "account_id": "acc-ch01-a",
        "keywords": ["kw1", "kw2"],
        "params_template": {"content": "hi", "count": 1},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["status"] == "active"


def test_list_channels_api(db):
    setup_group(db, group_id="grp-ch-api-002", account_ids=["acc-ch02-a"])
    client.post("/api/channels", json={
        "group_id": "grp-ch-api-002", "task_type": "search_comment",
        "account_mode": "single_account", "account_id": "acc-ch02-a",
        "keywords": ["a"], "params_template": {},
    })
    resp = client.get("/api/channels")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def test_get_channel_detail_api(db):
    setup_group(db, group_id="grp-ch-api-003", account_ids=["acc-ch03-a"])
    create_resp = client.post("/api/channels", json={
        "group_id": "grp-ch-api-003", "task_type": "search_comment",
        "account_mode": "single_account", "account_id": "acc-ch03-a",
        "keywords": ["detail-kw"], "params_template": {},
    })
    ch_id = create_resp.json()["id"]
    resp = client.get(f"/api/channels/{ch_id}")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1


def test_pause_resume_channel_api(db):
    setup_group(db, group_id="grp-ch-api-004", account_ids=["acc-ch04-a"])
    create_resp = client.post("/api/channels", json={
        "group_id": "grp-ch-api-004", "task_type": "search_comment",
        "account_mode": "single_account", "account_id": "acc-ch04-a",
        "keywords": ["pause-api"], "params_template": {},
    })
    ch_id = create_resp.json()["id"]

    resp = client.patch(f"/api/channels/{ch_id}", json={"status": "paused"})
    assert resp.status_code == 200

    resp = client.patch(f"/api/channels/{ch_id}", json={"status": "active"})
    assert resp.status_code == 200


def test_cancel_channel_api(db):
    setup_group(db, group_id="grp-ch-api-005", account_ids=["acc-ch05-a"])
    create_resp = client.post("/api/channels", json={
        "group_id": "grp-ch-api-005", "task_type": "search_comment",
        "account_mode": "single_account", "account_id": "acc-ch05-a",
        "keywords": ["cancel-api"], "params_template": {},
    })
    ch_id = create_resp.json()["id"]

    resp = client.patch(f"/api/channels/{ch_id}", json={"status": "cancelled"})
    assert resp.status_code == 200


def test_delete_channel_api(db):
    setup_group(db, group_id="grp-ch-api-006", account_ids=["acc-ch06-a"])
    create_resp = client.post("/api/channels", json={
        "group_id": "grp-ch-api-006", "task_type": "search_comment",
        "account_mode": "single_account", "account_id": "acc-ch06-a",
        "keywords": ["delete-api"], "params_template": {},
    })
    ch_id = create_resp.json()["id"]

    resp = client.delete(f"/api/channels/{ch_id}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True

    list_resp = client.get("/api/channels")
    ids = [c["id"] for c in list_resp.json()["channels"]]
    assert ch_id not in ids


def test_append_items_api(db):
    setup_group(db, group_id="grp-ch-api-007", account_ids=["acc-ch07-a"])
    create_resp = client.post("/api/channels", json={
        "group_id": "grp-ch-api-007", "task_type": "search_comment",
        "account_mode": "single_account", "account_id": "acc-ch07-a",
        "keywords": ["orig-api"], "params_template": {},
    })
    ch_id = create_resp.json()["id"]

    resp = client.post(f"/api/channels/{ch_id}/items", json={"keywords": ["new-api"]})
    assert resp.status_code == 200
    assert resp.json()["appended"] == 1


def test_skip_item_api(db):
    setup_group(db, group_id="grp-ch-api-008", account_ids=["acc-ch08-a"])
    create_resp = client.post("/api/channels", json={
        "group_id": "grp-ch-api-008", "task_type": "search_comment",
        "account_mode": "single_account", "account_id": "acc-ch08-a",
        "keywords": ["skip-api"], "params_template": {},
    })
    ch_id = create_resp.json()["id"]

    detail = client.get(f"/api/channels/{ch_id}")
    item_id = detail.json()["items"][0]["id"]

    resp = client.patch(f"/api/channels/{ch_id}/items/{item_id}", json={"status": "skipped"})
    assert resp.status_code == 200


def test_create_channel_validation_error(db):
    """Should return 422 for missing account_id in single_account mode."""
    setup_group(db, group_id="grp-ch-api-009", account_ids=["acc-ch09-a"])
    resp = client.post("/api/channels", json={
        "group_id": "grp-ch-api-009", "task_type": "search_comment",
        "account_mode": "single_account",
        "keywords": ["a"], "params_template": {},
    })
    assert resp.status_code == 422


def test_channel_not_found():
    resp = client.get("/api/channels/nonexistent")
    assert resp.status_code == 404


def test_create_channel_requires_auth(db):
    """Temporarily remove admin auth override to test 401."""
    from app.deps import verify_admin_token
    saved = app.dependency_overrides.pop(verify_admin_token, None)
    try:
        setup_group(db, group_id="grp-ch-api-010", account_ids=["acc-ch10-a"])
        resp = client.post("/api/channels", json={
            "group_id": "grp-ch-api-010", "task_type": "search_comment",
            "account_mode": "single_account", "account_id": "acc-ch10-a",
            "keywords": ["a"], "params_template": {},
        })
        assert resp.status_code == 401
    finally:
        if saved is not None:
            app.dependency_overrides[verify_admin_token] = saved

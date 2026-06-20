"""Channel edit API endpoint tests."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.db.models import Account, AccountGroup, AccountGroupMember, Channel, ChannelItem
from tests.conftest import setup_group

client = TestClient(app)


def _create_channel(db, group_id, account_ids, task_type="search_comment",
                    account_mode="single_account", keywords=None):
    if keywords is None:
        keywords = ["kw1", "kw2", "kw3"]
    setup_group(db, group_id=group_id, account_ids=account_ids)
    resp = client.post("/api/channels", json={
        "group_id": group_id, "task_type": task_type,
        "account_mode": account_mode,
        "account_id": account_ids[0],
        "keywords": keywords, "params_template": {"count": 1},
    })
    assert resp.status_code == 200
    return resp.json()


# ── PUT /api/channels/{id} ──

def test_edit_channel_metadata(db):
    ch = _create_channel(db, group_id="grp-cem-1", account_ids=["cem-1a", "cem-1b"])
    resp = client.put(f"/api/channels/{ch['id']}", json={"cooldown_seconds": 999})
    assert resp.status_code == 200
    assert resp.json()["cooldown_seconds"] == 999


def test_edit_channel_completed_rejected(db):
    ch = _create_channel(db, group_id="grp-cem-2", account_ids=["cem-2a", "cem-2b"])
    client.patch(f"/api/channels/{ch['id']}", json={"status": "cancelled"})
    resp = client.put(f"/api/channels/{ch['id']}", json={"cooldown_seconds": 500})
    assert resp.status_code == 400


def test_edit_channel_invalid_group(db):
    ch = _create_channel(db, group_id="grp-cem-3", account_ids=["cem-3a", "cem-3b"])
    resp = client.put(f"/api/channels/{ch['id']}", json={"group_id": "nonexistent"})
    assert resp.status_code == 400


def test_edit_channel_empty_body(db):
    ch = _create_channel(db, group_id="grp-cem-4", account_ids=["cem-4a", "cem-4b"])
    resp = client.put(f"/api/channels/{ch['id']}", json={})
    assert resp.status_code == 400


def test_edit_channel_account_not_in_group(db):
    ch = _create_channel(db, group_id="grp-cem-5", account_ids=["cem-5a", "cem-5b"])
    setup_group(db, group_id="grp-cem-5-other", account_ids=["cem-5-other"])
    resp = client.put(f"/api/channels/{ch['id']}", json={"account_id": "cem-5-other"})
    assert resp.status_code == 400


def test_edit_channel_sync_to_items(db):
    ch = _create_channel(db, group_id="grp-cem-6", account_ids=["cem-6a", "cem-6b"])
    detail = client.get(f"/api/channels/{ch['id']}").json()
    assert detail["items"][0]["account_id"] == "cem-6a"

    resp = client.put(f"/api/channels/{ch['id']}", json={
        "account_id": "cem-6b", "sync_to_items": True,
    })
    assert resp.status_code == 200

    detail = client.get(f"/api/channels/{ch['id']}").json()
    for item in detail["items"]:
        assert item["account_id"] == "cem-6b"


# ── PUT /api/channels/items/{id} ──

def test_edit_item_keyword(db):
    ch = _create_channel(db, group_id="grp-cei-1", account_ids=["cei-1a", "cei-1b"])
    detail = client.get(f"/api/channels/{ch['id']}").json()
    item_id = detail["items"][0]["id"]

    resp = client.put(f"/api/channels/items/{item_id}", json={"keyword": "new-kw"})
    assert resp.status_code == 200
    assert resp.json()["keyword"] == "new-kw"


def test_edit_item_completed_rejected(db):
    ch = _create_channel(db, group_id="grp-cei-2", account_ids=["cei-2a", "cei-2b"])
    detail = client.get(f"/api/channels/{ch['id']}").json()
    item_id = detail["items"][0]["id"]

    client.patch(f"/api/channels/{ch['id']}/items/{item_id}", json={"status": "skipped"})
    resp = client.put(f"/api/channels/items/{item_id}", json={"keyword": "test"})
    assert resp.status_code == 400


def test_edit_item_account_not_in_group(db):
    ch = _create_channel(db, group_id="grp-cei-3", account_ids=["cei-3a", "cei-3b"])
    detail = client.get(f"/api/channels/{ch['id']}").json()
    item_id = detail["items"][0]["id"]

    setup_group(db, group_id="grp-cei-3-other", account_ids=["cei-3-other"])
    resp = client.put(f"/api/channels/items/{item_id}", json={"account_id": "cei-3-other"})
    assert resp.status_code == 400


def test_edit_item_empty_keyword(db):
    ch = _create_channel(db, group_id="grp-cei-4", account_ids=["cei-4a", "cei-4b"])
    detail = client.get(f"/api/channels/{ch['id']}").json()
    item_id = detail["items"][0]["id"]

    resp = client.put(f"/api/channels/items/{item_id}", json={"keyword": "  "})
    assert resp.status_code == 400


# ── PUT /api/channels/items/batch ──

def test_batch_edit_items(db):
    ch = _create_channel(db, group_id="grp-cbe-1", account_ids=["cbe-1a", "cbe-1b"])
    detail = client.get(f"/api/channels/{ch['id']}").json()
    item_ids = [i["id"] for i in detail["items"]]

    resp = client.put("/api/channels/items/batch", json={
        "item_ids": item_ids, "account_id": "cbe-1b",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["updated"] == 3
    assert len(data["skipped"]) == 0


def test_batch_edit_skips_completed(db):
    ch = _create_channel(db, group_id="grp-cbe-2", account_ids=["cbe-2a", "cbe-2b"])
    detail = client.get(f"/api/channels/{ch['id']}").json()
    first_id = detail["items"][0]["id"]
    rest_ids = [i["id"] for i in detail["items"][1:]]

    client.patch(f"/api/channels/{ch['id']}/items/{first_id}", json={"status": "skipped"})

    resp = client.put("/api/channels/items/batch", json={
        "item_ids": [first_id] + rest_ids, "account_id": detail["items"][0]["account_id"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["updated"] == 2
    assert first_id in data["skipped"]


def test_batch_edit_nonexistent_item(db):
    # Need a valid account to bypass early account-existence check
    ch = _create_channel(db, group_id="grp-cbe-3", account_ids=["cbe-3a", "cbe-3b"])
    resp = client.put("/api/channels/items/batch", json={
        "item_ids": ["fake-id-x"], "account_id": "cbe-3a",
    })
    assert resp.status_code == 200
    assert any("fake-id-x" in e for e in resp.json()["errors"])

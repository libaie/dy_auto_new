"""End-to-end channel flow test via HTTP endpoints."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db_models import Device, Channel
from tests.conftest import setup_group

client = TestClient(app)
DEVICE_HEADERS = {"X-Device-Secret": "change-me-to-a-random-string"}


def test_full_channel_flow(db):
    """Create channel -> device poll claims item -> report result -> channel completes."""
    # Setup: group with accounts and a device
    setup_group(db, group_id="grp-e2e-001", account_ids=["acc-e2e-1"])
    db.add(Device(id="dev-e2e-001", name="e2e-device", status="online"))
    db.flush()

    # 1. Create channel via admin API
    resp = client.post("/api/channels", json={
        "group_id": "grp-e2e-001",
        "task_type": "search_comment",
        "account_mode": "single_account",
        "account_id": "acc-e2e-1",
        "keywords": ["test-keyword"],
        "params_template": {"content": "hello", "count": 1},
    })
    assert resp.status_code == 200
    channel_id = resp.json()["id"]
    assert resp.json()["total"] == 1
    assert resp.json()["status"] == "active"

    # 2. Device poll -- should get the channel task
    resp = client.get("/api/device/poll", params={"device_id": "dev-e2e-001"}, headers=DEVICE_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    task = data.get("task")
    assert task is not None
    assert task["type"] == "search_comment"
    assert task["params"]["keyword"] == "test-keyword"

    # 3. Report task result
    resp = client.post("/api/device/report", json={
        "task_id": task["id"],
        "status": "completed",
        "result": {"success_count": 1},
    }, headers=DEVICE_HEADERS)
    assert resp.status_code == 200

    # 4. Channel should be completed
    resp = client.get(f"/api/channels/{channel_id}")
    assert resp.status_code == 200
    ch_data = resp.json()
    assert ch_data["status"] == "completed"
    assert ch_data["completed"] == 1


def test_multi_keyword_flow(db):
    """Two keywords on single account -- serial execution."""
    setup_group(db, group_id="grp-e2e-002", account_ids=["acc-e2e-2"])
    db.add(Device(id="dev-e2e-002", name="e2e-dev-2", status="online"))
    db.flush()

    # Create channel with 2 keywords
    resp = client.post("/api/channels", json={
        "group_id": "grp-e2e-002",
        "task_type": "search_comment",
        "account_mode": "single_account",
        "account_id": "acc-e2e-2",
        "keywords": ["kw-a", "kw-b"],
        "params_template": {"content": "hi", "count": 1},
    })
    assert resp.status_code == 200
    channel_id = resp.json()["id"]

    # Bypass cooldown constraint (min 30 via API) by writing directly to DB
    ch = db.query(Channel).filter(Channel.id == channel_id).first()
    ch.cooldown_seconds = 0
    db.commit()

    # Poll -> get first task
    resp = client.get("/api/device/poll", params={"device_id": "dev-e2e-002"}, headers=DEVICE_HEADERS)
    task1 = resp.json().get("task")
    assert task1 is not None

    # Report first task
    resp = client.post("/api/device/report", json={
        "task_id": task1["id"], "status": "completed", "result": {"success_count": 1},
    }, headers=DEVICE_HEADERS)
    assert resp.status_code == 200

    # Channel should still be active (1 of 2 done)
    resp = client.get(f"/api/channels/{channel_id}")
    assert resp.json()["status"] == "active"

    # Poll -> get second task
    resp = client.get("/api/device/poll", params={"device_id": "dev-e2e-002"}, headers=DEVICE_HEADERS)
    task2 = resp.json().get("task")
    assert task2 is not None

    # Report second task
    resp = client.post("/api/device/report", json={
        "task_id": task2["id"], "status": "completed", "result": {"success_count": 1},
    }, headers=DEVICE_HEADERS)
    assert resp.status_code == 200

    # Channel should be completed
    resp = client.get(f"/api/channels/{channel_id}")
    assert resp.json()["status"] == "completed"


def test_pause_blocks_poll(db):
    """Paused channel should not return tasks."""
    setup_group(db, group_id="grp-e2e-003", account_ids=["acc-e2e-3"])
    db.add(Device(id="dev-e2e-003", name="e2e-dev-3", status="online"))
    db.flush()

    resp = client.post("/api/channels", json={
        "group_id": "grp-e2e-003",
        "task_type": "search_comment",
        "account_mode": "single_account",
        "account_id": "acc-e2e-3",
        "keywords": ["pause-kw"],
        "params_template": {},
    })
    channel_id = resp.json()["id"]

    # Pause the channel
    resp = client.patch(f"/api/channels/{channel_id}", json={"status": "paused"})
    assert resp.status_code == 200

    # Poll should return empty
    resp = client.get("/api/device/poll", params={"device_id": "dev-e2e-003"}, headers=DEVICE_HEADERS)
    assert resp.json().get("task") is None


def test_delete_channel_hides_from_list(db):
    """Deleted channel should not appear in list."""
    setup_group(db, group_id="grp-e2e-004", account_ids=["acc-e2e-4"])

    resp = client.post("/api/channels", json={
        "group_id": "grp-e2e-004",
        "task_type": "search_comment",
        "account_mode": "single_account",
        "account_id": "acc-e2e-4",
        "keywords": ["del-kw"],
        "params_template": {},
    })
    channel_id = resp.json()["id"]

    # Delete
    resp = client.delete(f"/api/channels/{channel_id}")
    assert resp.status_code == 200

    # List should not contain it
    resp = client.get("/api/channels")
    ids = [c["id"] for c in resp.json()["channels"]]
    assert channel_id not in ids

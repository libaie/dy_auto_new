"""Unknown delivery must not become automatically eligible for another send."""
from datetime import timedelta
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.config import bj_now
from app.db_models import Account, Conversation, Device

client = TestClient(app)


def claimed(db, preserve=True):
    suffix = uuid.uuid4().hex[:10]
    device = Device(id=f"uncertain-{suffix}", name="Uncertain", device_secret=f"uncertain-secret-{suffix}")
    db.add(device)
    db.commit()
    headers = {"X-Device-Secret": device.device_secret}
    body = {"account_id": db.query(Account).first().id, "recipient_douyin_id": suffix, "recipient_nickname": "Test"}
    if preserve:
        body["preserve_on_unknown"] = True
    response = client.post("/api/device/dm-claim-recipient", json=body, headers=headers)
    assert response.status_code == 200
    conversation = db.get(Conversation, response.json()["conversation_id"])
    return headers, body, conversation


def test_unknown_send_hold_survives_orphan_cleanup_without_counting_success(db):
    headers, body, conversation = claimed(db)
    conversation.claimed_at = bj_now() - timedelta(hours=1)
    db.commit()
    response = client.post("/api/device/dm-claim-recipient", json=body, headers=headers)
    assert response.json()["claimed"] is False
    db.refresh(conversation)
    assert conversation.status == "pending_confirmation"
    assert conversation.total_dm_count == 0
    assert conversation.last_dm_at is None


def test_confirmed_send_resolves_hold_and_counts_success(db):
    headers, _, conversation = claimed(db)
    response = client.post("/api/device/dm-send-report", json={"conversation_id": conversation.id, "content": "observed"}, headers=headers)
    assert response.status_code == 200
    db.refresh(conversation)
    assert conversation.status == "active"
    assert conversation.total_dm_count == 1
    assert conversation.claimed_at is None


def test_proven_failure_can_release_an_unconfirmed_hold(db):
    headers, _, conversation = claimed(db)
    response = client.post("/api/device/dm-release-recipient", json={"conversation_id": conversation.id}, headers=headers)
    assert response.status_code == 200
    assert response.json()["released"] is True


def test_legacy_claims_retain_the_existing_orphan_timeout(db):
    headers, body, conversation = claimed(db, preserve=False)
    conversation.claimed_at = bj_now() - timedelta(hours=1)
    db.commit()
    response = client.post("/api/device/dm-claim-recipient", json=body, headers=headers)
    assert response.json()["claimed"] is True

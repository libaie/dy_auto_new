"""Historical results must not be inherited when a physical device ID is reused."""
import base64
from datetime import timedelta
import hashlib
import uuid
from unittest.mock import mock_open, patch

import pytest
from fastapi.testclient import TestClient

from app.config import DEVICE_SECRET, bj_now
from app.db_models import Account, CollectedComment, CollectedUser, Conversation, Device, DevicePairRequest, RepliedComment, Task, User
from app.deps import verify_admin_token
from app.main import app


@pytest.fixture
def history(db):
    owner, other = str(uuid.uuid4()), str(uuid.uuid4())
    ids = {name: str(uuid.uuid4()) for name in ("comment", "lead", "task_lead", "sent", "claim")}
    author, text = "author-" + owner, "comment-" + owner
    digest = hashlib.sha256((author + "|" + text).encode()).hexdigest()
    for identity in (owner, other):
        db.add(User(id=identity, username=identity, password_hash="synthetic", role="operator"))
        db.flush()
        db.add(Account(id=identity, nickname=identity, user_id=identity))
        db.flush()
        db.add(Device(id=identity, name=identity, user_id=identity, bound_account_id=identity, device_secret="synthetic-" + identity))
        db.flush()
        db.add(Task(id=identity, type="collect", account_id=identity, device_id=identity,
                    user_id=identity, status="completed", params={}))
    db.flush()
    db.add(CollectedComment(id=ids["comment"], task_id=owner, device_id=owner,
                           keyword="", nickname=author, content=text))
    db.add(CollectedUser(id=ids["lead"], task_id=None, device_id=owner,
                        nickname="original", douyin_id=ids["lead"]))
    db.add(CollectedUser(id=ids["task_lead"], task_id=owner, device_id=owner,
                        nickname="original", douyin_id=ids["task_lead"]))
    for kind in ("sent", "claim"):
        db.add(Conversation(id=ids[kind], account_id=owner, device_id=owner,
                            recipient_nickname=kind, recipient_douyin_id=ids[kind],
                            status="pending_confirmation", claimed_at=bj_now() - timedelta(hours=1)))
    db.add(RepliedComment(content_hash=digest, author=author, text=text, replied_by_device=owner))
    db.commit()
    saved_override = app.dependency_overrides[verify_admin_token]
    app.dependency_overrides[verify_admin_token] = lambda: (owner, "operator")
    result = {"owner": owner, "other": other, "ids": ids, "author": author, "text": text,
              "hash": digest, "client": TestClient(app), "headers": {"X-Device-Secret": "synthetic-" + owner}}
    try:
        yield result
    finally:
        app.dependency_overrides[verify_admin_token] = saved_override
        db.rollback()
        db.query(RepliedComment).filter_by(content_hash=digest).delete(synchronize_session=False)
        for model in (CollectedComment, CollectedUser, Conversation):
            db.query(model).filter(model.id.in_(ids.values())).delete(synchronize_session=False)
        db.query(DevicePairRequest).filter(DevicePairRequest.device_id.in_([owner, other])).delete(synchronize_session=False)
        for model in (Task, Device, Account, User):
            db.query(model).filter(model.id.in_([owner, other])).delete(synchronize_session=False)
        db.commit()


def reassign_through_pairing(db, history):
    client, old_id = history["client"], history["owner"]
    removed = client.delete("/api/devices/" + old_id)
    assert removed.status_code == 200, removed.text
    paired = client.post("/api/device/pair-request", json={"device_id": old_id, "device_name": "reused"},
                         headers={"X-Forwarded-For": "lifecycle-" + old_id})
    assert paired.status_code == 200, paired.text
    db.expire_all()
    request = db.query(DevicePairRequest).filter_by(device_id=old_id, status="pending").one()
    app.dependency_overrides[verify_admin_token] = lambda: (history["other"], "operator")
    approved = client.post("/api/devices/pair-requests/" + request.id + "/approve")
    assert approved.status_code == 200, approved.text
    db.expire_all()
    device = db.get(Device, old_id)
    assert device.user_id == history["other"]
    return {"X-Device-Secret": device.device_secret}


def submit_report(history, endpoint, headers):
    ids = history["ids"]
    payloads = {
        "comment-ai-reply": {"task_id": history["owner"], "nickname": history["author"], "text": history["text"], "ai_reply": "updated"},
        "dm-send-report": {"conversation_id": ids["sent"], "content": "updated"},
        "dm-release-recipient": {"conversation_id": ids["claim"]},
        "user-profile": {"douyin_id": ids["lead"], "nickname": "updated"},
        "user-avatar": {"douyin_id": ids["lead"], "image_base64": base64.b64encode(b"synthetic image").decode()},
        "comment-claim-release": {"author": history["author"], "text": history["text"]},
    }
    return history["client"].post("/api/device/" + endpoint, json=payloads[endpoint], headers=headers)


def test_device_removal_detaches_history_without_deleting_results_or_unknown_holds(db, history):
    result = history["client"].delete("/api/devices/" + history["owner"])
    assert result.status_code == 200, result.text
    db.expire_all()
    for model, key in ((CollectedComment, "comment"), (CollectedUser, "lead"), (CollectedUser, "task_lead"),
                       (Conversation, "sent"), (Conversation, "claim")):
        record = db.get(model, history["ids"][key])
        assert record is not None, "delete the device, not the historical result"
        assert record.device_id is None, "a reusable hardware ID must not transfer ownership"
    hold = db.get(Conversation, history["ids"]["claim"])
    assert hold.status == "pending_confirmation"
    assert hold.claimed_at is not None
    assert hold.total_dm_count == 0
    assert db.get(RepliedComment, history["hash"]).replied_by_device is None
    assert db.get(Task, history["owner"]).user_id == history["owner"]


@pytest.mark.parametrize("endpoint", ["comment-ai-reply", "dm-send-report", "dm-release-recipient", "user-profile", "user-avatar", "comment-claim-release"])
def test_repaired_device_cannot_write_or_release_the_previous_owners_history(db, history, endpoint):
    headers = reassign_through_pairing(db, history)
    with patch("builtins.open", mock_open()) as writer, patch("os.makedirs"):
        response = submit_report(history, endpoint, headers)
        assert response.status_code in (200, 403), response.text
        writer.assert_not_called()
    db.expire_all()
    assert db.get(CollectedComment, history["ids"]["comment"]).ai_reply is None
    assert db.get(CollectedUser, history["ids"]["lead"]).nickname == "original"
    assert db.get(CollectedUser, history["ids"]["lead"]).avatar_url is None
    assert db.get(Conversation, history["ids"]["sent"]).last_dm_content is None
    assert db.get(Conversation, history["ids"]["claim"]) is not None
    assert db.get(RepliedComment, history["hash"]) is not None


@pytest.mark.parametrize("endpoint", ["comment-ai-reply", "dm-send-report", "dm-release-recipient", "user-profile", "user-avatar", "comment-claim-release"])
def test_current_device_can_still_update_its_own_history(db, history, endpoint):
    with patch("builtins.open", mock_open()) as writer, patch("os.makedirs"):
        response = submit_report(history, endpoint, history["headers"])
        assert response.status_code == 200, response.text
        if endpoint == "user-avatar":
            writer.assert_called_once()
    expected = {"comment-ai-reply": "updated", "dm-send-report": "ok", "dm-release-recipient": "released",
                "user-profile": "saved", "user-avatar": "saved", "comment-claim-release": "released"}
    assert response.json()[expected[endpoint]] is True


@pytest.mark.parametrize("endpoint", ["comment-ai-reply", "dm-send-report", "dm-release-recipient"])
def test_stable_task_or_account_owner_also_protects_preexisting_reused_id_rows(db, history, endpoint):
    # Older server versions left these bindings behind on delete/re-pair. Keep
    # that already reachable persisted state as an upgrade regression fixture.
    device = db.get(Device, history["owner"])
    device.user_id = history["other"]
    db.commit()
    response = submit_report(history, endpoint, history["headers"])
    assert response.status_code in (200, 403), response.text
    db.expire_all()
    assert db.get(CollectedComment, history["ids"]["comment"]).ai_reply is None
    assert db.get(Conversation, history["ids"]["sent"]).last_dm_content is None
    assert db.get(Conversation, history["ids"]["claim"]) is not None


@pytest.mark.parametrize("device_created_later_by_seconds", [0, 1])
def test_taskless_profile_not_newer_than_a_recreated_device_is_not_claimed(db, history, device_created_later_by_seconds):
    device = db.get(Device, history["owner"])
    device.user_id = history["other"]
    device.created_at = db.get(CollectedUser, history["ids"]["lead"]).created_at + timedelta(seconds=device_created_later_by_seconds)
    db.commit()
    response = submit_report(history, "user-profile", history["headers"])
    assert response.status_code == 200, response.text
    assert response.json()["saved"] is False
    db.expire_all()
    assert db.get(CollectedUser, history["ids"]["lead"]).nickname == "original"


def test_legacy_master_can_still_report_and_release_its_own_unassigned_claims(db, history):
    for key in ("sent", "claim"):
        db.get(Conversation, history["ids"][key]).device_id = None
    db.commit()
    headers = {"X-Device-Secret": DEVICE_SECRET}
    sent = submit_report(history, "dm-send-report", headers)
    released = submit_report(history, "dm-release-recipient", headers)
    assert sent.status_code == released.status_code == 200
    assert sent.json()["ok"] is True
    assert released.json()["released"] is True

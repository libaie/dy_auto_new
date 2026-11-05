"""Synthetic end-to-end checks for result attribution and account isolation."""
from datetime import timedelta
import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import bj_now
from app.db_models import Account, CollectedComment, CollectedUser, Conversation, Device, Task, User
from app.deps import verify_admin_token
from app.main import app


@pytest.fixture
def report_route(db):
    entries = {}
    for label in ("owner", "other"):
        tag = str(uuid.uuid4())
        user = User(id=tag, username=tag, password_hash="synthetic", role="operator")
        account = Account(id=tag, nickname=label, user_id=tag)
        device = Device(id=tag, name=label, device_secret=tag, user_id=tag, bound_account_id=tag)
        task = Task(id=tag, account_id=tag, device_id=tag, user_id=tag,
                    type="collect", status="running", params={})
        db.add(user)
        db.flush()
        db.add(account)
        db.flush()
        db.add(device)
        db.flush()
        db.add(task)
        entries[label] = {"id": tag, "headers": {"X-Device-Secret": tag}}
    db.commit()
    entries["client"] = TestClient(app)
    try:
        yield entries
    finally:
        db.rollback()
        ids = [entries[label]["id"] for label in ("owner", "other")]
        for model, field in ((CollectedComment, "device_id"), (CollectedUser, "device_id"), (Conversation, "account_id"),
                             (Task, "id"), (Device, "id"), (Account, "id"), (User, "id")):
            db.query(model).filter(getattr(model, field).in_(ids)).delete(synchronize_session=False)
        db.commit()


@pytest.mark.parametrize("endpoint", ["risk-report", "dm-claim-recipient"])
def test_account_report_cannot_mutate_another_owners_account(db, report_route, endpoint):
    owner, other = report_route["owner"], report_route["other"]
    payload = {"account_id": other["id"], "risk_type": "captcha"} if endpoint == "risk-report" else {
        "account_id": other["id"], "recipient_douyin_id": "synthetic", "recipient_nickname": "test",
    }
    response = report_route["client"].post("/api/device/" + endpoint, json=payload, headers=owner["headers"])
    assert response.status_code == 403, response.text
    db.expire_all()
    assert db.get(Account, other["id"]).status == "active"
    assert db.query(Conversation).filter_by(account_id=other["id"]).count() == 0


def test_dm_claim_does_not_cleanup_another_accounts_orphans(db, report_route):
    owner, other = report_route["owner"], report_route["other"]
    orphan = Conversation(account_id=other["id"], device_id=other["id"],
                          recipient_nickname="orphan", recipient_douyin_id="old",
                          status="active", claimed_at=bj_now() - timedelta(hours=1))
    db.add(orphan)
    db.commit()
    orphan_id = orphan.id
    response = report_route["client"].post("/api/device/dm-claim-recipient", json={
        "account_id": owner["id"], "recipient_douyin_id": "new", "recipient_nickname": "test",
    }, headers=owner["headers"])
    assert response.status_code == 200, response.text
    assert response.json()["claimed"] is True
    db.expire_all()
    assert db.get(Conversation, orphan_id) is not None


@pytest.mark.parametrize("target", ["owner", "other"])
def test_collection_report_uses_the_calling_devices_task(db, report_route, target):
    response = report_route["client"].post("/api/device/collect-report", json={
        "task_id": report_route[target]["id"], "keyword": "",
        "comment": {"nickname": "synthetic", "content": "test"},
    }, headers=report_route["owner"]["headers"])
    assert response.status_code == (200 if target == "owner" else 403), response.text
    assert db.query(CollectedComment).filter_by(task_id=report_route[target]["id"]).count() == (1 if target == "owner" else 0)


@pytest.mark.parametrize("target", ["owner", "other"])
def test_comment_reply_update_remains_on_the_collecting_device(db, report_route, target):
    comment = CollectedComment(task_id=report_route[target]["id"], device_id=report_route[target]["id"],
                               keyword="", nickname="synthetic", content="same text")
    db.add(comment)
    db.commit()
    response = report_route["client"].post("/api/device/comment-ai-reply", json={
        "nickname": "synthetic", "text": "same text", "ai_reply": "generated",
    }, headers=report_route["owner"]["headers"])
    assert response.status_code == 200, response.text
    assert response.json()["updated"] is (target == "owner")
    db.refresh(comment)
    assert comment.ai_reply == ("generated" if target == "owner" else None)


@pytest.mark.parametrize("export", [False, True])
def test_claimed_conversations_are_visible_to_the_account_owner_without_a_task_fk(db, report_route, export):
    for label in ("owner", "other"):
        entry = report_route[label]
        db.add(Conversation(account_id=entry["id"], device_id=entry["id"], task_id=None,
                            recipient_nickname=label, recipient_douyin_id=entry["id"]))
    db.commit()
    saved = app.dependency_overrides[verify_admin_token]
    app.dependency_overrides[verify_admin_token] = lambda: (report_route["owner"]["id"], "operator")
    try:
        response = report_route["client"].get("/api/data/export/conversations" if export else "/api/data/conversations")
        assert response.status_code == 200, response.text
        if export:
            import io
            from openpyxl import load_workbook
            rows = list(load_workbook(io.BytesIO(response.content), read_only=True).active.values)
            assert len(rows) == 2
            assert "owner" in rows[1]
            assert "other" not in rows[1]
        else:
            assert response.json()["total"] == 1
            assert response.json()["items"][0]["account_id"] == report_route["owner"]["id"]
    finally:
        app.dependency_overrides[verify_admin_token] = saved


@pytest.mark.parametrize("douyin_id", ["../synthetic-avatar", "folder\\synthetic-avatar", "C:synthetic-avatar"])
def test_avatar_upload_rejects_path_components_before_touching_files(db, report_route, douyin_id):
    import base64
    from unittest.mock import mock_open, patch

    db.add(CollectedUser(task_id=report_route["owner"]["id"], device_id=report_route["owner"]["id"],
                         nickname="synthetic", douyin_id=douyin_id))
    db.commit()
    # Replace only the filesystem boundary. No test writes outside a temporary fixture.
    with patch("builtins.open", mock_open()) as writer, patch("os.makedirs"):
        response = report_route["client"].post("/api/device/user-avatar", json={
            "douyin_id": douyin_id, "image_base64": base64.b64encode(b"synthetic image").decode(),
        }, headers=report_route["owner"]["headers"])
        assert response.status_code == 400, response.text
        writer.assert_not_called()


@pytest.mark.parametrize("endpoint", ["collect-report", "user-profile", "user-avatar"])
@pytest.mark.parametrize("record_owner", ["owner", "other"])
def test_duplicate_profile_updates_cannot_move_or_modify_another_owners_lead(db, report_route, endpoint, record_owner):
    import base64
    from unittest.mock import mock_open, patch

    target = report_route[record_owner]["id"]
    douyin_id = uuid.uuid4().hex
    existing = CollectedUser(task_id=target, device_id=target, nickname="original", douyin_id=douyin_id)
    db.add(existing)
    db.commit()
    payload = {"task_id": report_route["owner"]["id"], "douyin_id": douyin_id, "nickname": "updated"}
    if endpoint == "collect-report":
        payload = {"task_id": report_route["owner"]["id"], "keyword": "",
                   "comment": {"nickname": "test", "content": "test"},
                   "user": {"douyin_id": douyin_id, "nickname": "updated"}}
    elif endpoint == "user-avatar":
        payload = {"douyin_id": douyin_id, "image_base64": base64.b64encode(b"synthetic image").decode()}
    with patch("builtins.open", mock_open()) as writer, patch("os.makedirs"):
        response = report_route["client"].post("/api/device/" + endpoint, json=payload,
                                               headers=report_route["owner"]["headers"])
        if record_owner == "other":
            if endpoint == "user-avatar":
                assert response.status_code == 403, response.text
            elif endpoint == "user-profile":
                assert response.status_code == 200, response.text
                assert response.json()["saved"] is False
                assert "user_id" not in response.json()
            else:
                assert response.status_code == 200, response.text
                assert response.json().get("user_conflict") is True
            writer.assert_not_called()
        else:
            assert response.status_code == 200, response.text
            if endpoint != "collect-report":
                assert response.json()["saved"] is True
    db.refresh(existing)
    assert existing.task_id == target
    assert existing.device_id == target
    if record_owner == "other":
        assert existing.nickname == "original"
        assert existing.avatar_url is None

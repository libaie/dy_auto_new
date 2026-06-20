from unittest.mock import AsyncMock, patch

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app


SECRET = "change-me-to-a-random-string"
HEADERS = {"X-Device-Secret": SECRET}


CONTENT_BRIDGE_ENDPOINTS = {
    "/api/device/comment-claim-reply": "app.domains.device_operations.content_bridge.claim_comment_reply",
    "/api/device/comment-claim-release": "app.domains.device_operations.content_bridge.release_comment_claim",
    "/api/device/generate-content": "app.domains.device_operations.content_bridge.generate_content",
    "/api/device/ai-proxy": "app.domains.device_operations.content_bridge.ai_proxy",
    "/api/device/collect-report": "app.domains.device_operations.content_bridge.collect_report",
    "/api/device/dm-claim-recipient": "app.domains.device_operations.content_bridge.dm_claim_recipient",
    "/api/device/dm-send-report": "app.domains.device_operations.content_bridge.dm_send_report",
    "/api/device/dm-release-recipient": "app.domains.device_operations.content_bridge.dm_release_recipient",
    "/api/device/comment-ai-reply": "app.domains.device_operations.content_bridge.save_comment_ai_reply",
    "/api/device/user-profile": "app.domains.device_operations.content_bridge.save_user_profile",
    "/api/device/user-avatar": "app.domains.device_operations.content_bridge.upload_user_avatar",
    "/api/device/avatar/{douyin_id}": "app.domains.device_operations.content_bridge.get_user_avatar",
}


def test_content_bridge_routes_are_owned_by_domain_module():
    assert {
        route.path: f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
        for route in app.routes
        if isinstance(route, APIRoute) and route.path in CONTENT_BRIDGE_ENDPOINTS
    } == CONTENT_BRIDGE_ENDPOINTS


def test_comment_claim_and_release_response_shapes():
    payload = {"author": "author-one", "text": "useful comment"}

    with TestClient(app) as client:
        claim = client.post("/api/device/comment-claim-reply", json=payload, headers=HEADERS)
        duplicate_claim = client.post("/api/device/comment-claim-reply", json=payload, headers=HEADERS)
        release = client.post("/api/device/comment-claim-release", json=payload, headers=HEADERS)

    assert claim.status_code == 200
    assert set(claim.json()) == {"claimed", "hash"}
    assert claim.json()["claimed"] is True

    assert duplicate_claim.status_code == 200
    assert duplicate_claim.json()["claimed"] is False
    assert duplicate_claim.json()["hash"] == claim.json()["hash"]

    assert release.status_code == 200
    assert release.json() == {"released": True}


def test_generate_content_bridge_response_shape(db):
    from app.services.content_service import content_service

    template = content_service.create_template(
        db,
        name="device-bridge-template",
        body="Reply about {keyword}",
        category="comment",
        variables=["keyword"],
    )

    with patch(
        "app.services.content_service.ContentService.generate_from_template",
        new_callable=AsyncMock,
        return_value="Generated reply",
    ):
        with TestClient(app) as client:
            response = client.post(
                "/api/device/generate-content",
                json={"template_id": template.id, "context": {"keyword": "tea"}},
                headers=HEADERS,
            )

    assert response.status_code == 200
    assert response.json() == {"content": "Generated reply", "template_id": template.id}


def test_collect_report_bridge_response_shape():
    payload = {
        "task_id": "collect-shape-task",
        "keyword": "tea shop",
        "comment": {
            "nickname": "comment-author",
            "content": "I want a quiet place",
            "time_str": "2026-06-20T12:00:00",
        },
        "user": {
            "nickname": "comment-author",
            "douyin_id": "bridge-user-one",
            "fans_count": "12",
        },
    }

    with TestClient(app) as client:
        response = client.post("/api/device/collect-report", json=payload, headers=HEADERS)

    assert response.status_code == 200
    assert set(response.json()) == {"comment_saved", "user_new"}
    assert response.json()["comment_saved"] is True
    assert response.json()["user_new"] is True


def test_dm_bridge_claim_release_and_send_response_shapes():
    with TestClient(app) as client:
        claim = client.post(
            "/api/device/dm-claim-recipient",
            json={
                "account_id": "acc-001",
                "recipient_douyin_id": "dm-recipient-release",
                "recipient_nickname": "Release Recipient",
            },
            headers=HEADERS,
        )
        release = client.post(
            "/api/device/dm-release-recipient",
            json={"conversation_id": claim.json()["conversation_id"]},
            headers=HEADERS,
        )
        send_claim = client.post(
            "/api/device/dm-claim-recipient",
            json={
                "account_id": "acc-001",
                "recipient_douyin_id": "dm-recipient-send",
                "recipient_nickname": "Send Recipient",
            },
            headers=HEADERS,
        )
        send_report = client.post(
            "/api/device/dm-send-report",
            json={
                "conversation_id": send_claim.json()["conversation_id"],
                "stage": "qualifying",
                "intent": "interested",
                "keyword": "tea",
                "content": "Hello from the device",
            },
            headers=HEADERS,
        )

    assert claim.status_code == 200
    assert set(claim.json()) == {"claimed", "conversation_id"}
    assert claim.json()["claimed"] is True

    assert release.status_code == 200
    assert release.json() == {"released": True}

    assert send_claim.status_code == 200
    assert send_claim.json()["claimed"] is True

    assert send_report.status_code == 200
    assert send_report.json() == {"ok": True}


def test_dm_send_report_records_idempotent_message_ledger(db):
    from app.db_models import Task

    db.add(Task(
        id="dm-ledger-task",
        type="reply_comment",
        account_id="acc-001",
        device_id=None,
        status="running",
        params={},
    ))
    db.commit()

    with TestClient(app) as client:
        claim = client.post(
            "/api/device/dm-claim-recipient",
            json={
                "account_id": "acc-001",
                "recipient_douyin_id": "dm-ledger-recipient",
                "recipient_nickname": "Ledger Recipient",
            },
            headers=HEADERS,
        )
        payload = {
            "conversation_id": claim.json()["conversation_id"],
            "task_id": "dm-ledger-task",
            "stage": "qualifying",
            "intent": "interested",
            "keyword": "tea",
            "content": "First message",
            "dm_sequence_id": "sequence-one",
            "message_order": 1,
            "message_key": "conversation-one:sequence-one:1",
            "status": "sent",
        }

        first = client.post("/api/device/dm-send-report", json=payload, headers=HEADERS)
        duplicate = client.post("/api/device/dm-send-report", json=payload, headers=HEADERS)
        late_failed_payload = {**payload, "status": "failed", "error_message": "late failure"}
        late_failed = client.post("/api/device/dm-send-report", json=late_failed_payload, headers=HEADERS)

    from app.db_models import Conversation, ConversationMessage

    assert first.status_code == 200
    assert duplicate.status_code == 200
    assert late_failed.status_code == 200
    messages = db.query(ConversationMessage).filter_by(conversation_id=payload["conversation_id"]).all()
    assert len(messages) == 1
    assert messages[0].content == "First message"
    assert messages[0].message_order == 1
    assert messages[0].message_key == "conversation-one:sequence-one:1"
    assert messages[0].status == "sent"

    conversation = db.query(Conversation).filter_by(id=payload["conversation_id"]).one()
    assert conversation.task_id == "dm-ledger-task"
    assert conversation.total_dm_count == 1
    assert conversation.last_dm_content == "First message"


def test_dm_send_report_dedupes_legacy_payload_retries(db):
    with TestClient(app) as client:
        claim = client.post(
            "/api/device/dm-claim-recipient",
            json={
                "account_id": "acc-001",
                "recipient_douyin_id": "dm-legacy-retry-recipient",
                "recipient_nickname": "Legacy Retry Recipient",
            },
            headers=HEADERS,
        )
        payload = {
            "conversation_id": claim.json()["conversation_id"],
            "stage": "qualifying",
            "intent": "interested",
            "keyword": "tea",
            "content": "Legacy single message",
        }
        first = client.post("/api/device/dm-send-report", json=payload, headers=HEADERS)
        retry = client.post("/api/device/dm-send-report", json=payload, headers=HEADERS)

    from app.db_models import Conversation, ConversationMessage

    assert first.status_code == 200
    assert retry.status_code == 200
    messages = db.query(ConversationMessage).filter_by(conversation_id=payload["conversation_id"]).all()
    assert len(messages) == 1
    assert messages[0].message_key.startswith("legacy:")
    conversation = db.query(Conversation).filter_by(id=payload["conversation_id"]).one()
    assert conversation.total_dm_count == 1


def test_dm_send_report_rejects_task_from_other_account(db):
    from app.db_models import Task

    db.add(Task(
        id="wrong-account-task",
        type="reply_comment",
        account_id="acc-002",
        device_id=None,
        status="running",
        params={},
    ))
    db.commit()

    with TestClient(app) as client:
        claim = client.post(
            "/api/device/dm-claim-recipient",
            json={
                "account_id": "acc-001",
                "recipient_douyin_id": "dm-wrong-task-recipient",
                "recipient_nickname": "Wrong Task Recipient",
            },
            headers=HEADERS,
        )
        response = client.post(
            "/api/device/dm-send-report",
            json={
                "conversation_id": claim.json()["conversation_id"],
                "task_id": "wrong-account-task",
                "stage": "qualifying",
                "intent": "interested",
                "keyword": "tea",
                "content": "Wrong task message",
                "message_order": 1,
                "message_key": "wrong-account-task:single:1",
                "status": "sent",
            },
            headers=HEADERS,
        )

    assert response.status_code == 403
def test_dm_claim_reuses_failed_only_conversation_for_retry(db):
    from app.db_models import Task

    db.add(Task(
        id="retry-task",
        type="search_dm",
        account_id="acc-001",
        device_id=None,
        status="running",
        params={},
    ))
    db.commit()

    with TestClient(app) as client:
        first_claim = client.post(
            "/api/device/dm-claim-recipient",
            json={
                "account_id": "acc-001",
                "recipient_douyin_id": "dm-failed-retry-recipient",
                "recipient_nickname": "Failed Retry Recipient",
            },
            headers=HEADERS,
        )
        failed = client.post(
            "/api/device/dm-send-report",
            json={
                "conversation_id": first_claim.json()["conversation_id"],
                "task_id": "retry-task",
                "stage": "qualifying",
                "intent": "search_dm",
                "keyword": "tea",
                "content": "Could not send",
                "dm_sequence_id": "seq-retry",
                "message_order": 1,
                "message_key": "retry-task:seq-retry:1",
                "status": "failed",
                "error_message": "发送按钮未找到",
            },
            headers=HEADERS,
        )
        retry_claim = client.post(
            "/api/device/dm-claim-recipient",
            json={
                "account_id": "acc-001",
                "recipient_douyin_id": "dm-failed-retry-recipient",
                "recipient_nickname": "Failed Retry Recipient",
            },
            headers=HEADERS,
        )
        success = client.post(
            "/api/device/dm-send-report",
            json={
                "conversation_id": retry_claim.json()["conversation_id"],
                "task_id": "retry-task",
                "stage": "qualifying",
                "intent": "search_dm",
                "keyword": "tea",
                "content": "Retried successfully",
                "dm_sequence_id": "seq-retry",
                "message_order": 1,
                "message_key": "retry-task:seq-retry:1",
                "status": "sent",
            },
            headers=HEADERS,
        )

    from app.db_models import Conversation, ConversationMessage

    assert first_claim.status_code == 200
    assert first_claim.json()["claimed"] is True
    assert failed.status_code == 200
    assert retry_claim.status_code == 200
    assert retry_claim.json() == {"claimed": True, "conversation_id": first_claim.json()["conversation_id"]}
    assert success.status_code == 200
    messages = db.query(ConversationMessage).filter_by(conversation_id=first_claim.json()["conversation_id"]).all()
    assert len(messages) == 1
    assert messages[0].status == "sent"
    assert messages[0].content == "Retried successfully"
    conversation = db.query(Conversation).filter_by(id=first_claim.json()["conversation_id"]).one()
    assert conversation.total_dm_count == 1
def test_user_profile_and_avatar_bridge_response_shapes():
    with TestClient(app) as client:
        profile = client.post(
            "/api/device/user-profile",
            json={
                "nickname": "Profile User",
                "douyin_id": "profile-user-one",
                "fans_count": "20",
                "keyword": "tea",
            },
            headers=HEADERS,
        )
        avatar = client.post(
            "/api/device/user-avatar",
            json={"douyin_id": "profile-user-one", "image_base64": "not-base64"},
            headers=HEADERS,
        )

    assert profile.status_code == 200
    assert set(profile.json()) == {"saved", "updated", "user_id"}
    assert profile.json()["saved"] is True
    assert profile.json()["updated"] is False

    assert avatar.status_code == 200
    assert avatar.json() == {"saved": False, "reason": "invalid base64"}

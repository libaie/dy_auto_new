from unittest.mock import AsyncMock, patch

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app


SECRET = "change-me-to-a-random-string"
HEADERS = {"X-Device-Secret": SECRET}


DEVICE_BRIDGE_ENDPOINTS = {
    "/api/device/generate-content": "app.domains.device_operations.content_bridge.generate_content",
    "/api/device/collect-report": "app.domains.device_operations.content_bridge.collect_report",
    "/api/device/dm-claim-recipient": "app.domains.device_operations.content_bridge.dm_claim_recipient",
    "/api/device/dm-send-report": "app.domains.device_operations.content_bridge.dm_send_report",
    "/api/device/dm-release-recipient": "app.domains.device_operations.content_bridge.dm_release_recipient",
    "/api/device/comment-ai-reply": "app.domains.device_operations.content_bridge.save_comment_ai_reply",
    "/api/device/user-profile": "app.domains.device_operations.content_bridge.save_user_profile",
    "/api/device/user-avatar": "app.domains.device_operations.content_bridge.upload_user_avatar",
}


def test_device_bridge_routes_stay_in_device_operations_during_pr1():
    assert {
        route.path: f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
        for route in app.routes
        if isinstance(route, APIRoute) and route.path in DEVICE_BRIDGE_ENDPOINTS
    } == DEVICE_BRIDGE_ENDPOINTS


def test_device_bridge_handoff_use_case_modules_exist():
    import app.domains.content_collection.collection_reports as collection_reports
    import app.domains.content_collection.content_generation as content_generation
    import app.domains.content_collection.dm_claims as dm_claims

    for name in (
        "collect_report",
        "save_comment_ai_reply",
        "save_user_profile",
        "upload_user_avatar",
    ):
        assert hasattr(collection_reports, name)

    assert hasattr(content_generation, "generate_from_template")

    for name in ("claim_recipient", "send_report", "release_recipient"):
        assert hasattr(dm_claims, name)


def test_device_generate_content_bridge_response_shape(db):
    from app.services.content_service import content_service

    template = content_service.create_template(
        db,
        name="content-collection-device-template",
        body="Reply about {keyword}",
        category="comment",
        variables=["keyword"],
    )

    with patch(
        "app.services.content_service.ContentService.generate_from_template",
        new_callable=AsyncMock,
        return_value="Generated bridge reply",
    ):
        with TestClient(app) as client:
            response = client.post(
                "/api/device/generate-content",
                json={"template_id": template.id, "context": {"keyword": "coffee"}},
                headers=HEADERS,
            )

    assert response.status_code == 200
    assert response.json() == {"content": "Generated bridge reply", "template_id": template.id}


def test_device_collection_and_comment_reply_bridge_response_shapes():
    collect_payload = {
        "task_id": "content-collection-bridge-task",
        "keyword": "coffee",
        "comment": {
            "nickname": "Bridge Commenter",
            "content": "Looking for a quiet cafe",
            "time_str": "2026-06-20T13:00:00",
        },
        "user": {
            "nickname": "Bridge Commenter",
            "douyin_id": "content-collection-bridge-user",
        },
    }

    with TestClient(app) as client:
        collect = client.post("/api/device/collect-report", json=collect_payload, headers=HEADERS)
        ai_reply = client.post(
            "/api/device/comment-ai-reply",
            json={
                "nickname": "Bridge Commenter",
                "text": "Looking for a quiet cafe",
                "ai_reply": "Try the riverside cafe.",
                "task_id": "content-collection-bridge-task",
            },
            headers=HEADERS,
        )

    assert collect.status_code == 200
    assert collect.json() == {"comment_saved": True, "user_new": True}

    assert ai_reply.status_code == 200
    assert ai_reply.json() == {"updated": True}


def test_device_dm_bridge_response_shapes():
    with TestClient(app) as client:
        claim = client.post(
            "/api/device/dm-claim-recipient",
            json={
                "account_id": "acc-001",
                "recipient_douyin_id": "content-collection-dm-send",
                "recipient_nickname": "DM Recipient",
            },
            headers=HEADERS,
        )
        send = client.post(
            "/api/device/dm-send-report",
            json={
                "conversation_id": claim.json()["conversation_id"],
                "stage": "qualifying",
                "intent": "interested",
                "keyword": "coffee",
                "content": "Hello from content collection bridge",
            },
            headers=HEADERS,
        )
        release_claim = client.post(
            "/api/device/dm-claim-recipient",
            json={
                "account_id": "acc-001",
                "recipient_douyin_id": "content-collection-dm-release",
                "recipient_nickname": "DM Release Recipient",
            },
            headers=HEADERS,
        )
        release = client.post(
            "/api/device/dm-release-recipient",
            json={"conversation_id": release_claim.json()["conversation_id"]},
            headers=HEADERS,
        )

    assert claim.status_code == 200
    assert set(claim.json()) == {"claimed", "conversation_id"}
    assert claim.json()["claimed"] is True

    assert send.status_code == 200
    assert send.json() == {"ok": True}

    assert release.status_code == 200
    assert release.json() == {"released": True}


def test_device_user_profile_and_avatar_bridge_response_shapes():
    with TestClient(app) as client:
        profile = client.post(
            "/api/device/user-profile",
            json={
                "nickname": "Avatar User",
                "douyin_id": "content-collection-avatar-user",
                "keyword": "coffee",
            },
            headers=HEADERS,
        )
        avatar = client.post(
            "/api/device/user-avatar",
            json={"douyin_id": "content-collection-avatar-user", "image_base64": "not-base64"},
            headers=HEADERS,
        )

    assert profile.status_code == 200
    assert set(profile.json()) == {"saved", "updated", "user_id"}
    assert profile.json()["saved"] is True

    assert avatar.status_code == 200
    assert avatar.json() == {"saved": False, "reason": "invalid base64"}

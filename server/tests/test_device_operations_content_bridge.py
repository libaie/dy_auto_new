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

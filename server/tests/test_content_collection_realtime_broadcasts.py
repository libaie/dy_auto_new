from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app


SECRET = "change-me-to-a-random-string"
HEADERS = {"X-Device-Secret": SECRET}


def test_content_template_mutation_broadcasts_content_changed():
    with patch("app.routers.content.pair_ws_manager.broadcast_to_admins", new_callable=AsyncMock) as broadcast:
        with TestClient(app) as client:
            response = client.post(
                "/api/content/templates",
                json={
                    "name": "broadcast-template",
                    "category": "comment",
                    "body": "Reply about {keyword}",
                    "variables": ["keyword"],
                },
            )

    assert response.status_code == 200
    broadcast.assert_awaited_once_with({"event": "content_changed"})


def test_sensitive_word_mutation_broadcasts_content_changed():
    with patch("app.routers.content.pair_ws_manager.broadcast_to_admins", new_callable=AsyncMock) as broadcast:
        with TestClient(app) as client:
            response = client.post(
                "/api/content/sensitive-words",
                json={"word": "broadcast-sensitive-word"},
            )

    assert response.status_code == 200
    broadcast.assert_awaited_once_with({"event": "content_changed"})


def test_collect_report_broadcasts_comment_and_user_data_changed_events():
    with patch(
        "app.domains.device_operations.content_bridge.pair_ws_manager.broadcast_to_admins",
        new_callable=AsyncMock,
    ) as broadcast:
        with TestClient(app) as client:
            response = client.post(
                "/api/device/collect-report",
                json={
                    "task_id": "content-collection-broadcast-task",
                    "keyword": "coffee",
                    "comment": {
                        "nickname": "Broadcast Commenter",
                        "content": "Looking for a quiet cafe",
                        "time_str": "2026-06-20T14:00:00",
                    },
                    "user": {
                        "nickname": "Broadcast Commenter",
                        "douyin_id": "content-collection-broadcast-user",
                    },
                },
                headers=HEADERS,
            )

    assert response.status_code == 200
    payloads = [call.args[0] for call in broadcast.await_args_list]
    assert payloads[0]["event"] == "data_changed"
    assert payloads[0]["type"] == "comment"
    assert "id" in payloads[0]
    assert payloads[1] == {
        "event": "data_changed",
        "type": "user",
        "id": "content-collection-broadcast-user",
    }


def test_dm_send_report_broadcasts_conversation_data_changed_event():
    with patch(
        "app.domains.device_operations.content_bridge.pair_ws_manager.broadcast_to_admins",
        new_callable=AsyncMock,
    ) as broadcast:
        with TestClient(app) as client:
            claim = client.post(
                "/api/device/dm-claim-recipient",
                json={
                    "account_id": "acc-001",
                    "recipient_douyin_id": "content-collection-broadcast-dm",
                    "recipient_nickname": "Broadcast DM Recipient",
                },
                headers=HEADERS,
            )
            response = client.post(
                "/api/device/dm-send-report",
                json={
                    "conversation_id": claim.json()["conversation_id"],
                    "stage": "qualifying",
                    "intent": "interested",
                    "keyword": "coffee",
                    "content": "Hello from realtime characterization",
                },
                headers=HEADERS,
            )

    assert response.status_code == 200
    payloads = [call.args[0] for call in broadcast.await_args_list]
    assert payloads == [
        {
            "event": "data_changed",
            "type": "conversation",
            "id": claim.json()["conversation_id"],
        }
    ]

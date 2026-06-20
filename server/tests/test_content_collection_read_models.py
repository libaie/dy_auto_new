from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app


READ_MODEL_ENDPOINTS = {
    "/api/data/comments": "app.domains.content_collection.data_router.list_comments",
    "/api/data/users": "app.domains.content_collection.data_router.list_users",
    "/api/data/conversations": "app.domains.content_collection.data_router.list_conversations",
    "/api/data/conversations/{conversation_id}": "app.domains.content_collection.data_router.get_conversation",
    "/api/data/export/comments": "app.domains.content_collection.data_router.export_comments",
    "/api/data/export/users": "app.domains.content_collection.data_router.export_users",
    "/api/data/export/conversations": "app.domains.content_collection.data_router.export_conversations",
}


def test_data_routes_delegate_through_domain_router():
    assert {
        route.path: f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
        for route in app.routes
        if isinstance(route, APIRoute) and route.path in READ_MODEL_ENDPOINTS
    } == READ_MODEL_ENDPOINTS


def test_read_model_module_owns_payload_functions():
    import app.domains.content_collection.read_models as read_models

    for name in (
        "list_comments",
        "list_users",
        "list_conversations",
        "get_conversation",
        "export_comments",
        "export_users",
        "export_conversations",
    ):
        assert hasattr(read_models, name)


def test_comment_user_and_conversation_read_model_response_shapes(db):
    from app.db.models import CollectedComment, CollectedUser, Conversation, ConversationMessage

    db.add(CollectedComment(
        task_id="read-model-task",
        device_id="read-model-device",
        keyword="coffee",
        nickname="Read Commenter",
        content="Quiet cafe please",
        time_str="2026-06-20T15:00:00",
    ))
    db.add(CollectedUser(
        task_id="read-model-task",
        device_id="read-model-device",
        keyword="coffee",
        nickname="Read User",
        douyin_id="read-model-user",
        source_comment_content="Quiet cafe please",
    ))
    db.add(Conversation(
        account_id="acc-001",
        device_id="read-model-device",
        recipient_nickname="Read Recipient",
        recipient_douyin_id="read-model-recipient",
        last_dm_content="Hello",
    ))
    db.commit()

    with TestClient(app) as client:
        comments = client.get("/api/data/comments", params={"search": "Quiet"})
        users = client.get("/api/data/users", params={"search": "Quiet"})
        conversations = client.get("/api/data/conversations", params={"search": "Hello"})

    assert comments.status_code == 200
    assert set(comments.json()) == {"items", "total"}
    assert comments.json()["total"] == 1
    assert comments.json()["items"][0]["content"] == "Quiet cafe please"

    assert users.status_code == 200
    assert set(users.json()) == {"items", "total"}
    assert users.json()["total"] == 1
    assert users.json()["items"][0]["source_comment_content"] == "Quiet cafe please"

    assert conversations.status_code == 200
    assert set(conversations.json()) == {"items", "total"}
    assert conversations.json()["total"] == 1
    assert conversations.json()["items"][0]["last_dm_content"] == "Hello"


def test_conversation_detail_returns_message_ledger(db):
    from app.db.models import Conversation, ConversationMessage
    db.add(Conversation(
        id="detail-conversation",
        account_id="acc-001",
        device_id="read-model-device",
        recipient_nickname="Detail Recipient",
        recipient_douyin_id="detail-recipient",
        current_stage="nurturing",
        last_dm_content="Second message",
        total_dm_count=2,
    ))
    db.add_all([
        ConversationMessage(
            conversation_id="detail-conversation",
            device_id="read-model-device",
            dm_sequence_id="seq-one",
            message_order=1,
            message_key="detail-conversation:seq-one:1",
            content="First message",
            status="sent",
        ),
        ConversationMessage(
            conversation_id="detail-conversation",
            device_id="read-model-device",
            dm_sequence_id="seq-one",
            message_order=2,
            message_key="detail-conversation:seq-one:2",
            content="Second message",
            status="sent",
        ),
    ])
    db.commit()

    with TestClient(app) as client:
        response = client.get("/api/data/conversations/detail-conversation")

    assert response.status_code == 200
    payload = response.json()
    assert payload["conversation"]["recipient_douyin_id"] == "detail-recipient"
    assert payload["history_incomplete"] is False
    assert [message["content"] for message in payload["messages"]] == ["First message", "Second message"]
    assert [message["message_order"] for message in payload["messages"]] == [1, 2]


def test_conversation_detail_hides_other_users_task(db):
    from app.db.models import Conversation, Task
    from app.deps import verify_admin_token

    db.add(Task(
        id="owner-task",
        type="reply_comment",
        account_id="acc-001",
        user_id="owner-user",
        status="completed",
        params={},
    ))
    db.add(Conversation(
        id="owner-conversation",
        task_id="owner-task",
        account_id="acc-001",
        device_id="read-model-device",
        recipient_nickname="Owner Recipient",
        recipient_douyin_id="owner-recipient",
        last_dm_content="Private message",
    ))
    db.commit()

    saved = app.dependency_overrides.get(verify_admin_token)
    app.dependency_overrides[verify_admin_token] = lambda: ("other-user", "operator")
    try:
        with TestClient(app) as client:
            response = client.get("/api/data/conversations/owner-conversation")
    finally:
        if saved is not None:
            app.dependency_overrides[verify_admin_token] = saved
        else:
            app.dependency_overrides.pop(verify_admin_token, None)

    assert response.status_code == 404
def test_export_read_model_response_shapes():
    with TestClient(app) as client:
        comments = client.get("/api/data/export/comments", params={"limit": 1})
        users = client.get("/api/data/export/users", params={"limit": 1})
        conversations = client.get("/api/data/export/conversations", params={"limit": 1})

    for response in (comments, users, conversations):
        assert response.status_code == 200
        assert response.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert response.content

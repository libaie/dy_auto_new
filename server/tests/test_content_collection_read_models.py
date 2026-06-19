from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app


READ_MODEL_ENDPOINTS = {
    "/api/data/comments": "app.domains.content_collection.data_router.list_comments",
    "/api/data/users": "app.domains.content_collection.data_router.list_users",
    "/api/data/conversations": "app.domains.content_collection.data_router.list_conversations",
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
        "export_comments",
        "export_users",
        "export_conversations",
    ):
        assert hasattr(read_models, name)


def test_comment_user_and_conversation_read_model_response_shapes(db):
    from app.db_models import CollectedComment, CollectedUser, Conversation

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

from unittest.mock import AsyncMock, patch

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app


CONTENT_MUTATION_ENDPOINTS = {
    "/api/content/templates": {
        "create_template",
        "list_templates",
    },
    "/api/content/templates/{template_id}": {
        "get_template",
        "update_template",
        "delete_template",
    },
    "/api/content/sensitive-words": {
        "add_sensitive_word",
        "list_sensitive_words",
    },
    "/api/content/sensitive-words/{word_id}": {
        "delete_sensitive_word",
    },
    "/api/content/generate": {
        "generate_content",
    },
    "/api/content/generate-keywords": {
        "generate_keywords",
    },
    "/api/content/generate-regex": {
        "generate_regex",
    },
    "/api/content/generate-clean-prompt": {
        "generate_clean_prompt",
    },
}

DM_SEQUENCE_MUTATION_ENDPOINTS = {
    "/api/dm-sequences": {"list_sequences", "create_sequence"},
    "/api/dm-sequences/{sequence_id}": {"get_sequence", "update_sequence", "delete_sequence"},
    "/api/dm-sequences/generate": {"generate_dm_sequence"},
    "/api/dm-sequences/{seq_id}/variants": {"generate_variants"},
    "/api/dm-sequences/device/sync": {"device_sync"},
}


def test_content_mutation_routes_stay_on_domain_router():
    seen = {}
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path in CONTENT_MUTATION_ENDPOINTS:
            seen.setdefault(route.path, set()).add(route.name)
            assert route.endpoint.__module__ == "app.domains.content_collection.content_router"

    assert seen == CONTENT_MUTATION_ENDPOINTS


def test_dm_sequence_mutation_routes_stay_on_domain_router():
    seen = {}
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path in DM_SEQUENCE_MUTATION_ENDPOINTS:
            seen.setdefault(route.path, set()).add(route.name)
            assert route.endpoint.__module__ == "app.domains.content_collection.dm_sequences_router"

    assert seen == DM_SEQUENCE_MUTATION_ENDPOINTS


def test_content_collection_use_case_modules_export_expected_functions():
    import app.domains.content_collection.content_generation as content_generation
    import app.domains.content_collection.mutations as mutations
    import app.domains.content_collection.realtime_events as realtime_events

    for name in (
        "create_template",
        "list_templates",
        "get_template",
        "update_template",
        "delete_template",
        "add_sensitive_word",
        "list_sensitive_words",
        "delete_sensitive_word",
        "list_dm_sequences",
        "create_dm_sequence",
        "get_dm_sequence",
        "update_dm_sequence",
        "delete_dm_sequence",
        "generate_dm_sequence_events",
        "generate_dm_variants",
        "device_sync_dm_sequences",
    ):
        assert hasattr(mutations, name)

    for name in ("generate_from_template", "generate_keywords", "generate_regex", "generate_clean_prompt"):
        assert hasattr(content_generation, name)

    assert hasattr(realtime_events, "broadcast_content_changed")
    assert hasattr(realtime_events, "broadcast_data_changed")


def test_content_template_and_sensitive_word_response_shapes():
    with TestClient(app) as client:
        created = client.post(
            "/api/content/templates",
            json={
                "name": "mutation-template",
                "category": "comment",
                "body": "Reply about {keyword}",
                "variables": ["keyword"],
            },
        )
        template_id = created.json()["id"]
        listed = client.get("/api/content/templates")
        updated = client.put(
            f"/api/content/templates/{template_id}",
            json={"name": "mutation-template-updated"},
        )
        deleted = client.delete(f"/api/content/templates/{template_id}")

        word = client.post("/api/content/sensitive-words", json={"word": "mutation-sensitive"})
        words = client.get("/api/content/sensitive-words")
        word_deleted = client.delete(f"/api/content/sensitive-words/{word.json()['id']}")

    assert created.status_code == 200
    assert created.json()["name"] == "mutation-template"

    assert listed.status_code == 200
    assert set(listed.json()) == {"templates", "total"}

    assert updated.status_code == 200
    assert updated.json()["name"] == "mutation-template-updated"

    assert deleted.status_code == 200
    assert deleted.json() == {"ok": True}

    assert word.status_code == 200
    assert word.json()["word"] == "mutation-sensitive"

    assert words.status_code == 200
    assert set(words.json()) == {"words", "total"}

    assert word_deleted.status_code == 200
    assert word_deleted.json() == {"ok": True}


def test_content_generation_response_shapes(db):
    from app.domains.content_collection.content_service import content_service

    template = content_service.create_template(
        db,
        name="mutation-generation-template",
        category="comment",
        body="Reply about {keyword}",
        variables=["keyword"],
    )

    with patch(
        "app.domains.content_collection.content_service.ContentService.generate_from_template",
        new_callable=AsyncMock,
        return_value="Generated content",
    ):
        with TestClient(app) as client:
            response = client.post(
                "/api/content/generate",
                json={"template_id": template.id, "context": {"keyword": "coffee"}},
            )

    assert response.status_code == 200
    assert response.json() == {"content": "Generated content", "template_id": template.id}


def test_dm_sequence_mutation_response_shapes():
    with TestClient(app) as client:
        created = client.post(
            "/api/dm-sequences",
            json={
                "name": "Mutation Sequence",
                "messages": [
                    {"order": 2, "content": "second", "delay_ms": 1000},
                    {"order": 1, "content": "first", "delay_ms": 500},
                ],
                "industry": "general",
            },
        )
        sequence_id = created.json()["id"]
        listed = client.get("/api/dm-sequences")
        fetched = client.get(f"/api/dm-sequences/{sequence_id}")
        updated = client.put(
            f"/api/dm-sequences/{sequence_id}",
            json={
                "name": "Mutation Sequence Updated",
                "messages": [{"order": 1, "content": "updated", "delay_ms": 250}],
            },
        )
        deleted = client.delete(f"/api/dm-sequences/{sequence_id}")

    assert created.status_code == 200
    assert created.json()["name"] == "Mutation Sequence"
    assert created.json()["message_count"] == 2
    assert created.json()["messages"][0]["content"] == "first"

    assert listed.status_code == 200
    assert "sequences" in listed.json()

    assert fetched.status_code == 200
    assert fetched.json()["id"] == sequence_id

    assert updated.status_code == 200
    assert updated.json()["name"] == "Mutation Sequence Updated"
    assert updated.json()["message_count"] == 1

    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True, "id": sequence_id}

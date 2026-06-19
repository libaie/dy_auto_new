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


def test_content_mutation_routes_stay_on_domain_router():
    seen = {}
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path in CONTENT_MUTATION_ENDPOINTS:
            seen.setdefault(route.path, set()).add(route.name)
            assert route.endpoint.__module__ == "app.domains.content_collection.content_router"

    assert seen == CONTENT_MUTATION_ENDPOINTS


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
    from app.services.content_service import content_service

    template = content_service.create_template(
        db,
        name="mutation-generation-template",
        category="comment",
        body="Reply about {keyword}",
        variables=["keyword"],
    )

    with patch(
        "app.services.content_service.ContentService.generate_from_template",
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

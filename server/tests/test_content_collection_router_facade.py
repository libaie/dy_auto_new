import importlib
from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]


EXPECTED_CONTENT_ROUTER_SNAPSHOT = [
    ("POST", "/api/content/templates", "create_template"),
    ("GET", "/api/content/templates", "list_templates"),
    ("GET", "/api/content/templates/{template_id}", "get_template"),
    ("PUT", "/api/content/templates/{template_id}", "update_template"),
    ("DELETE", "/api/content/templates/{template_id}", "delete_template"),
    ("POST", "/api/content/sensitive-words", "add_sensitive_word"),
    ("GET", "/api/content/sensitive-words", "list_sensitive_words"),
    ("DELETE", "/api/content/sensitive-words/{word_id}", "delete_sensitive_word"),
    ("POST", "/api/content/generate", "generate_content"),
    ("POST", "/api/content/generate-keywords", "generate_keywords"),
    ("POST", "/api/content/generate-regex", "generate_regex"),
    ("POST", "/api/content/generate-clean-prompt", "generate_clean_prompt"),
]


EXPECTED_DATA_ROUTER_SNAPSHOT = [
    ("GET", "/api/data/comments", "list_comments"),
    ("GET", "/api/data/users", "list_users"),
    ("GET", "/api/data/conversations", "list_conversations"),
    ("GET", "/api/data/conversations/{conversation_id}", "get_conversation"),
    ("GET", "/api/data/export/comments", "export_comments"),
    ("GET", "/api/data/export/users", "export_users"),
    ("GET", "/api/data/export/conversations", "export_conversations"),
]


EXPECTED_DM_SEQUENCES_ROUTER_SNAPSHOT = [
    ("GET", "/api/dm-sequences", "list_sequences"),
    ("POST", "/api/dm-sequences", "create_sequence"),
    ("GET", "/api/dm-sequences/{sequence_id}", "get_sequence"),
    ("PUT", "/api/dm-sequences/{sequence_id}", "update_sequence"),
    ("DELETE", "/api/dm-sequences/{sequence_id}", "delete_sequence"),
    ("POST", "/api/dm-sequences/generate", "generate_dm_sequence"),
    ("POST", "/api/dm-sequences/{seq_id}/variants", "generate_variants"),
    ("GET", "/api/dm-sequences/device/sync", "device_sync"),
]


def test_domain_content_router_matches_current_route_snapshot():
    domain_router = importlib.import_module("app.domains.content_collection.content_router")

    assert _router_snapshot(domain_router.router) == EXPECTED_CONTENT_ROUTER_SNAPSHOT


def test_domain_data_router_matches_current_route_snapshot():
    domain_router = importlib.import_module("app.domains.content_collection.data_router")

    assert _router_snapshot(domain_router.router) == EXPECTED_DATA_ROUTER_SNAPSHOT


def test_domain_dm_sequences_router_matches_current_route_snapshot():
    domain_router = importlib.import_module("app.domains.content_collection.dm_sequences_router")

    assert _router_snapshot(domain_router.router) == EXPECTED_DM_SEQUENCES_ROUTER_SNAPSHOT


def test_legacy_content_router_module_is_domain_router_module():
    legacy_router = importlib.import_module("app.routers.content")
    domain_router = importlib.import_module("app.domains.content_collection.content_router")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router


def test_legacy_data_router_module_is_domain_router_module():
    legacy_router = importlib.import_module("app.routers.data")
    domain_router = importlib.import_module("app.domains.content_collection.data_router")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router


def test_legacy_dm_sequences_router_module_is_domain_router_module():
    legacy_router = importlib.import_module("app.routers.dm_sequences")
    domain_router = importlib.import_module("app.domains.content_collection.dm_sequences_router")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router


def test_router_facade_cleanup_gates_are_documented():
    readme = (REPO_ROOT / "server/app/domains/content_collection/README.md").read_text(encoding="utf-8")

    assert "Compatibility Cleanup Gates" in readme
    assert "Do not remove `app.routers.content`, `app.routers.data`, or `app.routers.dm_sequences` until all of these are true" in readme


def _router_snapshot(router):
    snapshot = []
    for route in router.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods or []):
                snapshot.append((method, route.path, route.name))
    return snapshot

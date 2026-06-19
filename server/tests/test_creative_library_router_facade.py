import importlib

from fastapi.routing import APIRoute


EXPECTED_CHARACTER_ROUTES = [
    ("GET", "/api/characters", "list_characters"),
    ("POST", "/api/characters", "create_character"),
    ("PUT", "/api/characters/{character_id}", "update_character"),
    ("DELETE", "/api/characters/{character_id}", "delete_character"),
    ("POST", "/api/characters/{character_id}/reference-images/generate", "generate_character_reference_images_endpoint"),
    ("POST", "/api/characters/{character_id}/ai-rewrite", "generate_character_ai_rewrite_endpoint"),
    ("POST", "/api/characters/{character_id}/ai-rewrite-candidate", "generate_character_ai_rewrite_endpoint"),
    ("POST", "/api/characters/auto-generate", "auto_generate_characters"),
]


EXPECTED_SCENE_ROUTES = [
    ("GET", "/api/scenes", "list_scenes"),
    ("POST", "/api/scenes", "create_scene"),
    ("PUT", "/api/scenes/{scene_id}", "update_scene"),
    ("DELETE", "/api/scenes/{scene_id}", "delete_scene"),
    ("POST", "/api/scenes/{scene_id}/reference-images/generate", "generate_scene_reference_images_endpoint"),
    ("POST", "/api/scenes/{scene_id}/ai-rewrite", "generate_scene_ai_rewrite_endpoint"),
    ("POST", "/api/scenes/{scene_id}/ai-rewrite-candidate", "generate_scene_ai_rewrite_endpoint"),
    ("POST", "/api/scenes/auto-generate", "auto_generate_scenes"),
]


EXPECTED_REFERENCE_DATA_ROUTES = [
    ("GET", "/api/reference-categories", "list_categories"),
    ("POST", "/api/reference-categories", "create_category"),
    ("PUT", "/api/reference-categories/{cat_id}", "update_category"),
    ("DELETE", "/api/reference-categories/{cat_id}", "delete_category"),
    ("GET", "/api/reference-data/{category}", "list_items"),
    ("POST", "/api/reference-data", "create_item"),
    ("PUT", "/api/reference-data/{item_id}", "update_item"),
    ("DELETE", "/api/reference-data/{item_id}", "delete_item"),
    ("GET", "/api/reference-data/admin/{category}", "list_all_items"),
]


def test_characters_legacy_router_module_is_domain_router_module():
    legacy_router = importlib.import_module("app.routers.characters")
    domain_router = importlib.import_module("app.domains.creative_library.characters_router")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router
    assert _router_snapshot(domain_router.router) == EXPECTED_CHARACTER_ROUTES


def test_scenes_legacy_router_module_is_domain_router_module():
    legacy_router = importlib.import_module("app.routers.scenes")
    domain_router = importlib.import_module("app.domains.creative_library.scenes_router")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router
    assert _router_snapshot(domain_router.router) == EXPECTED_SCENE_ROUTES


def test_reference_data_legacy_router_module_is_domain_router_module():
    legacy_router = importlib.import_module("app.routers.reference_data")
    domain_router = importlib.import_module("app.domains.creative_library.reference_data_router")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router
    assert _router_snapshot(domain_router.router) == EXPECTED_REFERENCE_DATA_ROUTES


def _router_snapshot(router):
    snapshot = []
    for route in router.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods or []):
                snapshot.append((method, route.path, route.name))
    return snapshot

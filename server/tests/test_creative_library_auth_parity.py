from fastapi.routing import APIRoute

from app.main import app


EXPECTED_CREATIVE_LIBRARY_HTTP_ROUTES = [
    ("/api/characters", ("GET",), "list_characters", "app.domains.creative_library.characters_router.list_characters", ("get_db", "verify_admin_token")),
    ("/api/characters", ("POST",), "create_character", "app.domains.creative_library.characters_router.create_character", ("get_db", "verify_admin_token")),
    ("/api/characters/{character_id}", ("PUT",), "update_character", "app.domains.creative_library.characters_router.update_character", ("get_db", "verify_admin_token")),
    ("/api/characters/{character_id}", ("DELETE",), "delete_character", "app.domains.creative_library.characters_router.delete_character", ("get_db", "verify_admin_token")),
    ("/api/characters/{character_id}/reference-images/generate", ("POST",), "generate_character_reference_images_endpoint", "app.domains.creative_library.characters_router.generate_character_reference_images_endpoint", ("get_db", "verify_admin_token")),
    ("/api/characters/{character_id}/ai-rewrite", ("POST",), "generate_character_ai_rewrite_endpoint", "app.domains.creative_library.characters_router.generate_character_ai_rewrite_endpoint", ("get_db", "verify_admin_token")),
    ("/api/characters/{character_id}/ai-rewrite-candidate", ("POST",), "generate_character_ai_rewrite_endpoint", "app.domains.creative_library.characters_router.generate_character_ai_rewrite_endpoint", ("get_db", "verify_admin_token")),
    ("/api/characters/auto-generate", ("POST",), "auto_generate_characters", "app.domains.creative_library.characters_router.auto_generate_characters", ("get_db", "verify_admin_token")),
    ("/api/scenes", ("GET",), "list_scenes", "app.domains.creative_library.scenes_router.list_scenes", ("get_db", "verify_admin_token")),
    ("/api/scenes", ("POST",), "create_scene", "app.domains.creative_library.scenes_router.create_scene", ("get_db", "verify_admin_token")),
    ("/api/scenes/{scene_id}", ("PUT",), "update_scene", "app.domains.creative_library.scenes_router.update_scene", ("get_db", "verify_admin_token")),
    ("/api/scenes/{scene_id}", ("DELETE",), "delete_scene", "app.domains.creative_library.scenes_router.delete_scene", ("get_db", "verify_admin_token")),
    ("/api/scenes/{scene_id}/reference-images/generate", ("POST",), "generate_scene_reference_images_endpoint", "app.domains.creative_library.scenes_router.generate_scene_reference_images_endpoint", ("get_db", "verify_admin_token")),
    ("/api/scenes/{scene_id}/ai-rewrite", ("POST",), "generate_scene_ai_rewrite_endpoint", "app.domains.creative_library.scenes_router.generate_scene_ai_rewrite_endpoint", ("get_db", "verify_admin_token")),
    ("/api/scenes/{scene_id}/ai-rewrite-candidate", ("POST",), "generate_scene_ai_rewrite_endpoint", "app.domains.creative_library.scenes_router.generate_scene_ai_rewrite_endpoint", ("get_db", "verify_admin_token")),
    ("/api/scenes/auto-generate", ("POST",), "auto_generate_scenes", "app.domains.creative_library.scenes_router.auto_generate_scenes", ("get_db", "verify_admin_token")),
    ("/api/reference-categories", ("GET",), "list_categories", "app.domains.creative_library.reference_data_router.list_categories", ("get_db",)),
    ("/api/reference-categories", ("POST",), "create_category", "app.domains.creative_library.reference_data_router.create_category", ("get_db", "verify_admin_token")),
    ("/api/reference-categories/{cat_id}", ("PUT",), "update_category", "app.domains.creative_library.reference_data_router.update_category", ("get_db", "verify_admin_token")),
    ("/api/reference-categories/{cat_id}", ("DELETE",), "delete_category", "app.domains.creative_library.reference_data_router.delete_category", ("get_db", "verify_admin_token")),
    ("/api/reference-data/{category}", ("GET",), "list_items", "app.domains.creative_library.reference_data_router.list_items", ("get_db",)),
    ("/api/reference-data", ("POST",), "create_item", "app.domains.creative_library.reference_data_router.create_item", ("get_db", "verify_admin_token")),
    ("/api/reference-data/{item_id}", ("PUT",), "update_item", "app.domains.creative_library.reference_data_router.update_item", ("get_db", "verify_admin_token")),
    ("/api/reference-data/{item_id}", ("DELETE",), "delete_item", "app.domains.creative_library.reference_data_router.delete_item", ("get_db", "verify_admin_token")),
    ("/api/reference-data/admin/{category}", ("GET",), "list_all_items", "app.domains.creative_library.reference_data_router.list_all_items", ("get_db", "verify_admin_token")),
]


def test_creative_library_route_table_snapshot():
    assert _creative_library_http_routes() == EXPECTED_CREATIVE_LIBRARY_HTTP_ROUTES


def _creative_library_http_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and _is_creative_library_route(route.path):
            endpoint = f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
            dependency_names = tuple(
                getattr(dep.call, "__name__", repr(dep.call))
                for dep in route.dependant.dependencies
                if dep.call
            )
            routes.append((route.path, tuple(sorted(route.methods)), route.name, endpoint, dependency_names))
    return routes


def _is_creative_library_route(path):
    return path.startswith((
        "/api/characters",
        "/api/scenes",
        "/api/reference-categories",
        "/api/reference-data",
    ))

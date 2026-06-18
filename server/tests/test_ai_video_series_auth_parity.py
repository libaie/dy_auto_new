from fastapi.routing import APIRoute

from app.main import app


EXPECTED_SERIES_ROUTES = [
    ("/api/series/{series_id}/auto-generate", ("POST",), "auto_generate_series_assets", ("get_db", "verify_admin_token")),
    ("/api/series", ("GET",), "list_series", ("get_db", "verify_admin_token")),
    ("/api/series/{series_id}/style-lock", ("GET",), "get_style_lock", ("get_db", "verify_admin_token")),
    ("/api/series/{series_id}/agency-console", ("GET",), "get_agency_console", ("get_db", "checker")),
    ("/api/series/style-lock/worker-step", ("POST",), "run_style_lock_worker_step", ("get_db", "checker")),
    ("/api/series/story-plan/worker-step", ("POST",), "run_story_plan_worker_step", ("get_db", "checker")),
    ("/api/series/{series_id}/style-lock", ("POST",), "lock_series_style", ("get_db", "verify_admin_token")),
    ("/api/series", ("POST",), "create_series", ("get_db", "verify_admin_token")),
    ("/api/series/{series_id}", ("GET",), "get_series", ("get_db", "verify_admin_token")),
    ("/api/series/{series_id}/ensure-episodes", ("POST",), "ensure_series_episodes", ("get_db", "verify_admin_token")),
    ("/api/series/{series_id}/story-plan", ("POST",), "create_series_story_plan", ("get_db", "verify_admin_token")),
    ("/api/series/{series_id}", ("PUT",), "update_series", ("get_db", "verify_admin_token")),
    ("/api/series/{series_id}", ("DELETE",), "delete_series", ("get_db", "verify_admin_token")),
    ("/api/series/{series_id}/characters/{character_id}", ("POST",), "link_character", ("get_db", "verify_admin_token")),
    ("/api/series/{series_id}/characters/{character_id}", ("DELETE",), "unlink_character", ("get_db", "verify_admin_token")),
    ("/api/series/{series_id}/scenes/{scene_id}", ("POST",), "link_scene", ("get_db", "verify_admin_token")),
    ("/api/series/{series_id}/scenes/{scene_id}", ("DELETE",), "unlink_scene", ("get_db", "verify_admin_token")),
    ("/api/series/{series_id}/episodes/{episode_id}/script", ("POST",), "generate_episode_script", ("get_db", "verify_admin_token")),
    ("/api/series/{series_id}/episodes/{episode_id}", ("PUT",), "update_episode", ("get_db", "verify_admin_token")),
]


def test_series_route_table_snapshot():
    routes = [(path, methods, name) for path, methods, name, _dependencies in _series_routes()]

    assert routes == [(path, methods, name) for path, methods, name, _dependencies in EXPECTED_SERIES_ROUTES]


def test_series_route_auth_dependency_snapshot():
    assert _series_routes() == EXPECTED_SERIES_ROUTES


def _series_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/series"):
            dependency_names = [dep.call.__name__ for dep in route.dependant.dependencies if dep.call]
            routes.append((route.path, tuple(sorted(route.methods)), route.name, tuple(dependency_names)))
    return routes

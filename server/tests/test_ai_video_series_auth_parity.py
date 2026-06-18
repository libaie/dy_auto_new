from fastapi.routing import APIRoute

from app.main import app


EXPECTED_BASELINE_SERIES_ROUTES = [
    ("/api/series/{series_id}/auto-generate", ("POST",), "auto_generate_series_assets", ("get_db", "verify_admin_token")),
    ("/api/series", ("GET",), "list_series", ("get_db", "verify_admin_token")),
    ("/api/series/{series_id}/style-lock", ("GET",), "get_style_lock", ("get_db", "verify_admin_token")),
    ("/api/series/{series_id}/agency-console", ("GET",), "get_agency_console", ("get_db", "require_role:admin")),
    ("/api/series/style-lock/worker-step", ("POST",), "run_style_lock_worker_step", ("get_db", "require_role:admin")),
    ("/api/series/{series_id}/style-lock", ("POST",), "lock_series_style", ("get_db", "verify_admin_token")),
    ("/api/series", ("POST",), "create_series", ("get_db", "verify_admin_token")),
    ("/api/series/{series_id}", ("GET",), "get_series", ("get_db",)),
    ("/api/series/{series_id}", ("PUT",), "update_series", ("get_db", "verify_admin_token")),
    ("/api/series/{series_id}", ("DELETE",), "delete_series", ("get_db", "verify_admin_token")),
    ("/api/series/{series_id}/characters/{character_id}", ("POST",), "link_character", ("get_db", "verify_admin_token")),
    ("/api/series/{series_id}/characters/{character_id}", ("DELETE",), "unlink_character", ("get_db", "verify_admin_token")),
    ("/api/series/{series_id}/scenes/{scene_id}", ("POST",), "link_scene", ("get_db", "verify_admin_token")),
    ("/api/series/{series_id}/scenes/{scene_id}", ("DELETE",), "unlink_scene", ("get_db", "verify_admin_token")),
    ("/api/series/{series_id}/episodes/{episode_id}", ("PUT",), "update_episode", ("get_db", "verify_admin_token")),
]


EXPECTED_IN_PROGRESS_SERIES_ROUTES = [
    ("/api/series/{series_id}/auto-generate", ("POST",), "auto_generate_series_assets", ("get_db", "verify_admin_token")),
    ("/api/series", ("GET",), "list_series", ("get_db", "verify_admin_token")),
    ("/api/series/{series_id}/style-lock", ("GET",), "get_style_lock", ("get_db", "verify_admin_token")),
    ("/api/series/{series_id}/agency-console", ("GET",), "get_agency_console", ("get_db", "require_role:admin")),
    ("/api/series/style-lock/worker-step", ("POST",), "run_style_lock_worker_step", ("get_db", "require_role:admin")),
    ("/api/series/story-plan/worker-step", ("POST",), "run_story_plan_worker_step", ("get_db", "require_role:admin")),
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


ALLOWED_SERIES_ROUTE_SNAPSHOTS = [
    EXPECTED_BASELINE_SERIES_ROUTES,
    EXPECTED_IN_PROGRESS_SERIES_ROUTES,
]


def test_series_route_table_snapshot():
    routes = [(path, methods, name) for path, methods, name, _dependencies in _series_routes()]

    assert routes in [
        [(path, methods, name) for path, methods, name, _dependencies in snapshot]
        for snapshot in ALLOWED_SERIES_ROUTE_SNAPSHOTS
    ]


def test_series_route_auth_dependency_snapshot():
    assert _series_routes() in ALLOWED_SERIES_ROUTE_SNAPSHOTS


def _series_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and _is_series_route(route.path):
            dependency_names = [_dependency_identity(dep.call) for dep in route.dependant.dependencies if dep.call]
            routes.append((route.path, tuple(sorted(route.methods)), route.name, tuple(dependency_names)))
    return routes


def _is_series_route(path):
    return path == "/api/series" or path.startswith("/api/series/")


def _dependency_identity(call):
    name = getattr(call, "__name__", repr(call))
    qualname = getattr(call, "__qualname__", "")
    if name == "checker" and qualname.endswith("require_role.<locals>.checker"):
        closure = getattr(call, "__closure__", None) or ()
        for cell in closure:
            try:
                value = cell.cell_contents
            except ValueError:
                continue
            if isinstance(value, str):
                return f"require_role:{value}"
            if isinstance(value, (frozenset, set, tuple, list)) and value:
                roles = ",".join(sorted(str(role) for role in value))
                return f"require_role:{roles}"
    return name

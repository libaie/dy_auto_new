from fastapi.routing import APIRoute

from app.main import app


EXPECTED_DIRECTOR_PLANNING_HTTP_ROUTES = [
    (
        "/api/director/auto-plan",
        ("POST",),
        "auto_plan_episode",
        "app.domains.director_planning.director_router.auto_plan_episode",
        ("get_db", "verify_admin_token"),
    ),
    (
        "/api/director/episode-production-plan",
        ("POST",),
        "create_episode_production_plan_endpoint",
        "app.domains.director_planning.director_router.create_episode_production_plan_endpoint",
        ("get_db", "verify_admin_token"),
    ),
    (
        "/api/director/episode-plan",
        ("POST",),
        "create_episode_plan_endpoint",
        "app.domains.director_planning.director_router.create_episode_plan_endpoint",
        ("get_db", "verify_admin_token"),
    ),
    (
        "/api/director/shot-segments",
        ("POST",),
        "create_shot_segments_endpoint",
        "app.domains.director_planning.director_router.create_shot_segments_endpoint",
        ("get_db", "verify_admin_token"),
    ),
    (
        "/api/director/plan",
        ("POST",),
        "build_plan",
        "app.domains.director_planning.director_router.build_plan",
        ("verify_admin_token",),
    ),
]


def test_director_planning_route_table_snapshot():
    assert _director_planning_http_routes() == EXPECTED_DIRECTOR_PLANNING_HTTP_ROUTES


def _director_planning_http_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/director"):
            endpoint = f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
            dependency_names = tuple(
                getattr(dep.call, "__name__", repr(dep.call))
                for dep in route.dependant.dependencies
                if dep.call
            )
            routes.append((route.path, tuple(sorted(route.methods)), route.name, endpoint, dependency_names))
    return routes

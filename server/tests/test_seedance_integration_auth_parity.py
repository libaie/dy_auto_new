from fastapi.routing import APIRoute

from app.main import app


EXPECTED_SEEDANCE_HTTP_ROUTES = [
    (
        "/api/seedance/generate",
        ("POST",),
        "seedance_generate",
        "app.domains.seedance_integration.seedance_router.seedance_generate",
        ("get_db", "checker"),
    ),
    (
        "/api/seedance/task/{task_id}",
        ("GET",),
        "seedance_get_task",
        "app.domains.seedance_integration.seedance_router.seedance_get_task",
        ("get_db", "checker"),
    ),
    (
        "/api/seedance-proxy/{path:path}",
        ("DELETE", "GET", "PATCH", "POST", "PUT"),
        "proxy_seedance",
        "app.domains.seedance_integration.seedance_router.proxy_seedance",
        ("get_db", "checker"),
    ),
    (
        "/api/seedance-proxy/",
        ("DELETE", "GET", "PATCH", "POST", "PUT"),
        "proxy_seedance_root",
        "app.domains.seedance_integration.seedance_router.proxy_seedance_root",
        ("get_db", "checker"),
    ),
]


def test_seedance_integration_route_table_snapshot():
    assert _seedance_http_routes() == EXPECTED_SEEDANCE_HTTP_ROUTES


def _seedance_http_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and (
            route.path.startswith("/api/seedance") or route.path.startswith("/api/seedance-proxy")
        ):
            endpoint = f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
            dependency_names = tuple(
                getattr(dep.call, "__name__", repr(dep.call))
                for dep in route.dependant.dependencies
                if dep.call
            )
            routes.append((route.path, tuple(sorted(route.methods)), route.name, endpoint, dependency_names))
    return routes

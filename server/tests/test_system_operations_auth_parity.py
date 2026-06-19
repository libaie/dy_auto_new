from fastapi.routing import APIRoute

from app.main import app


EXPECTED_SYSTEM_OPERATIONS_HTTP_ROUTES = [
    ("/api/system/health", ("GET",), "system_health", "app.domains.system_operations.system_health_router.system_health", ("get_db", "verify_admin_token")),
]


def test_system_operations_route_table_snapshot():
    assert _system_operations_http_routes() == EXPECTED_SYSTEM_OPERATIONS_HTTP_ROUTES


def _system_operations_http_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/system"):
            endpoint = f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
            dependency_names = tuple(
                getattr(dep.call, "__name__", repr(dep.call))
                for dep in route.dependant.dependencies
                if dep.call
            )
            routes.append((route.path, tuple(sorted(route.methods)), route.name, endpoint, dependency_names))
    return routes

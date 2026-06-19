from fastapi.routing import APIRoute

from app.main import app


EXPECTED_IDENTITY_ACCESS_HTTP_ROUTES = [
    (
        "/api/auth/login",
        ("POST",),
        "login",
        "app.domains.identity_access.auth_router.login",
        ("get_db",),
    ),
    (
        "/api/auth/device-login",
        ("POST",),
        "device_login",
        "app.domains.identity_access.auth_router.device_login",
        ("get_db",),
    ),
    (
        "/api/auth/register",
        ("POST",),
        "register_user",
        "app.domains.identity_access.auth_router.register_user",
        ("checker", "get_db"),
    ),
    (
        "/api/auth/users",
        ("GET",),
        "list_users",
        "app.domains.identity_access.auth_router.list_users",
        ("checker", "get_db"),
    ),
]


def test_identity_access_route_table_snapshot():
    assert _identity_access_http_routes() == EXPECTED_IDENTITY_ACCESS_HTTP_ROUTES


def _identity_access_http_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/auth"):
            endpoint = f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
            dependency_names = tuple(
                getattr(dep.call, "__name__", repr(dep.call))
                for dep in route.dependant.dependencies
                if dep.call
            )
            routes.append((route.path, tuple(sorted(route.methods)), route.name, endpoint, dependency_names))
    return routes

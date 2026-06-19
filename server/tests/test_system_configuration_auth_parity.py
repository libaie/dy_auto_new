from fastapi.routing import APIRoute

from app.main import app


EXPECTED_SYSTEM_CONFIGURATION_HTTP_ROUTES = [
    (
        "/api/settings",
        ("GET",),
        "get_settings",
        "app.domains.system_configuration.settings_router.get_settings",
        ("get_db", "verify_admin_token"),
    ),
    (
        "/api/settings",
        ("PUT",),
        "update_settings",
        "app.domains.system_configuration.settings_router.update_settings",
        ("get_db", "checker"),
    ),
]


def test_system_configuration_route_table_snapshot():
    assert _system_configuration_http_routes() == EXPECTED_SYSTEM_CONFIGURATION_HTTP_ROUTES


def _system_configuration_http_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/settings"):
            endpoint = f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
            dependency_names = tuple(
                getattr(dep.call, "__name__", repr(dep.call))
                for dep in route.dependant.dependencies
                if dep.call
            )
            routes.append((route.path, tuple(sorted(route.methods)), route.name, endpoint, dependency_names))
    return routes

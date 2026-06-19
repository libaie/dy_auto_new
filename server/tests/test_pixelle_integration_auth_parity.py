from fastapi.routing import APIRoute

from app.main import app


EXPECTED_PIXELLE_HTTP_ROUTES = [
    (
        "/api/pixelle/config",
        ("GET",),
        "get_pixelle_config",
        "app.domains.pixelle_integration.pixelle_router.get_pixelle_config",
        ("checker",),
    ),
    (
        "/api/pixelle/config",
        ("PUT",),
        "update_pixelle_config",
        "app.domains.pixelle_integration.pixelle_router.update_pixelle_config",
        ("get_db", "checker"),
    ),
    (
        "/api/pixelle/template-preview/{size}/{filename}",
        ("GET",),
        "template_preview_image",
        "app.domains.pixelle_integration.pixelle_router.template_preview_image",
        (),
    ),
    (
        "/api/pixelle/test-connection",
        ("GET",),
        "test_connection",
        "app.domains.pixelle_integration.pixelle_router.test_connection",
        ("get_db", "checker"),
    ),
    (
        "/api/pixelle-proxy/{path:path}",
        ("DELETE", "GET", "PATCH", "POST", "PUT"),
        "proxy_to_pixelle",
        "app.domains.pixelle_integration.pixelle_router.proxy_to_pixelle",
        ("get_db", "checker"),
    ),
    (
        "/api/pixelle-proxy/",
        ("DELETE", "GET", "PATCH", "POST", "PUT"),
        "proxy_root_to_pixelle",
        "app.domains.pixelle_integration.pixelle_router.proxy_root_to_pixelle",
        ("get_db", "checker"),
    ),
]


def test_pixelle_integration_route_table_snapshot():
    assert _pixelle_http_routes() == EXPECTED_PIXELLE_HTTP_ROUTES


def _pixelle_http_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and (
            route.path.startswith("/api/pixelle") or route.path.startswith("/api/pixelle-proxy")
        ):
            endpoint = f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
            dependency_names = tuple(
                getattr(dep.call, "__name__", repr(dep.call))
                for dep in route.dependant.dependencies
                if dep.call
            )
            routes.append((route.path, tuple(sorted(route.methods)), route.name, endpoint, dependency_names))
    return routes

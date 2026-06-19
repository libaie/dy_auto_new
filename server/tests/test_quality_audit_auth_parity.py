from fastapi.routing import APIRoute

from app.main import app


EXPECTED_QUALITY_AUDIT_HTTP_ROUTES = [
    (
        "/api/audit/image",
        ("POST",),
        "audit_image",
        "app.domains.quality_audit.audit_router.audit_image",
        ("get_db", "verify_admin_token"),
    ),
    (
        "/api/audit/reports/{target_type}/{target_id}",
        ("GET",),
        "list_reports",
        "app.domains.quality_audit.audit_router.list_reports",
        ("get_db",),
    ),
]


def test_quality_audit_route_table_snapshot():
    assert _quality_audit_http_routes() == EXPECTED_QUALITY_AUDIT_HTTP_ROUTES


def _quality_audit_http_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/audit"):
            endpoint = f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
            dependency_names = tuple(
                getattr(dep.call, "__name__", repr(dep.call))
                for dep in route.dependant.dependencies
                if dep.call
            )
            routes.append((route.path, tuple(sorted(route.methods)), route.name, endpoint, dependency_names))
    return routes

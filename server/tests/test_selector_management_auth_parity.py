from fastapi.routing import APIRoute

from app.main import app


EXPECTED_SELECTOR_MANAGEMENT_HTTP_ROUTES = [
    ("/api/selectors", ("GET",), "list_selectors", "app.domains.selector_management.selectors_router.list_selectors", ("get_db", "verify_admin_token")),
    ("/api/selectors/templates", ("GET",), "list_templates", "app.domains.selector_management.selectors_router.list_templates", ("verify_admin_token",)),
    ("/api/selectors/templates/upload", ("POST",), "upload_template", "app.domains.selector_management.selectors_router.upload_template", ("checker",)),
    ("/api/selectors/templates/{filename}", ("DELETE",), "delete_template", "app.domains.selector_management.selectors_router.delete_template", ("checker",)),
    ("/api/selectors/{action_name}", ("GET",), "get_selector", "app.domains.selector_management.selectors_router.get_selector", ("get_db", "verify_admin_token")),
    ("/api/selectors", ("POST",), "create_selector", "app.domains.selector_management.selectors_router.create_selector", ("get_db", "checker")),
    ("/api/selectors/{action_name}", ("PUT",), "update_selector", "app.domains.selector_management.selectors_router.update_selector", ("get_db", "checker")),
    ("/api/selectors/{action_name}", ("DELETE",), "delete_selector", "app.domains.selector_management.selectors_router.delete_selector", ("get_db", "checker")),
    ("/api/selectors/{action_name}/toggle", ("PATCH",), "toggle_selector", "app.domains.selector_management.selectors_router.toggle_selector", ("get_db", "checker")),
]


def test_selector_management_route_table_snapshot():
    assert _selector_management_http_routes() == EXPECTED_SELECTOR_MANAGEMENT_HTTP_ROUTES


def _selector_management_http_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/selectors"):
            endpoint = f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
            dependency_names = tuple(
                getattr(dep.call, "__name__", repr(dep.call))
                for dep in route.dependant.dependencies
                if dep.call
            )
            routes.append((route.path, tuple(sorted(route.methods)), route.name, endpoint, dependency_names))
    return routes

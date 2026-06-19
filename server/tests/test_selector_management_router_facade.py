import importlib

from fastapi.routing import APIRoute


EXPECTED_SELECTOR_ROUTES = [
    ("GET", "/api/selectors", "list_selectors"),
    ("GET", "/api/selectors/templates", "list_templates"),
    ("POST", "/api/selectors/templates/upload", "upload_template"),
    ("DELETE", "/api/selectors/templates/{filename}", "delete_template"),
    ("GET", "/api/selectors/{action_name}", "get_selector"),
    ("POST", "/api/selectors", "create_selector"),
    ("PUT", "/api/selectors/{action_name}", "update_selector"),
    ("DELETE", "/api/selectors/{action_name}", "delete_selector"),
    ("PATCH", "/api/selectors/{action_name}/toggle", "toggle_selector"),
]


def test_selectors_legacy_router_module_is_domain_router_module():
    legacy_router = importlib.import_module("app.routers.selectors")
    domain_router = importlib.import_module("app.domains.selector_management.selectors_router")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router
    assert _router_snapshot(domain_router.router) == EXPECTED_SELECTOR_ROUTES


def _router_snapshot(router):
    snapshot = []
    for route in router.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods or []):
                snapshot.append((method, route.path, route.name))
    return snapshot

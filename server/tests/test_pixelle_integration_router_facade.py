import importlib

import pytest
from fastapi.routing import APIRoute


EXPECTED_PIXELLE_ROUTES = [
    ("GET", "/api/pixelle/config", "get_pixelle_config"),
    ("PUT", "/api/pixelle/config", "update_pixelle_config"),
    ("GET", "/api/pixelle/template-preview/{size}/{filename}", "template_preview_image"),
    ("GET", "/api/pixelle/test-connection", "test_connection"),
]

EXPECTED_PIXELLE_PROXY_ROUTES = [
    ("DELETE", "/api/pixelle-proxy/{path:path}", "proxy_to_pixelle"),
    ("GET", "/api/pixelle-proxy/{path:path}", "proxy_to_pixelle"),
    ("PATCH", "/api/pixelle-proxy/{path:path}", "proxy_to_pixelle"),
    ("POST", "/api/pixelle-proxy/{path:path}", "proxy_to_pixelle"),
    ("PUT", "/api/pixelle-proxy/{path:path}", "proxy_to_pixelle"),
    ("DELETE", "/api/pixelle-proxy/", "proxy_root_to_pixelle"),
    ("GET", "/api/pixelle-proxy/", "proxy_root_to_pixelle"),
    ("PATCH", "/api/pixelle-proxy/", "proxy_root_to_pixelle"),
    ("POST", "/api/pixelle-proxy/", "proxy_root_to_pixelle"),
    ("PUT", "/api/pixelle-proxy/", "proxy_root_to_pixelle"),
]


def test_pixelle_legacy_router_module_is_domain_router_module():
    try:
        legacy_router = importlib.import_module("app.routers.pixelle")
        domain_router = importlib.import_module("app.domains.pixelle_integration.pixelle_router")
    except ModuleNotFoundError as exc:
        pytest.fail(f"pixelle integration domain router import failed: {exc}")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router
    assert legacy_router.proxy_router is domain_router.proxy_router
    assert legacy_router._serialize_ai_models is domain_router._serialize_ai_models
    assert legacy_router._redact_secrets is domain_router._redact_secrets
    assert legacy_router._get_proxy_client is domain_router._get_proxy_client
    assert _router_snapshot(domain_router.router) == EXPECTED_PIXELLE_ROUTES
    assert _router_snapshot(domain_router.proxy_router) == EXPECTED_PIXELLE_PROXY_ROUTES


def _router_snapshot(router):
    snapshot = []
    for route in router.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods or []):
                snapshot.append((method, route.path, route.name))
    return snapshot

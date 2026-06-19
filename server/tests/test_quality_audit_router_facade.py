import importlib

import pytest
from fastapi.routing import APIRoute


EXPECTED_QUALITY_AUDIT_ROUTES = [
    ("POST", "/api/audit/image", "audit_image"),
    ("GET", "/api/audit/reports/{target_type}/{target_id}", "list_reports"),
]


def test_audit_legacy_router_module_is_domain_router_module():
    try:
        legacy_router = importlib.import_module("app.routers.audit")
        domain_router = importlib.import_module("app.domains.quality_audit.audit_router")
    except ModuleNotFoundError as exc:
        pytest.fail(f"quality audit domain router import failed: {exc}")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router
    assert legacy_router._do_audit is domain_router._do_audit
    assert legacy_router._audit_openai_compatible is domain_router._audit_openai_compatible
    assert legacy_router.httpx is domain_router.httpx
    assert _router_snapshot(domain_router.router) == EXPECTED_QUALITY_AUDIT_ROUTES


def _router_snapshot(router):
    snapshot = []
    for route in router.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods or []):
                snapshot.append((method, route.path, route.name))
    return snapshot

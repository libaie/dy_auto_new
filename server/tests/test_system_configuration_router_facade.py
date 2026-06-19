import importlib

import pytest
from fastapi.routing import APIRoute


EXPECTED_SYSTEM_CONFIGURATION_ROUTES = [
    ("GET", "/api/settings", "get_settings"),
    ("PUT", "/api/settings", "update_settings"),
]


def test_settings_legacy_router_module_is_domain_router_module():
    try:
        legacy_router = importlib.import_module("app.routers.settings")
        domain_router = importlib.import_module("app.domains.system_configuration.settings_router")
    except ModuleNotFoundError as exc:
        pytest.fail(f"system configuration domain router import failed: {exc}")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router
    assert _router_snapshot(domain_router.router) == EXPECTED_SYSTEM_CONFIGURATION_ROUTES


def _router_snapshot(router):
    snapshot = []
    for route in router.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods or []):
                snapshot.append((method, route.path, route.name))
    return snapshot

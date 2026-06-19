import importlib

import pytest
from fastapi.routing import APIRoute


EXPECTED_IDENTITY_ACCESS_ROUTES = [
    ("POST", "/api/auth/login", "login"),
    ("POST", "/api/auth/device-login", "device_login"),
    ("POST", "/api/auth/register", "register_user"),
    ("GET", "/api/auth/users", "list_users"),
]


def test_auth_legacy_router_module_is_domain_router_module():
    try:
        legacy_router = importlib.import_module("app.routers.auth")
        domain_router = importlib.import_module("app.domains.identity_access.auth_router")
    except ModuleNotFoundError as exc:
        pytest.fail(f"identity access domain router import failed: {exc}")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router
    assert legacy_router._failed_attempts is domain_router._failed_attempts
    assert _router_snapshot(domain_router.router) == EXPECTED_IDENTITY_ACCESS_ROUTES


def _router_snapshot(router):
    snapshot = []
    for route in router.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods or []):
                snapshot.append((method, route.path, route.name))
    return snapshot

import importlib

import pytest
from fastapi.routing import APIRoute


EXPECTED_STATS_ROUTES = [
    ("GET", "/api/stats/dashboard", "dashboard_summary"),
    ("GET", "/api/stats/daily", "daily_stats"),
    ("GET", "/api/stats/accounts/{account_id}", "account_stats"),
    ("GET", "/api/stats/realtime", "realtime_stats"),
]


def test_stats_legacy_router_module_is_domain_router_module():
    try:
        legacy_router = importlib.import_module("app.routers.stats")
        domain_router = importlib.import_module("app.domains.reporting.stats_router")
    except ModuleNotFoundError as exc:
        pytest.fail(f"reporting domain router import failed: {exc}")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router
    assert _router_snapshot(domain_router.router) == EXPECTED_STATS_ROUTES


def _router_snapshot(router):
    snapshot = []
    for route in router.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods or []):
                snapshot.append((method, route.path, route.name))
    return snapshot

import importlib

from fastapi.routing import APIRoute


EXPECTED_SYSTEM_HEALTH_ROUTES = [
    ("GET", "/api/system/health", "system_health"),
]


def test_system_health_legacy_router_module_is_domain_router_module():
    legacy_router = importlib.import_module("app.routers.system_health")
    domain_router = importlib.import_module("app.domains.system_operations.system_health_router")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router
    assert _router_snapshot(domain_router.router) == EXPECTED_SYSTEM_HEALTH_ROUTES


def test_system_health_helper_monkeypatch_path_is_preserved():
    legacy_router = importlib.import_module("app.routers.system_health")
    domain_router = importlib.import_module("app.domains.system_operations.system_health_router")

    assert legacy_router._migration_health is domain_router._migration_health
    assert legacy_router._provider_capability_health is domain_router._provider_capability_health
    assert legacy_router._capability_for_model is domain_router._capability_for_model


def _router_snapshot(router):
    snapshot = []
    for route in router.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods or []):
                snapshot.append((method, route.path, route.name))
    return snapshot

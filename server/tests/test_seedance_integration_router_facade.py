import importlib

import pytest
from fastapi.routing import APIRoute


EXPECTED_SEEDANCE_API_ROUTES = [
    ("POST", "/api/seedance/generate", "seedance_generate"),
    ("GET", "/api/seedance/task/{task_id}", "seedance_get_task"),
]

EXPECTED_SEEDANCE_PROXY_ROUTES = [
    ("DELETE", "/api/seedance-proxy/{path:path}", "proxy_seedance"),
    ("GET", "/api/seedance-proxy/{path:path}", "proxy_seedance"),
    ("PATCH", "/api/seedance-proxy/{path:path}", "proxy_seedance"),
    ("POST", "/api/seedance-proxy/{path:path}", "proxy_seedance"),
    ("PUT", "/api/seedance-proxy/{path:path}", "proxy_seedance"),
    ("DELETE", "/api/seedance-proxy/", "proxy_seedance_root"),
    ("GET", "/api/seedance-proxy/", "proxy_seedance_root"),
    ("PATCH", "/api/seedance-proxy/", "proxy_seedance_root"),
    ("POST", "/api/seedance-proxy/", "proxy_seedance_root"),
    ("PUT", "/api/seedance-proxy/", "proxy_seedance_root"),
]


def test_seedance_legacy_router_module_is_domain_router_module():
    try:
        legacy_router = importlib.import_module("app.routers.seedance")
        domain_router = importlib.import_module("app.domains.seedance_integration.seedance_router")
    except ModuleNotFoundError as exc:
        pytest.fail(f"seedance integration domain router import failed: {exc}")

    assert legacy_router is domain_router
    assert legacy_router.api_router is domain_router.api_router
    assert legacy_router.proxy_router is domain_router.proxy_router
    assert legacy_router.SeedanceGenerateRequest is domain_router.SeedanceGenerateRequest
    assert legacy_router._get_client is domain_router._get_client
    assert legacy_router._get_api_key is domain_router._get_api_key
    assert legacy_router._do_proxy is domain_router._do_proxy
    assert _router_snapshot(domain_router.api_router) == EXPECTED_SEEDANCE_API_ROUTES
    assert _router_snapshot(domain_router.proxy_router) == EXPECTED_SEEDANCE_PROXY_ROUTES


def _router_snapshot(router):
    snapshot = []
    for route in router.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods or []):
                snapshot.append((method, route.path, route.name))
    return snapshot

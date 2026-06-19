import importlib

import pytest
from fastapi.routing import APIRoute


EXPECTED_SCRIPT_PIPELINE_ROUTES = [
    ("POST", "/api/pipeline/start", "pipeline_start"),
    ("GET", "/api/pipeline/runs/{series_id}", "list_pipeline_runs"),
    ("GET", "/api/pipeline/runs/by-id/{run_id}", "get_pipeline_run_by_id"),
    ("GET", "/api/pipeline/runs/{series_id}/{run_id}", "get_pipeline_run"),
]


def test_pipeline_legacy_router_module_is_domain_router_module():
    try:
        legacy_router = importlib.import_module("app.routers.pipeline")
        domain_router = importlib.import_module("app.domains.script_pipeline.pipeline_router")
    except ModuleNotFoundError as exc:
        pytest.fail(f"script pipeline domain router import failed: {exc}")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router
    assert legacy_router._run_all_layers is domain_router._run_all_layers
    assert legacy_router._submit_and_poll is domain_router._submit_and_poll
    assert _router_snapshot(domain_router.router) == EXPECTED_SCRIPT_PIPELINE_ROUTES


def _router_snapshot(router):
    snapshot = []
    for route in router.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods or []):
                snapshot.append((method, route.path, route.name))
    return snapshot

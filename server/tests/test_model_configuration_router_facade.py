import importlib

import pytest
from fastapi.routing import APIRoute


EXPECTED_MODEL_CONFIGURATION_ROUTES = [
    ("GET", "/api/ai-models", "list_models"),
    ("GET", "/api/ai-models/options", "get_options"),
    ("GET", "/api/ai-models/schema", "get_schema"),
    ("GET", "/api/ai-models/{model_id}", "get_model"),
    ("POST", "/api/ai-models", "create_model"),
    ("PUT", "/api/ai-models/{model_id}", "update_model"),
    ("DELETE", "/api/ai-models/{model_id}", "delete_model"),
    ("POST", "/api/ai-models/{model_id}/test", "test_connection"),
]


def test_ai_config_legacy_router_module_is_domain_router_module():
    try:
        legacy_router = importlib.import_module("app.routers.ai_config")
        domain_router = importlib.import_module("app.domains.model_configuration.ai_models_router")
    except ModuleNotFoundError as exc:
        pytest.fail(f"model configuration domain router import failed: {exc}")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router
    assert legacy_router.DEFAULT_MODELS is domain_router.DEFAULT_MODELS
    assert legacy_router.seed_ai_models is domain_router.seed_ai_models
    assert legacy_router.httpx is domain_router.httpx
    assert _router_snapshot(domain_router.router) == EXPECTED_MODEL_CONFIGURATION_ROUTES


def _router_snapshot(router):
    snapshot = []
    for route in router.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods or []):
                snapshot.append((method, route.path, route.name))
    return snapshot

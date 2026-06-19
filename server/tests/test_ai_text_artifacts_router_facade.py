import importlib

import pytest
from fastapi.routing import APIRoute


EXPECTED_AI_TEXT_ARTIFACT_ROUTES = [
    ("GET", "/api/ai-text-artifacts", "list_artifacts"),
    ("GET", "/api/ai-text-artifacts/{artifact_id}", "get_artifact"),
    ("GET", "/api/ai-text-artifacts/{artifact_id}/lineage", "get_lineage"),
    ("POST", "/api/ai-text-artifacts/{artifact_id}/edit", "edit_artifact"),
    ("POST", "/api/ai-text-artifacts/{artifact_id}/approve", "approve_artifact"),
    ("POST", "/api/ai-text-artifacts/{artifact_id}/regenerate", "regenerate_artifact"),
]


def test_ai_text_artifacts_legacy_router_module_is_domain_router_module():
    try:
        legacy_router = importlib.import_module("app.routers.ai_text_artifacts")
        domain_router = importlib.import_module("app.domains.ai_text_artifacts.ai_text_artifacts_router")
    except ModuleNotFoundError as exc:
        pytest.fail(f"ai text artifacts domain router import failed: {exc}")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router
    assert legacy_router.ArtifactEditRequest is domain_router.ArtifactEditRequest
    assert legacy_router.ArtifactRegenerateRequest is domain_router.ArtifactRegenerateRequest
    assert legacy_router._artifact_dict is domain_router._artifact_dict
    assert _router_snapshot(domain_router.router) == EXPECTED_AI_TEXT_ARTIFACT_ROUTES


def _router_snapshot(router):
    snapshot = []
    for route in router.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods or []):
                snapshot.append((method, route.path, route.name))
    return snapshot

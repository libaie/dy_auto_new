import importlib

import pytest
from fastapi.routing import APIRoute


EXPECTED_AGENCY_OPERATIONS_ROUTES = [
    ("GET", "/api/agency/experts", "get_agency_experts"),
    ("GET", "/api/agency/experts/{expert_id}", "get_agency_expert"),
    ("GET", "/api/agency/invocations", "list_invocations"),
    ("GET", "/api/agency/invocations/{invocation_id}", "get_invocation"),
    ("GET", "/api/agency/creative-patches", "list_creative_patches"),
    ("PATCH", "/api/agency/creative-patches/{patch_id}", "update_creative_patch"),
    ("POST", "/api/agency/creative-patches/{patch_id}/approve", "approve_creative_patch_route"),
    ("POST", "/api/agency/creative-patches/{patch_id}/reject", "reject_creative_patch_route"),
    ("POST", "/api/agency/creative-patches/{patch_id}/apply", "apply_creative_patch_route"),
    ("POST", "/api/agency/creative-patches/apply-approved", "apply_approved_creative_patches_route"),
    ("POST", "/api/agency/assets/{asset_id}/multimodal-review", "run_asset_multimodal_review"),
    ("GET", "/api/agency/repair-tasks", "list_repair_tasks"),
    ("POST", "/api/agency/repair-tasks/{job_id}/retry", "retry_repair_task"),
    ("POST", "/api/agency/repair-tasks/{job_id}/authorize-retry", "authorize_paid_repair_retry"),
]


def test_agency_legacy_router_module_is_domain_router_module():
    try:
        legacy_router = importlib.import_module("app.routers.agency")
        domain_router = importlib.import_module("app.domains.agency_operations.agency_router")
    except ModuleNotFoundError as exc:
        pytest.fail(f"agency operations domain router import failed: {exc}")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router
    assert legacy_router._redact_model_config_snapshot is domain_router._redact_model_config_snapshot
    assert legacy_router._repair_retry_actions is domain_router._repair_retry_actions
    assert _router_snapshot(domain_router.router) == EXPECTED_AGENCY_OPERATIONS_ROUTES


def _router_snapshot(router):
    snapshot = []
    for route in router.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods or []):
                snapshot.append((method, route.path, route.name))
    return snapshot

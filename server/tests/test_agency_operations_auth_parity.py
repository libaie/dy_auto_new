from fastapi.routing import APIRoute

from app.main import app


EXPECTED_AGENCY_OPERATIONS_HTTP_ROUTES = [
    (
        "/api/agency/experts",
        ("GET",),
        "get_agency_experts",
        "app.domains.agency_operations.agency_router.get_agency_experts",
        ("verify_admin_token",),
    ),
    (
        "/api/agency/experts/{expert_id}",
        ("GET",),
        "get_agency_expert",
        "app.domains.agency_operations.agency_router.get_agency_expert",
        ("checker",),
    ),
    (
        "/api/agency/invocations",
        ("GET",),
        "list_invocations",
        "app.domains.agency_operations.agency_router.list_invocations",
        ("get_db", "checker"),
    ),
    (
        "/api/agency/invocations/{invocation_id}",
        ("GET",),
        "get_invocation",
        "app.domains.agency_operations.agency_router.get_invocation",
        ("get_db", "checker"),
    ),
    (
        "/api/agency/creative-patches",
        ("GET",),
        "list_creative_patches",
        "app.domains.agency_operations.agency_router.list_creative_patches",
        ("get_db", "checker"),
    ),
    (
        "/api/agency/creative-patches/{patch_id}",
        ("PATCH",),
        "update_creative_patch",
        "app.domains.agency_operations.agency_router.update_creative_patch",
        ("get_db", "checker"),
    ),
    (
        "/api/agency/creative-patches/{patch_id}/approve",
        ("POST",),
        "approve_creative_patch_route",
        "app.domains.agency_operations.agency_router.approve_creative_patch_route",
        ("get_db", "checker"),
    ),
    (
        "/api/agency/creative-patches/{patch_id}/reject",
        ("POST",),
        "reject_creative_patch_route",
        "app.domains.agency_operations.agency_router.reject_creative_patch_route",
        ("get_db", "checker"),
    ),
    (
        "/api/agency/creative-patches/{patch_id}/apply",
        ("POST",),
        "apply_creative_patch_route",
        "app.domains.agency_operations.agency_router.apply_creative_patch_route",
        ("get_db", "checker"),
    ),
    (
        "/api/agency/creative-patches/apply-approved",
        ("POST",),
        "apply_approved_creative_patches_route",
        "app.domains.agency_operations.agency_router.apply_approved_creative_patches_route",
        ("get_db", "checker"),
    ),
    (
        "/api/agency/assets/{asset_id}/multimodal-review",
        ("POST",),
        "run_asset_multimodal_review",
        "app.domains.agency_operations.agency_router.run_asset_multimodal_review",
        ("get_db", "checker"),
    ),
    (
        "/api/agency/repair-tasks",
        ("GET",),
        "list_repair_tasks",
        "app.domains.agency_operations.agency_router.list_repair_tasks",
        ("get_db", "checker"),
    ),
    (
        "/api/agency/repair-tasks/{job_id}/retry",
        ("POST",),
        "retry_repair_task",
        "app.domains.agency_operations.agency_router.retry_repair_task",
        ("get_db", "checker"),
    ),
    (
        "/api/agency/repair-tasks/{job_id}/authorize-retry",
        ("POST",),
        "authorize_paid_repair_retry",
        "app.domains.agency_operations.agency_router.authorize_paid_repair_retry",
        ("get_db", "checker"),
    ),
]


def test_agency_operations_route_table_snapshot():
    assert _agency_operations_http_routes() == EXPECTED_AGENCY_OPERATIONS_HTTP_ROUTES


def _agency_operations_http_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/agency"):
            endpoint = f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
            dependency_names = tuple(
                getattr(dep.call, "__name__", repr(dep.call))
                for dep in route.dependant.dependencies
                if dep.call
            )
            routes.append((route.path, tuple(sorted(route.methods)), route.name, endpoint, dependency_names))
    return routes

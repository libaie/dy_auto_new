from fastapi.routing import APIRoute

from app.main import app


EXPECTED_AI_TEXT_ARTIFACT_HTTP_ROUTES = [
    (
        "/api/ai-text-artifacts",
        ("GET",),
        "list_artifacts",
        "app.domains.ai_text_artifacts.ai_text_artifacts_router.list_artifacts",
        ("get_db", "verify_admin_token"),
    ),
    (
        "/api/ai-text-artifacts/{artifact_id}",
        ("GET",),
        "get_artifact",
        "app.domains.ai_text_artifacts.ai_text_artifacts_router.get_artifact",
        ("get_db", "verify_admin_token"),
    ),
    (
        "/api/ai-text-artifacts/{artifact_id}/lineage",
        ("GET",),
        "get_lineage",
        "app.domains.ai_text_artifacts.ai_text_artifacts_router.get_lineage",
        ("get_db", "verify_admin_token"),
    ),
    (
        "/api/ai-text-artifacts/{artifact_id}/edit",
        ("POST",),
        "edit_artifact",
        "app.domains.ai_text_artifacts.ai_text_artifacts_router.edit_artifact",
        ("get_db", "checker"),
    ),
    (
        "/api/ai-text-artifacts/{artifact_id}/approve",
        ("POST",),
        "approve_artifact",
        "app.domains.ai_text_artifacts.ai_text_artifacts_router.approve_artifact",
        ("get_db", "checker"),
    ),
    (
        "/api/ai-text-artifacts/{artifact_id}/regenerate",
        ("POST",),
        "regenerate_artifact",
        "app.domains.ai_text_artifacts.ai_text_artifacts_router.regenerate_artifact",
        ("get_db", "checker"),
    ),
]


def test_ai_text_artifacts_route_table_snapshot():
    assert _ai_text_artifact_http_routes() == EXPECTED_AI_TEXT_ARTIFACT_HTTP_ROUTES


def _ai_text_artifact_http_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/ai-text-artifacts"):
            endpoint = f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
            dependency_names = tuple(
                getattr(dep.call, "__name__", repr(dep.call))
                for dep in route.dependant.dependencies
                if dep.call
            )
            routes.append((route.path, tuple(sorted(route.methods)), route.name, endpoint, dependency_names))
    return routes

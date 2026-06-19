from fastapi.routing import APIRoute

from app.main import app


EXPECTED_SCRIPT_PIPELINE_HTTP_ROUTES = [
    (
        "/api/pipeline/start",
        ("POST",),
        "pipeline_start",
        "app.domains.script_pipeline.pipeline_router.pipeline_start",
        ("get_db", "checker"),
    ),
    (
        "/api/pipeline/runs/{series_id}",
        ("GET",),
        "list_pipeline_runs",
        "app.domains.script_pipeline.pipeline_router.list_pipeline_runs",
        ("get_db", "checker"),
    ),
    (
        "/api/pipeline/runs/by-id/{run_id}",
        ("GET",),
        "get_pipeline_run_by_id",
        "app.domains.script_pipeline.pipeline_router.get_pipeline_run_by_id",
        ("get_db", "checker"),
    ),
    (
        "/api/pipeline/runs/{series_id}/{run_id}",
        ("GET",),
        "get_pipeline_run",
        "app.domains.script_pipeline.pipeline_router.get_pipeline_run",
        ("get_db", "checker"),
    ),
]


def test_script_pipeline_route_table_snapshot():
    assert _script_pipeline_http_routes() == EXPECTED_SCRIPT_PIPELINE_HTTP_ROUTES


def _script_pipeline_http_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/pipeline"):
            endpoint = f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
            dependency_names = tuple(
                getattr(dep.call, "__name__", repr(dep.call))
                for dep in route.dependant.dependencies
                if dep.call
            )
            routes.append((route.path, tuple(sorted(route.methods)), route.name, endpoint, dependency_names))
    return routes

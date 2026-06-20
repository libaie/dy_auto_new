from fastapi.routing import APIRoute

from app.main import app


EXPECTED_VIDEO_PRODUCTION_ROUTES = [
    ("POST", "/api/video-production/runs", "create_run"),
    ("POST", "/api/video-production/runs/start", "start_run"),
    ("POST", "/api/video-production/one-sentence", "one_sentence_video"),
    ("GET", "/api/video-production/runs/{run_id}", "get_run"),
    ("POST", "/api/video-production/runs/{run_id}/backfill-text-artifacts", "backfill_run_text_artifacts"),
    ("POST", "/api/video-production/runs/{run_id}/mock-worker-step", "mock_worker_step"),
    ("POST", "/api/video-production/runs/{run_id}/worker-step", "real_worker_step"),
    ("GET", "/api/video-production/runs/{run_id}/readiness", "get_run_readiness"),
    ("GET", "/api/video-production/runs/{run_id}/provider-stage-tasks", "get_provider_stage_tasks"),
    ("GET", "/api/video-production/plans/{plan_id}/tree", "get_production_plan_tree"),
    ("GET", "/api/video-production/runs/{run_id}/tree", "get_production_run_tree"),
    ("GET", "/api/video-production/runs/{run_id}/costs", "run_costs"),
    ("GET", "/api/video-production/segments/{segment_id}/detail", "segment_detail"),
    ("GET", "/api/video-production/segments/{segment_id}/retry-impact", "segment_retry_impact"),
    ("POST", "/api/video-production/runs/{run_id}/pause", "pause_run"),
    ("POST", "/api/video-production/runs/{run_id}/resume", "resume_run"),
    ("GET", "/api/video-production/review-items", "review_items"),
    ("POST", "/api/video-production/assets/{asset_id}/review", "review_asset"),
    ("POST", "/api/video-production/assets/{asset_id}/void", "void_asset"),
    ("POST", "/api/video-production/assets/{asset_id}/image-edit", "image_edit_asset"),
    ("POST", "/api/video-production/assets/{asset_id}/persist-retry", "retry_asset_persistence"),
    ("POST", "/api/video-production/segments/{segment_id}/retry", "retry_production_segment"),
    ("POST", "/api/video-production/reviews/bulk-action", "bulk_review_action"),
    ("POST", "/api/video-production/collections", "create_collection"),
    ("POST", "/api/video-production/runs/{run_id}/start-images", "start_images"),
    ("POST", "/api/video-production/runs/{run_id}/sync-image-results", "sync_images"),
    ("POST", "/api/video-production/runs/{run_id}/start-videos", "start_videos"),
    ("POST", "/api/video-production/runs/{run_id}/sync-video-results", "sync_videos"),
    ("POST", "/api/video-production/runs/{run_id}/compose", "compose_run"),
    ("POST", "/api/video-production/runs/{run_id}/sync-compose-results", "sync_compose"),
    ("POST", "/api/video-production/assets/{asset_id}/regenerate", "regenerate_asset"),
    ("POST", "/api/video-production/assets/{asset_id}/start-regeneration", "start_regeneration"),
    ("POST", "/api/video-production/assets/{asset_id}/sync-regeneration", "sync_regeneration"),
]


def test_video_production_route_table_snapshot():
    assert _video_production_route_triples() == EXPECTED_VIDEO_PRODUCTION_ROUTES


def test_video_production_route_auth_and_endpoint_modules():
    for route in _video_production_http_routes():
        path, _methods, name, endpoint, dependency_names = route

        assert endpoint == f"app.domains.video_production.video_production_router.{name}", path
        assert dependency_names == ("get_db", "checker"), path


def _video_production_route_triples():
    return [
        (methods[0], path, name)
        for path, methods, name, _endpoint, _dependencies in _video_production_http_routes()
    ]


def _video_production_http_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/video-production"):
            endpoint = f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
            dependency_names = tuple(
                getattr(dep.call, "__name__", repr(dep.call))
                for dep in route.dependant.dependencies
                if dep.call
            )
            routes.append((route.path, tuple(sorted(route.methods)), route.name, endpoint, dependency_names))
    return routes

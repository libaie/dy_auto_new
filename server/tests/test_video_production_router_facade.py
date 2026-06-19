import importlib

import pytest
from fastapi.routing import APIRoute


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


def test_video_production_legacy_router_module_is_domain_router_module():
    try:
        legacy_router = importlib.import_module("app.routers.video_production")
        domain_router = importlib.import_module("app.domains.video_production.video_production_router")
    except ModuleNotFoundError as exc:
        pytest.fail(f"video production domain router import failed: {exc}")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router
    assert legacy_router.StartRunRequest is domain_router.StartRunRequest
    assert legacy_router.OneSentenceVideoRequest is domain_router.OneSentenceVideoRequest
    assert legacy_router._run_payload is domain_router._run_payload
    assert legacy_router._asset_payload is domain_router._asset_payload
    assert legacy_router.edit_image_asset is domain_router.edit_image_asset
    assert _router_snapshot(domain_router.router) == EXPECTED_VIDEO_PRODUCTION_ROUTES


def _router_snapshot(router):
    snapshot = []
    for route in router.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods or []):
                snapshot.append((method, route.path, route.name))
    return snapshot

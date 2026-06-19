import importlib

import pytest
from fastapi.routing import APIRoute


EXPECTED_STORYBOARD_IMAGE_ROUTES = [
    ("POST", "/api/storyboard-images/episodes/{episode_id}/frames/{frame_id}/tasks", "create_frame_task"),
    ("POST", "/api/storyboard-images/episodes/{episode_id}/tasks:batch", "create_missing_tasks"),
    ("GET", "/api/storyboard-images/episodes/{episode_id}", "read_storyboard_images"),
    ("POST", "/api/storyboard-images/assets/{asset_id}/promote", "promote_asset"),
]


def test_storyboard_images_legacy_router_module_is_domain_router_module():
    try:
        legacy_router = importlib.import_module("app.routers.storyboard_images")
        domain_router = importlib.import_module("app.domains.storyboard_images.storyboard_images_router")
    except ModuleNotFoundError as exc:
        pytest.fail(f"storyboard images domain router import failed: {exc}")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router
    assert legacy_router.StoryboardImageTaskRequest is domain_router.StoryboardImageTaskRequest
    assert legacy_router.PromoteStoryboardImageRequest is domain_router.PromoteStoryboardImageRequest
    assert legacy_router._auth_user_id is domain_router._auth_user_id
    assert _router_snapshot(domain_router.router) == EXPECTED_STORYBOARD_IMAGE_ROUTES


def _router_snapshot(router):
    snapshot = []
    for route in router.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods or []):
                snapshot.append((method, route.path, route.name))
    return snapshot

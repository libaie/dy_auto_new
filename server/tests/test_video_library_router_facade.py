import importlib

import pytest
from fastapi.routing import APIRoute


EXPECTED_VIDEO_LIBRARY_ROUTES = [
    ("GET", "/api/videos", "list_videos"),
    ("GET", "/api/videos/{video_id}", "get_video"),
    ("GET", "/api/videos/{video_id}/download", "download_video"),
    ("DELETE", "/api/videos/{video_id}", "delete_video"),
]


def test_videos_legacy_router_module_is_domain_router_module():
    try:
        legacy_router = importlib.import_module("app.routers.videos")
        domain_router = importlib.import_module("app.domains.video_library.videos_router")
    except ModuleNotFoundError as exc:
        pytest.fail(f"video library domain router import failed: {exc}")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router
    assert _router_snapshot(domain_router.router) == EXPECTED_VIDEO_LIBRARY_ROUTES


def _router_snapshot(router):
    snapshot = []
    for route in router.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods or []):
                snapshot.append((method, route.path, route.name))
    return snapshot

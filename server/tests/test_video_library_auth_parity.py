from fastapi.routing import APIRoute

from app.main import app


EXPECTED_VIDEO_LIBRARY_HTTP_ROUTES = [
    (
        "/api/videos",
        ("GET",),
        "list_videos",
        "app.domains.video_library.videos_router.list_videos",
        ("get_db", "verify_admin_token"),
    ),
    (
        "/api/videos/{video_id}",
        ("GET",),
        "get_video",
        "app.domains.video_library.videos_router.get_video",
        ("get_db", "verify_admin_token"),
    ),
    (
        "/api/videos/{video_id}/download",
        ("GET",),
        "download_video",
        "app.domains.video_library.videos_router.download_video",
        ("get_db",),
    ),
    (
        "/api/videos/{video_id}",
        ("DELETE",),
        "delete_video",
        "app.domains.video_library.videos_router.delete_video",
        ("get_db", "verify_admin_token"),
    ),
]


def test_video_library_route_table_snapshot():
    assert _video_library_http_routes() == EXPECTED_VIDEO_LIBRARY_HTTP_ROUTES


def _video_library_http_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/videos"):
            endpoint = f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
            dependency_names = tuple(
                getattr(dep.call, "__name__", repr(dep.call))
                for dep in route.dependant.dependencies
                if dep.call
            )
            routes.append((route.path, tuple(sorted(route.methods)), route.name, endpoint, dependency_names))
    return routes

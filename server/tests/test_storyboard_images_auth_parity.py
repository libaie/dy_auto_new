from fastapi.routing import APIRoute

from app.main import app


EXPECTED_STORYBOARD_IMAGE_HTTP_ROUTES = [
    (
        "/api/storyboard-images/episodes/{episode_id}/frames/{frame_id}/tasks",
        ("POST",),
        "create_frame_task",
        "app.domains.storyboard_images.storyboard_images_router.create_frame_task",
        ("get_db", "checker"),
    ),
    (
        "/api/storyboard-images/episodes/{episode_id}/tasks:batch",
        ("POST",),
        "create_missing_tasks",
        "app.domains.storyboard_images.storyboard_images_router.create_missing_tasks",
        ("get_db", "checker"),
    ),
    (
        "/api/storyboard-images/episodes/{episode_id}",
        ("GET",),
        "read_storyboard_images",
        "app.domains.storyboard_images.storyboard_images_router.read_storyboard_images",
        ("get_db", "checker"),
    ),
    (
        "/api/storyboard-images/assets/{asset_id}/promote",
        ("POST",),
        "promote_asset",
        "app.domains.storyboard_images.storyboard_images_router.promote_asset",
        ("get_db", "checker"),
    ),
]


def test_storyboard_images_route_table_snapshot():
    assert _storyboard_image_http_routes() == EXPECTED_STORYBOARD_IMAGE_HTTP_ROUTES


def _storyboard_image_http_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/storyboard-images"):
            endpoint = f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
            dependency_names = tuple(
                getattr(dep.call, "__name__", repr(dep.call))
                for dep in route.dependant.dependencies
                if dep.call
            )
            routes.append((route.path, tuple(sorted(route.methods)), route.name, endpoint, dependency_names))
    return routes

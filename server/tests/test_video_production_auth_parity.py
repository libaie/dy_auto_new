from fastapi.routing import APIRoute

from app.main import app

from tests.test_video_production_router_facade import EXPECTED_VIDEO_PRODUCTION_ROUTES


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

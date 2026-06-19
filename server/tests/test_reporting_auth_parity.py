from fastapi.routing import APIRoute

from app.main import app


EXPECTED_REPORTING_HTTP_ROUTES = [
    (
        "/api/stats/dashboard",
        ("GET",),
        "dashboard_summary",
        "app.domains.reporting.stats_router.dashboard_summary",
        ("get_db", "verify_admin_token"),
    ),
    (
        "/api/stats/daily",
        ("GET",),
        "daily_stats",
        "app.domains.reporting.stats_router.daily_stats",
        ("get_db", "verify_admin_token"),
    ),
    (
        "/api/stats/accounts/{account_id}",
        ("GET",),
        "account_stats",
        "app.domains.reporting.stats_router.account_stats",
        ("get_db", "verify_admin_token"),
    ),
    (
        "/api/stats/realtime",
        ("GET",),
        "realtime_stats",
        "app.domains.reporting.stats_router.realtime_stats",
        ("get_db", "verify_admin_token"),
    ),
]


def test_reporting_route_table_snapshot():
    assert _reporting_http_routes() == EXPECTED_REPORTING_HTTP_ROUTES


def _reporting_http_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/stats"):
            endpoint = f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
            dependency_names = tuple(
                getattr(dep.call, "__name__", repr(dep.call))
                for dep in route.dependant.dependencies
                if dep.call
            )
            routes.append((route.path, tuple(sorted(route.methods)), route.name, endpoint, dependency_names))
    return routes

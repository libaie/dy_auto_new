import importlib


EXPECTED_SERIES_ROUTER_SNAPSHOT = [
    ("POST", "/api/series/{series_id}/auto-generate"),
    ("GET", "/api/series"),
    ("GET", "/api/series/{series_id}/style-lock"),
    ("GET", "/api/series/{series_id}/agency-console"),
    ("POST", "/api/series/style-lock/worker-step"),
    ("POST", "/api/series/story-plan/worker-step"),
    ("POST", "/api/series/{series_id}/style-lock"),
    ("POST", "/api/series"),
    ("GET", "/api/series/{series_id}"),
    ("POST", "/api/series/{series_id}/ensure-episodes"),
    ("POST", "/api/series/{series_id}/story-plan"),
    ("PUT", "/api/series/{series_id}"),
    ("DELETE", "/api/series/{series_id}"),
    ("POST", "/api/series/{series_id}/characters/{character_id}"),
    ("DELETE", "/api/series/{series_id}/characters/{character_id}"),
    ("POST", "/api/series/{series_id}/scenes/{scene_id}"),
    ("DELETE", "/api/series/{series_id}/scenes/{scene_id}"),
    ("POST", "/api/series/{series_id}/episodes/{episode_id}/script"),
    ("PUT", "/api/series/{series_id}/episodes/{episode_id}"),
]


def _router_snapshot(router):
    snapshot = []
    for route in router.routes:
        path = getattr(route, "path", "")
        for method in sorted(getattr(route, "methods", []) or []):
            snapshot.append((method, path))
    return snapshot


def test_domain_router_matches_existing_series_route_snapshot():
    domain_router = importlib.import_module("app.domains.ai_video_series.router")

    assert _router_snapshot(domain_router.router) == EXPECTED_SERIES_ROUTER_SNAPSHOT


def test_legacy_series_router_module_is_domain_router_module():
    legacy_router = importlib.import_module("app.routers.series")
    domain_router = importlib.import_module("app.domains.ai_video_series.router")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router


def test_legacy_monkeypatch_paths_share_domain_globals():
    legacy_router = importlib.import_module("app.routers.series")
    domain_router = importlib.import_module("app.domains.ai_video_series.router")

    assert legacy_router._run_style_lock_job.__globals__ is domain_router.__dict__
    assert legacy_router._run_story_plan_worker_step.__globals__ is domain_router.__dict__
    assert legacy_router._fill_reference_assets.__globals__ is domain_router.__dict__

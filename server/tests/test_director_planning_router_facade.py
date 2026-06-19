import importlib

import pytest
from fastapi.routing import APIRoute


EXPECTED_DIRECTOR_PLANNING_ROUTES = [
    ("POST", "/api/director/auto-plan", "auto_plan_episode"),
    ("POST", "/api/director/episode-production-plan", "create_episode_production_plan_endpoint"),
    ("POST", "/api/director/episode-plan", "create_episode_plan_endpoint"),
    ("POST", "/api/director/shot-segments", "create_shot_segments_endpoint"),
    ("POST", "/api/director/plan", "build_plan"),
]


def test_director_legacy_router_module_is_domain_router_module():
    try:
        legacy_router = importlib.import_module("app.routers.director")
        domain_router = importlib.import_module("app.domains.director_planning.director_router")
    except ModuleNotFoundError as exc:
        pytest.fail(f"director planning domain router import failed: {exc}")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router
    assert legacy_router.generate_auto_storyboard is domain_router.generate_auto_storyboard
    assert legacy_router._normalize_auto_frames is domain_router._normalize_auto_frames
    assert legacy_router.ai_generator is domain_router.ai_generator
    assert legacy_router.AgencyOrchestrator is domain_router.AgencyOrchestrator
    assert _router_snapshot(domain_router.router) == EXPECTED_DIRECTOR_PLANNING_ROUTES


def _router_snapshot(router):
    snapshot = []
    for route in router.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods or []):
                snapshot.append((method, route.path, route.name))
    return snapshot

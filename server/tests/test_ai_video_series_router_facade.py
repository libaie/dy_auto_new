import importlib
from pathlib import Path

from fastapi.testclient import TestClient

from app.db.models.ai_video_series import Series
from app.main import app


REPO_ROOT = Path(__file__).resolve().parents[2]


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


def test_legacy_private_helper_names_alias_owning_modules():
    legacy_router = importlib.import_module("app.routers.series")
    story_planning = importlib.import_module("app.domains.ai_video_series.story_planning")
    style_lock = importlib.import_module("app.domains.ai_video_series.style_lock")

    assert legacy_router._run_style_lock_job is style_lock.run_style_lock_job
    assert legacy_router._run_style_lock_worker_step is style_lock.run_style_lock_worker_step
    assert legacy_router._run_story_plan_worker_step is story_planning.run_story_plan_worker_step
    assert legacy_router._fill_reference_assets is style_lock.fill_reference_assets


def test_legacy_auto_asset_generation_facade_aliases_style_lock_dependencies():
    legacy_router = importlib.import_module("app.routers.series")
    style_lock = importlib.import_module("app.domains.ai_video_series.style_lock")

    assert legacy_router.ai_generator is style_lock.ai_generator
    assert (
        legacy_router.AUTO_GENERATE_ASSET_MODEL_TIMEOUT_SECONDS
        == style_lock.AUTO_GENERATE_ASSET_MODEL_TIMEOUT_SECONDS
    )


def test_auto_generate_endpoint_uses_facade_ai_generator_timeout(db, monkeypatch):
    from app.routers import series as series_router

    series = Series(
        title="City Healer",
        logline="A young doctor solves urban mysteries with a consistent cyber-noir style.",
        genre="drama",
    )
    db.add(series)
    db.commit()

    calls = []

    async def fake_generate_custom(_db, _system_prompt, _user_prompt, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return """
            {
              "characters": [
                {
                  "name": "Lin",
                  "role_type": "protagonist",
                  "gender": "female",
                  "age_range": "25-30",
                  "personality": "Focused and kind.",
                  "appearance_desc": "Short black hair and sharp eyes.",
                  "outfit_desc": "Gray coat."
                }
              ]
            }
            """
        return """
        {
          "scenes": [
            {
              "name": "Rain Clinic",
              "scene_type": "indoor",
              "location_desc": "Small clinic with neon reflections.",
              "lighting": "night",
              "mood": "mysterious"
            }
          ]
        }
        """

    monkeypatch.setattr(series_router.ai_generator, "generate_custom", fake_generate_custom)

    response = TestClient(app).post(f"/api/series/{series.id}/auto-generate")

    assert response.status_code == 200
    assert [call["request_timeout_seconds"] for call in calls] == [
        series_router.AUTO_GENERATE_ASSET_MODEL_TIMEOUT_SECONDS,
        series_router.AUTO_GENERATE_ASSET_MODEL_TIMEOUT_SECONDS,
    ]


def test_router_facade_cleanup_gates_are_documented():
    readme = (REPO_ROOT / "server/app/domains/ai_video_series/README.md").read_text(encoding="utf-8")

    assert "Compatibility Cleanup Gates" in readme
    assert "Do not remove `app.routers.series` until all of these are true" in readme

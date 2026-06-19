import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-ai-video-series-planning-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-ai-video-series-planning-service-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/ai_video_series/series_planning_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/series_planning_service.py"
DOMAIN_ROUTER_PATH = REPO_ROOT / "server/app/domains/ai_video_series/router.py"
DOMAIN_STORY_PLANNING_PATH = REPO_ROOT / "server/app/domains/ai_video_series/story_planning.py"
README_PATH = REPO_ROOT / "server/app/domains/ai_video_series/README.md"


def test_ai_video_series_planning_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.ai_video_series.series_planning_service",
        "app.services.series_planning_service",
        "generate_series_story_plan",
        "ensure_episode_placeholders",
        "ensure_series_continuity_artifacts",
        "generate_story_plan_with_expert",
    ]:
        assert term in spec
        assert term in plan


def test_ai_video_series_planning_service_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_series_planning_service_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.ai_video_series" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def ensure_episode_placeholders" not in text
    assert "async def generate_series_story_plan" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_series_planning_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.series_planning_service")
        domain = importlib.import_module("app.domains.ai_video_series.series_planning_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"series planning service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.EpisodePlaceholderResult is domain.EpisodePlaceholderResult
    assert legacy.ContinuityArtifactResult is domain.ContinuityArtifactResult
    assert legacy.SeriesStoryPlanResult is domain.SeriesStoryPlanResult
    assert legacy.ensure_episode_placeholders is domain.ensure_episode_placeholders
    assert legacy.ensure_series_continuity_artifacts is domain.ensure_series_continuity_artifacts
    assert legacy.generate_series_story_plan is domain.generate_series_story_plan
    assert legacy.generate_story_plan_with_expert is domain.generate_story_plan_with_expert


def test_ai_video_series_domain_modules_import_domain_service_path():
    for path in [DOMAIN_ROUTER_PATH, DOMAIN_STORY_PLANNING_PATH]:
        text = path.read_text(encoding="utf-8")

        assert "app.domains.ai_video_series.series_planning_service" in text
        assert "app.services.series_planning_service" not in text


def test_ai_video_series_readme_registers_series_planning_service_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.series_planning_service" in text
    assert "app.domains.ai_video_series.series_planning_service" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-ai-video-series-story-generator-expert-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-ai-video-series-story-generator-expert-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/ai_video_series/story_generator_expert.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/story_generator_expert.py"
DOMAIN_SERIES_PLANNING_PATH = REPO_ROOT / "server/app/domains/ai_video_series/series_planning_service.py"
README_PATH = REPO_ROOT / "server/app/domains/ai_video_series/README.md"


def test_story_generator_expert_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.ai_video_series.story_generator_expert",
        "app.services.story_generator_expert",
        "generate_story_plan_with_expert",
        "StoryGeneratorResult",
    ]:
        assert term in spec
        assert term in plan


def test_story_generator_expert_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_story_generator_expert_service_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.ai_video_series" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "async def generate_story_plan_with_expert" not in text
    assert "class StoryGeneratorResult" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_story_generator_expert_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.story_generator_expert")
        domain = importlib.import_module("app.domains.ai_video_series.story_generator_expert")
    except ModuleNotFoundError as exc:
        pytest.fail(f"story generator expert domain import failed: {exc}")

    assert legacy is domain
    assert legacy.StoryGeneratorResult is domain.StoryGeneratorResult
    assert legacy.StoryModelClient is domain.StoryModelClient
    assert legacy.STORY_GENERATOR_EXPERT_ID is domain.STORY_GENERATOR_EXPERT_ID
    assert legacy.STORY_PLAN_OUTPUT_SCHEMA is domain.STORY_PLAN_OUTPUT_SCHEMA
    assert legacy.generate_story_plan_with_expert is domain.generate_story_plan_with_expert


def test_series_planning_service_imports_story_generator_expert_domain_path():
    text = DOMAIN_SERIES_PLANNING_PATH.read_text(encoding="utf-8")

    assert "app.domains.ai_video_series.story_generator_expert" in text
    assert "app.services.story_generator_expert" not in text


def test_ai_video_series_readme_registers_story_generator_expert_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.story_generator_expert" in text
    assert "app.domains.ai_video_series.story_generator_expert" in text
    assert 'rg "app\\.services\\.story_generator_expert" server/app server/tests' in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

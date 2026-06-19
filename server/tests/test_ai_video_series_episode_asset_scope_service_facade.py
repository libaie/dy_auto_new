import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-ai-video-series-episode-asset-scope-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-ai-video-series-episode-asset-scope-service-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/ai_video_series/episode_asset_scope_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/episode_asset_scope_service.py"
SERIES_PLANNING_SERVICE_PATH = REPO_ROOT / "server/app/domains/ai_video_series/series_planning_service.py"
README_PATH = REPO_ROOT / "server/app/domains/ai_video_series/README.md"


def test_episode_asset_scope_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.ai_video_series.episode_asset_scope_service",
        "app.services.episode_asset_scope_service",
        "EpisodeAssetScopeError",
        "normalize_episode_asset_scope",
    ]:
        assert term in spec
        assert term in plan


def test_episode_asset_scope_service_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_episode_asset_scope_service_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.ai_video_series" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def normalize_episode_asset_scope" not in text
    assert "class EpisodeAssetScopeError" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_episode_asset_scope_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.episode_asset_scope_service")
        domain = importlib.import_module("app.domains.ai_video_series.episode_asset_scope_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"episode asset scope service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.EpisodeAssetScopeError is domain.EpisodeAssetScopeError
    assert legacy.normalize_episode_asset_scope is domain.normalize_episode_asset_scope


def test_series_planning_service_imports_domain_episode_asset_scope_service():
    text = SERIES_PLANNING_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.ai_video_series.episode_asset_scope_service" in text
    assert "app.services.episode_asset_scope_service" not in text


def test_ai_video_series_readme_registers_episode_asset_scope_service_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.episode_asset_scope_service" in text
    assert "app.domains.ai_video_series.episode_asset_scope_service" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

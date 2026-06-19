import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-ai-text-artifact-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-ai-text-artifact-service-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/ai_text_artifacts/ai_text_artifact_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/ai_text_artifact_service.py"
README_PATH = REPO_ROOT / "server/app/domains/ai_text_artifacts/README.md"
DOMAIN_IMPORT_PATHS = [
    REPO_ROOT / "server/app/domains/ai_text_artifacts/ai_text_artifacts_router.py",
    REPO_ROOT / "server/app/domains/ai_video_series/artifacts.py",
    REPO_ROOT / "server/app/domains/ai_video_series/read_models.py",
    REPO_ROOT / "server/app/domains/ai_video_series/series_planning_service.py",
    REPO_ROOT / "server/app/domains/ai_video_series/style_lock.py",
    REPO_ROOT / "server/app/domains/director_planning/director_router.py",
    REPO_ROOT / "server/app/domains/video_production/video_production_router.py",
]


def test_ai_text_artifact_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.ai_text_artifacts.ai_text_artifact_service",
        "app.services.ai_text_artifact_service",
        "AITextArtifactService",
        "ARTIFACT_CONSUMPTION_ORDER",
    ]:
        assert term in spec
        assert term in plan


def test_ai_text_artifact_service_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_ai_text_artifact_service_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.ai_text_artifacts" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "class AITextArtifactService" not in text
    assert "def create_artifact" not in text
    assert "def approve_artifact" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_ai_text_artifact_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.ai_text_artifact_service")
        domain = importlib.import_module("app.domains.ai_text_artifacts.ai_text_artifact_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"ai text artifact service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.AITextArtifactService is domain.AITextArtifactService
    assert legacy.SERIES_RUN_ARTIFACT_TYPES is domain.SERIES_RUN_ARTIFACT_TYPES
    assert legacy.EPISODE_RUN_ARTIFACT_TYPES is domain.EPISODE_RUN_ARTIFACT_TYPES
    assert legacy.ARTIFACT_CONSUMPTION_ORDER is domain.ARTIFACT_CONSUMPTION_ORDER


def test_domain_modules_import_ai_text_artifact_service_domain_path():
    for path in DOMAIN_IMPORT_PATHS:
        text = path.read_text(encoding="utf-8")

        assert "app.domains.ai_text_artifacts.ai_text_artifact_service" in text, path
        assert "app.services.ai_text_artifact_service" not in text, path


def test_ai_text_artifacts_readme_registers_service_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.ai_text_artifact_service" in text
    assert "app.domains.ai_text_artifacts.ai_text_artifact_service" in text
    assert 'rg "app\\.services\\.ai_text_artifact_service" server/app server/tests' in text
    assert "AITextArtifactService" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

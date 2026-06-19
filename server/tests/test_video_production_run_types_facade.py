import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-run-types-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-run-types-domain-plan.md"
DOMAIN_RUN_TYPES_PATH = REPO_ROOT / "server/app/domains/video_production/video_production_run_types.py"
LEGACY_RUN_TYPES_PATH = REPO_ROOT / "server/app/services/video_production_run_types.py"
ROUTER_PATH = REPO_ROOT / "server/app/domains/video_production/video_production_router.py"
REVIEW_SERVICE_PATH = REPO_ROOT / "server/app/domains/video_production/production_review_service.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_run_types_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.video_production_run_types",
        "app.services.video_production_run_types",
        "REAL_SHORT_E2E",
        "MOCK_SERIES_SCALE",
        "LEGACY_EPISODE_RUN",
        "validate_run_type",
        "assert_run_type",
        "is_mock_scale_run",
    ]:
        assert term in spec
        assert term in plan


def test_video_production_run_types_domain_file_exists():
    assert DOMAIN_RUN_TYPES_PATH.exists()


def test_legacy_video_production_run_types_is_thin_facade():
    text = LEGACY_RUN_TYPES_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "REAL_SHORT_E2E =" not in text
    assert "MOCK_SERIES_SCALE =" not in text
    assert "def validate_run_type" not in text
    assert "def assert_run_type" not in text
    assert _line_count(LEGACY_RUN_TYPES_PATH) <= 20


def test_legacy_video_production_run_types_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.video_production_run_types")
        domain = importlib.import_module("app.domains.video_production.video_production_run_types")
    except ModuleNotFoundError as exc:
        pytest.fail(f"video production run types domain import failed: {exc}")

    assert legacy is domain
    assert legacy.REAL_SHORT_E2E is domain.REAL_SHORT_E2E
    assert legacy.MOCK_SERIES_SCALE is domain.MOCK_SERIES_SCALE
    assert legacy.LEGACY_EPISODE_RUN is domain.LEGACY_EPISODE_RUN
    assert legacy.ALLOWED_RUN_TYPES is domain.ALLOWED_RUN_TYPES
    assert legacy.validate_run_type is domain.validate_run_type
    assert legacy.assert_run_type is domain.assert_run_type
    assert legacy.is_real_provider_run is domain.is_real_provider_run
    assert legacy.is_mock_scale_run is domain.is_mock_scale_run


def test_video_production_domain_modules_import_domain_run_types():
    router = ROUTER_PATH.read_text(encoding="utf-8")
    review_service = REVIEW_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production.video_production_run_types" in router
    assert "app.domains.video_production.video_production_run_types" in review_service
    assert "app.services.video_production_run_types" not in router
    assert "app.services.video_production_run_types" not in review_service


def test_video_production_readme_registers_run_types_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.video_production_run_types" in text
    assert "app.domains.video_production.video_production_run_types" in text
    assert 'rg "app\\.services\\.video_production_run_types" server/app server/tests' in text
    assert "REAL_SHORT_E2E" in text
    assert "MOCK_SERIES_SCALE" in text
    assert "validate_run_type" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

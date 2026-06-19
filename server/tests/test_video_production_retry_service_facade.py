import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-retry-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-retry-service-domain-plan.md"
DOMAIN_RETRY_PATH = REPO_ROOT / "server/app/domains/video_production/production_retry_service.py"
LEGACY_RETRY_PATH = REPO_ROOT / "server/app/services/production_retry_service.py"
SEGMENT_SERVICE_PATH = REPO_ROOT / "server/app/domains/video_production/production_segment_service.py"
ROUTER_PATH = REPO_ROOT / "server/app/domains/video_production/video_production_router.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_retry_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.production_retry_service",
        "app.services.production_retry_service",
        "get_retry_impact",
        "retry_segment_with_impact",
    ]:
        assert term in spec
        assert term in plan


def test_video_production_retry_service_domain_file_exists():
    assert DOMAIN_RETRY_PATH.exists()


def test_legacy_video_production_retry_service_is_thin_facade():
    text = LEGACY_RETRY_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def get_retry_impact" not in text
    assert "def retry_segment_with_impact" not in text
    assert _line_count(LEGACY_RETRY_PATH) <= 20


def test_legacy_video_production_retry_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.production_retry_service")
        domain = importlib.import_module("app.domains.video_production.production_retry_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"video production retry service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.get_retry_impact is domain.get_retry_impact
    assert legacy.retry_segment_with_impact is domain.retry_segment_with_impact


def test_video_production_domain_callers_import_domain_retry_service():
    segment_service = SEGMENT_SERVICE_PATH.read_text(encoding="utf-8")
    router = ROUTER_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production.production_retry_service" in segment_service
    assert "app.domains.video_production.production_retry_service" in router
    assert "app.services.production_retry_service" not in segment_service
    assert "app.services.production_retry_service" not in router


def test_video_production_readme_registers_retry_service_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.production_retry_service" in text
    assert "app.domains.video_production.production_retry_service" in text
    assert 'rg "app\\.services\\.production_retry_service" server/app server/tests' in text
    assert "get_retry_impact" in text
    assert "retry_segment_with_impact" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

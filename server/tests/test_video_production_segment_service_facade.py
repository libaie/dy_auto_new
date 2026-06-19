import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-segment-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-segment-service-domain-plan.md"
DOMAIN_SEGMENT_PATH = REPO_ROOT / "server/app/domains/video_production/production_segment_service.py"
LEGACY_SEGMENT_PATH = REPO_ROOT / "server/app/services/production_segment_service.py"
ROUTER_PATH = REPO_ROOT / "server/app/domains/video_production/video_production_router.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_segment_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.production_segment_service",
        "app.services.production_segment_service",
        "retry_segment",
        "retry_segment_with_impact",
    ]:
        assert term in spec
        assert term in plan


def test_video_production_segment_service_domain_file_exists():
    assert DOMAIN_SEGMENT_PATH.exists()


def test_legacy_video_production_segment_service_is_thin_facade():
    text = LEGACY_SEGMENT_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def retry_segment" not in text
    assert _line_count(LEGACY_SEGMENT_PATH) <= 20


def test_legacy_video_production_segment_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.production_segment_service")
        domain = importlib.import_module("app.domains.video_production.production_segment_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"video production segment service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.retry_segment is domain.retry_segment


def test_video_production_router_imports_domain_segment_service():
    text = ROUTER_PATH.read_text(encoding="utf-8")

    assert "from app.domains.video_production.production_segment_service import retry_segment" in text
    assert "from app.services.production_segment_service import retry_segment" not in text


def test_video_production_readme_registers_segment_service_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.production_segment_service" in text
    assert "app.domains.video_production.production_segment_service" in text
    assert 'rg "app\\.services\\.production_segment_service" server/app server/tests' in text
    assert "retry_segment" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

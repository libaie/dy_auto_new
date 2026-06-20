import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-mock-scale-scheduler-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-mock-scale-scheduler-domain-plan.md"
DOMAIN_SCHEDULER_PATH = REPO_ROOT / "server/app/domains/video_production/mock_scale_scheduler_service.py"
LEGACY_SCHEDULER_PATH = REPO_ROOT / "server/app/services/mock_scale_scheduler_service.py"
ROUTER_PATH = REPO_ROOT / "server/app/domains/video_production/video_production_router.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_mock_scale_scheduler_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.mock_scale_scheduler_service",
        "app.services.mock_scale_scheduler_service",
        "create_mock_scale_run",
        "advance_mock_scheduler",
    ]:
        assert term in spec
        assert term in plan


def test_video_production_mock_scale_scheduler_domain_file_exists():
    assert DOMAIN_SCHEDULER_PATH.exists()


def test_legacy_video_production_mock_scale_scheduler_is_thin_facade():
    text = LEGACY_SCHEDULER_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def create_mock_scale_run" not in text
    assert "def advance_mock_scheduler" not in text
    assert _line_count(LEGACY_SCHEDULER_PATH) <= 20


def test_legacy_video_production_mock_scale_scheduler_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.mock_scale_scheduler_service")
        domain = importlib.import_module("app.domains.video_production.mock_scale_scheduler_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"video production mock scale scheduler domain import failed: {exc}")

    assert legacy is domain
    assert legacy.create_mock_scale_run is domain.create_mock_scale_run
    assert legacy.advance_mock_scheduler is domain.advance_mock_scheduler


def test_video_production_router_imports_domain_mock_scale_scheduler():
    text = ROUTER_PATH.read_text(encoding="utf-8")

    assert "from app.domains.video_production.mock_scale_scheduler_service import advance_mock_scheduler" in text
    assert "from app.services.mock_scale_scheduler_service import advance_mock_scheduler" not in text


def test_video_production_mock_scale_scheduler_imports_domain_contracts():
    text = DOMAIN_SCHEDULER_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production.production_status" in text
    assert "app.domains.video_production.video_production_run_types" in text
    assert "app.services.production_status" not in text
    assert "app.services.video_production_run_types" not in text


def test_video_production_readme_registers_mock_scale_scheduler_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.mock_scale_scheduler_service" in text
    assert "app.domains.video_production.mock_scale_scheduler_service" in text
    assert 'rg "app\\.services\\.mock_scale_scheduler_service" server/app server/tests' in text
    assert "create_mock_scale_run" in text
    assert "advance_mock_scheduler" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

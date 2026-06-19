import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-cost-summary-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-cost-summary-service-domain-plan.md"
DOMAIN_COST_SUMMARY_PATH = REPO_ROOT / "server/app/domains/video_production/production_cost_summary_service.py"
LEGACY_COST_SUMMARY_PATH = REPO_ROOT / "server/app/services/production_cost_summary_service.py"
ROUTER_PATH = REPO_ROOT / "server/app/domains/video_production/video_production_router.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_cost_summary_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.production_cost_summary_service",
        "app.services.production_cost_summary_service",
        "_ZERO_RESERVATION_COSTS",
        "_ACTIVE_RESERVATION_STATUSES",
        "get_run_costs",
    ]:
        assert term in spec
        assert term in plan


def test_video_production_cost_summary_service_domain_file_exists():
    assert DOMAIN_COST_SUMMARY_PATH.exists()


def test_legacy_video_production_cost_summary_service_is_thin_facade():
    text = LEGACY_COST_SUMMARY_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "_ZERO_RESERVATION_COSTS =" not in text
    assert "def _reservation_costs" not in text
    assert "def get_run_costs" not in text
    assert _line_count(LEGACY_COST_SUMMARY_PATH) <= 20


def test_legacy_video_production_cost_summary_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.production_cost_summary_service")
        domain = importlib.import_module("app.domains.video_production.production_cost_summary_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"video production cost summary service domain import failed: {exc}")

    assert legacy is domain
    assert legacy._ZERO_RESERVATION_COSTS is domain._ZERO_RESERVATION_COSTS
    assert legacy._ACTIVE_RESERVATION_STATUSES is domain._ACTIVE_RESERVATION_STATUSES
    assert legacy.get_run_costs is domain.get_run_costs


def test_video_production_cost_summary_service_imports_domain_state_contract():
    text = DOMAIN_COST_SUMMARY_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production.production_state_contract" in text
    assert "app.services.production_state_contract" not in text


def test_video_production_router_imports_domain_cost_summary_service():
    text = ROUTER_PATH.read_text(encoding="utf-8")

    assert "from app.domains.video_production.production_cost_summary_service import get_run_costs" in text
    assert "from app.services.production_cost_summary_service import get_run_costs" not in text


def test_video_production_readme_registers_cost_summary_service_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.production_cost_summary_service" in text
    assert "app.domains.video_production.production_cost_summary_service" in text
    assert 'rg "app\\.services\\.production_cost_summary_service" server/app server/tests' in text
    assert "_ZERO_RESERVATION_COSTS" in text
    assert "get_run_costs" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

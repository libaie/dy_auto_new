import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-provider-cost-reservation-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-provider-cost-reservation-service-domain-plan.md"
DOMAIN_RESERVATION_PATH = REPO_ROOT / "server/app/domains/video_production/provider_cost_reservation_service.py"
LEGACY_RESERVATION_PATH = REPO_ROOT / "server/app/services/provider_cost_reservation_service.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_provider_cost_reservation_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.provider_cost_reservation_service",
        "app.services.provider_cost_reservation_service",
        "_ACTIVE_RESERVATION_STATUSES",
        "_PLAN_LOCKS",
        "active_reserved_cost",
        "create_cost_reservation",
        "settle_reservation",
        "expire_unsubmitted_reservations",
    ]:
        assert term in spec
        assert term in plan


def test_video_production_provider_cost_reservation_service_domain_file_exists():
    assert DOMAIN_RESERVATION_PATH.exists()


def test_legacy_video_production_provider_cost_reservation_service_is_thin_facade():
    text = LEGACY_RESERVATION_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "_ACTIVE_RESERVATION_STATUSES =" not in text
    assert "_PLAN_LOCKS:" not in text
    assert "def create_cost_reservation" not in text
    assert "def settle_reservation" not in text
    assert _line_count(LEGACY_RESERVATION_PATH) <= 20


def test_legacy_video_production_provider_cost_reservation_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.provider_cost_reservation_service")
        domain = importlib.import_module("app.domains.video_production.provider_cost_reservation_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"video production provider cost reservation service domain import failed: {exc}")

    assert legacy is domain
    assert legacy._ACTIVE_RESERVATION_STATUSES is domain._ACTIVE_RESERVATION_STATUSES
    assert legacy._PLAN_LOCKS is domain._PLAN_LOCKS
    assert legacy.active_reserved_cost is domain.active_reserved_cost
    assert legacy.create_cost_reservation is domain.create_cost_reservation
    assert legacy.mark_reservation_submitted is domain.mark_reservation_submitted
    assert legacy.mark_reservation_stale_needs_repair is domain.mark_reservation_stale_needs_repair
    assert legacy.settle_reservation is domain.settle_reservation
    assert legacy.release_unsubmitted_reservation is domain.release_unsubmitted_reservation
    assert legacy.expire_unsubmitted_reservations is domain.expire_unsubmitted_reservations


def test_video_production_provider_cost_reservation_service_imports_domain_helpers():
    text = DOMAIN_RESERVATION_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production.production_errors" in text
    assert "app.domains.video_production.production_state_contract" in text
    assert "app.services.production_errors" not in text
    assert "app.services.production_state_contract" not in text


def test_video_production_readme_registers_provider_cost_reservation_service_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.provider_cost_reservation_service" in text
    assert "app.domains.video_production.provider_cost_reservation_service" in text
    assert 'rg "app\\.services\\.provider_cost_reservation_service" server/app server/tests' in text
    assert "approved cross-domain consumers" in text
    assert "active_reserved_cost" in text
    assert "settle_reservation" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-review-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-review-service-domain-plan.md"
DOMAIN_REVIEW_PATH = REPO_ROOT / "server/app/domains/video_production/production_review_service.py"
LEGACY_REVIEW_PATH = REPO_ROOT / "server/app/services/production_review_service.py"
ROUTER_PATH = REPO_ROOT / "server/app/domains/video_production/video_production_router.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_review_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.production_review_service",
        "app.services.production_review_service",
        "SUPPORTED_BULK_REVIEW_ACTIONS",
        "SUPPORTED_BULK_ASSET_TYPES",
        "GATED_ASSET_TYPES",
        "apply_bulk_review_action",
    ]:
        assert term in spec
        assert term in plan


def test_video_production_review_service_domain_file_exists():
    assert DOMAIN_REVIEW_PATH.exists()


def test_legacy_video_production_review_service_is_thin_facade():
    text = LEGACY_REVIEW_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "SUPPORTED_BULK_REVIEW_ACTIONS =" not in text
    assert "def _review_snapshot" not in text
    assert "def apply_bulk_review_action" not in text
    assert _line_count(LEGACY_REVIEW_PATH) <= 20


def test_legacy_video_production_review_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.production_review_service")
        domain = importlib.import_module("app.domains.video_production.production_review_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"video production review service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.SUPPORTED_BULK_REVIEW_ACTIONS is domain.SUPPORTED_BULK_REVIEW_ACTIONS
    assert legacy.SUPPORTED_BULK_ASSET_TYPES is domain.SUPPORTED_BULK_ASSET_TYPES
    assert legacy.GATED_ASSET_TYPES is domain.GATED_ASSET_TYPES
    assert legacy.apply_bulk_review_action is domain.apply_bulk_review_action


def test_video_production_review_service_imports_domain_state_contract():
    text = DOMAIN_REVIEW_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production.production_state_contract" in text
    assert "app.services.production_state_contract" not in text


def test_video_production_router_imports_domain_review_service():
    text = ROUTER_PATH.read_text(encoding="utf-8")

    assert "from app.domains.video_production.production_review_service import apply_bulk_review_action" in text
    assert "from app.services.production_review_service import apply_bulk_review_action" not in text


def test_video_production_readme_registers_review_service_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.production_review_service" in text
    assert "app.domains.video_production.production_review_service" in text
    assert 'rg "app\\.services\\.production_review_service" server/app server/tests' in text
    assert "SUPPORTED_BULK_REVIEW_ACTIONS" in text
    assert "apply_bulk_review_action" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

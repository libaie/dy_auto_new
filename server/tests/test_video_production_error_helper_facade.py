import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-error-helper-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-error-helper-domain-plan.md"
DOMAIN_HELPER_PATH = REPO_ROOT / "server/app/domains/video_production/production_errors.py"
LEGACY_HELPER_PATH = REPO_ROOT / "server/app/services/production_errors.py"
DOMAIN_ROUTER_PATH = REPO_ROOT / "server/app/domains/video_production/video_production_router.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_error_helper_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.production_errors",
        "app.services.production_errors",
        "ProductionErrorCode",
        "ProductionRepairableError",
        "to_http_detail",
    ]:
        assert term in spec
        assert term in plan


def test_video_production_error_helper_domain_file_exists():
    assert DOMAIN_HELPER_PATH.exists()


def test_legacy_video_production_error_helper_is_thin_facade():
    text = LEGACY_HELPER_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "class ProductionErrorCode" not in text
    assert "class ProductionRepairableError" not in text
    assert "def to_http_detail" not in text
    assert _line_count(LEGACY_HELPER_PATH) <= 20


def test_legacy_video_production_error_helper_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.production_errors")
        domain = importlib.import_module("app.domains.video_production.production_errors")
    except ModuleNotFoundError as exc:
        pytest.fail(f"video production error helper domain import failed: {exc}")

    assert legacy is domain
    assert legacy.ProductionErrorCode is domain.ProductionErrorCode
    assert legacy.ProductionRepairableError is domain.ProductionRepairableError
    assert legacy.to_http_detail is domain.to_http_detail


def test_video_production_router_imports_error_helper_domain_path():
    text = DOMAIN_ROUTER_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production.production_errors" in text
    assert "app.services.production_errors" not in text


def test_video_production_readme_registers_error_helper_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.production_errors" in text
    assert "app.domains.video_production.production_errors" in text
    assert 'rg "app\\.services\\.production_errors" server/app server/tests' in text
    assert "ProductionErrorCode" in text
    assert "ProductionRepairableError" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

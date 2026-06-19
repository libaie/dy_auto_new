import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-provider-capability-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-provider-capability-service-domain-plan.md"
DOMAIN_CAPABILITY_PATH = REPO_ROOT / "server/app/domains/video_production/provider_capability_service.py"
LEGACY_CAPABILITY_PATH = REPO_ROOT / "server/app/services/provider_capability_service.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_provider_capability_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.provider_capability_service",
        "app.services.provider_capability_service",
        "DEFAULT_REAL_PROVIDER_CAPABILITY",
        "capability_from_model_config",
        "assert_real_paid_allowed",
        "ProductionRepairableError",
        "ProductionErrorCode",
    ]:
        assert term in spec
        assert term in plan


def test_video_production_provider_capability_service_domain_file_exists():
    assert DOMAIN_CAPABILITY_PATH.exists()


def test_legacy_video_production_provider_capability_service_is_thin_facade():
    text = LEGACY_CAPABILITY_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "DEFAULT_REAL_PROVIDER_CAPABILITY =" not in text
    assert "def capability_from_model_config" not in text
    assert "def assert_real_paid_allowed" not in text
    assert _line_count(LEGACY_CAPABILITY_PATH) <= 20


def test_legacy_video_production_provider_capability_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.provider_capability_service")
        domain = importlib.import_module("app.domains.video_production.provider_capability_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"video production provider capability service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.DEFAULT_REAL_PROVIDER_CAPABILITY is domain.DEFAULT_REAL_PROVIDER_CAPABILITY
    assert legacy.capability_from_model_config is domain.capability_from_model_config
    assert legacy.assert_real_paid_allowed is domain.assert_real_paid_allowed


def test_video_production_provider_capability_service_imports_domain_errors():
    text = DOMAIN_CAPABILITY_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production.production_errors" in text
    assert "app.services.production_errors" not in text


def test_video_production_readme_registers_provider_capability_service_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.provider_capability_service" in text
    assert "app.domains.video_production.provider_capability_service" in text
    assert 'rg "app\\.services\\.provider_capability_service" server/app server/tests' in text
    assert "capability_from_model_config" in text
    assert "assert_real_paid_allowed" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

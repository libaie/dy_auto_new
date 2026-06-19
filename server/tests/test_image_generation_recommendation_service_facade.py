import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-image-generation-recommendation-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-image-generation-recommendation-service-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/image_generation/image_production_recommendation_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/image_production_recommendation_service.py"
DOMAIN_ROUTER_PATH = REPO_ROOT / "server/app/domains/image_generation/image_production_router.py"
README_PATH = REPO_ROOT / "server/app/domains/image_generation/README.md"


def test_image_recommendation_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.image_generation.image_production_recommendation_service",
        "app.services.image_production_recommendation_service",
        "strategy_recommendation_payload",
        "ab_winner_recommendation_payload",
    ]:
        assert term in spec
        assert term in plan


def test_image_recommendation_service_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_image_recommendation_service_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.image_generation" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def strategy_recommendation_payload" not in text
    assert "def ab_winner_recommendation_payload" not in text
    assert "LOW_SAMPLE_ATTEMPTS =" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_image_recommendation_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.image_production_recommendation_service")
        domain = importlib.import_module("app.domains.image_generation.image_production_recommendation_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"image production recommendation service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.strategy_recommendation_payload is domain.strategy_recommendation_payload
    assert legacy.ab_winner_recommendation_payload is domain.ab_winner_recommendation_payload
    assert legacy.LOW_SAMPLE_ATTEMPTS is domain.LOW_SAMPLE_ATTEMPTS
    assert legacy.HIGH_CONFIDENCE_ATTEMPTS is domain.HIGH_CONFIDENCE_ATTEMPTS


def test_recommendation_service_imports_metrics_service_domain_path():
    text = DOMAIN_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.image_generation.image_production_metrics_service" in text
    assert "app.services.image_production_metrics_service" not in text


def test_image_production_router_imports_recommendation_service_domain_path():
    text = DOMAIN_ROUTER_PATH.read_text(encoding="utf-8")

    assert "app.domains.image_generation.image_production_recommendation_service" in text
    assert "app.services.image_production_recommendation_service" not in text


def test_image_generation_readme_registers_recommendation_service_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.image_production_recommendation_service" in text
    assert "app.domains.image_generation.image_production_recommendation_service" in text
    assert 'rg "app\\.services\\.image_production_recommendation_service" server/app server/tests' in text
    assert "strategy_recommendation_payload" in text
    assert "ab_winner_recommendation_payload" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

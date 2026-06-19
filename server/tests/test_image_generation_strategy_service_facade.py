import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-image-generation-strategy-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-image-generation-strategy-service-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/image_generation/image_production_strategy_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/image_production_strategy_service.py"
DOMAIN_ROUTER_PATH = REPO_ROOT / "server/app/domains/image_generation/image_production_router.py"
README_PATH = REPO_ROOT / "server/app/domains/image_generation/README.md"


def test_image_strategy_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.image_generation.image_production_strategy_service",
        "app.services.image_production_strategy_service",
        "seed_default_image_strategies",
        "create_strategy",
        "update_strategy",
        "strategy_payload",
    ]:
        assert term in spec
        assert term in plan


def test_image_strategy_service_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_image_strategy_service_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.image_generation" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def seed_default_image_strategies" not in text
    assert "def create_strategy" not in text
    assert "def update_strategy" not in text
    assert "def strategy_payload" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_image_strategy_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.image_production_strategy_service")
        domain = importlib.import_module("app.domains.image_generation.image_production_strategy_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"image strategy service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.DEFAULT_STRATEGIES is domain.DEFAULT_STRATEGIES
    assert legacy.VALID_DESTINATION_ROLES is domain.VALID_DESTINATION_ROLES
    assert legacy.seed_default_image_strategies is domain.seed_default_image_strategies
    assert legacy.create_strategy is domain.create_strategy
    assert legacy.update_strategy is domain.update_strategy
    assert legacy.strategy_payload is domain.strategy_payload


def test_image_production_router_imports_strategy_service_domain_path():
    text = DOMAIN_ROUTER_PATH.read_text(encoding="utf-8")

    assert "app.domains.image_generation.image_production_strategy_service" in text
    assert "app.services.image_production_strategy_service" not in text


def test_image_generation_readme_registers_strategy_service_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.image_production_strategy_service" in text
    assert "app.domains.image_generation.image_production_strategy_service" in text
    assert 'rg "app\\.services\\.image_production_strategy_service" server/app server/tests' in text
    assert "seed_default_image_strategies" in text
    assert "strategy_payload" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

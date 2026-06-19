import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-image-generation-metrics-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-image-generation-metrics-service-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/image_generation/image_production_metrics_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/image_production_metrics_service.py"
DOMAIN_ROUTER_PATH = REPO_ROOT / "server/app/domains/image_generation/image_production_router.py"
README_PATH = REPO_ROOT / "server/app/domains/image_generation/README.md"


def test_image_metrics_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.image_generation.image_production_metrics_service",
        "app.services.image_production_metrics_service",
        "refresh_image_strategy_metrics",
        "refresh_all_image_strategy_metrics",
        "aggregate_strategy_metrics_payload",
        "strategy_metrics_payload",
    ]:
        assert term in spec
        assert term in plan


def test_image_metrics_service_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_image_metrics_service_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.image_generation" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def refresh_image_strategy_metrics" not in text
    assert "def refresh_all_image_strategy_metrics" not in text
    assert "def aggregate_strategy_metrics_payload" not in text
    assert "def strategy_metrics_payload" not in text
    assert "SUCCESS_TASK_STATUSES = {" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_image_metrics_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.image_production_metrics_service")
        domain = importlib.import_module("app.domains.image_generation.image_production_metrics_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"image production metrics service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.refresh_image_strategy_metrics is domain.refresh_image_strategy_metrics
    assert legacy.refresh_all_image_strategy_metrics is domain.refresh_all_image_strategy_metrics
    assert legacy.aggregate_strategy_metrics_payload is domain.aggregate_strategy_metrics_payload
    assert legacy.strategy_metrics_payload is domain.strategy_metrics_payload
    assert legacy.SUCCESS_TASK_STATUSES is domain.SUCCESS_TASK_STATUSES


def test_image_production_router_imports_metrics_service_domain_path():
    text = DOMAIN_ROUTER_PATH.read_text(encoding="utf-8")

    assert "app.domains.image_generation.image_production_metrics_service" in text
    assert "app.services.image_production_metrics_service" not in text


def test_image_generation_readme_registers_metrics_service_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.image_production_metrics_service" in text
    assert "app.domains.image_generation.image_production_metrics_service" in text
    assert 'rg "app\\.services\\.image_production_metrics_service" server/app server/tests' in text
    assert "refresh_image_strategy_metrics" in text
    assert "aggregate_strategy_metrics_payload" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

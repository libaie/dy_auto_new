import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-provider-stage-executor-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-provider-stage-executor-domain-plan.md"
DOMAIN_EXECUTOR_PATH = REPO_ROOT / "server/app/domains/video_production/provider_stage_executor.py"
LEGACY_EXECUTOR_PATH = REPO_ROOT / "server/app/services/provider_stage_executor.py"
SYSTEM_HEALTH_PATH = REPO_ROOT / "server/app/domains/system_operations/system_health_router.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_provider_stage_executor_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.provider_stage_executor",
        "app.services.provider_stage_executor",
        "ProviderStageExecutor",
        "PROVIDER_THROTTLE_DEPLOYMENT_CONTRACT",
    ]:
        assert term in spec
        assert term in plan


def test_provider_stage_executor_domain_file_exists():
    assert DOMAIN_EXECUTOR_PATH.exists()


def test_legacy_provider_stage_executor_is_thin_facade():
    text = LEGACY_EXECUTOR_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "class ProviderStageExecutor" not in text
    assert "def assert_paid_submit_deployment_safe" not in text
    assert _line_count(LEGACY_EXECUTOR_PATH) <= 20


def test_legacy_provider_stage_executor_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.provider_stage_executor")
        domain = importlib.import_module("app.domains.video_production.provider_stage_executor")
    except ModuleNotFoundError as exc:
        pytest.fail(f"provider stage executor domain import failed: {exc}")

    assert legacy is domain
    assert legacy.ProviderStageExecutor is domain.ProviderStageExecutor
    assert legacy.PROVIDER_THROTTLE_DEPLOYMENT_CONTRACT is domain.PROVIDER_THROTTLE_DEPLOYMENT_CONTRACT
    assert legacy.PROVIDER_SUBMIT_WORKER_COUNT_ENV is domain.PROVIDER_SUBMIT_WORKER_COUNT_ENV
    assert legacy.assert_paid_submit_deployment_safe is domain.assert_paid_submit_deployment_safe


def test_provider_stage_executor_imports_domain_helper_contracts():
    text = DOMAIN_EXECUTOR_PATH.read_text(encoding="utf-8")

    for module_name in [
        "production_action_result",
        "production_errors",
        "production_state_contract",
        "provider_capability_service",
        "provider_cost_reservation_service",
        "provider_stage_task_service",
    ]:
        assert f"app.domains.video_production.{module_name}" in text
        assert f"app.services.{module_name}" not in text

    assert "app.services.production_observability" in text
    assert "app.services.production_queue_service" in text


def test_system_health_router_imports_domain_executor_constant():
    text = SYSTEM_HEALTH_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production.provider_stage_executor" in text
    assert "app.services.provider_stage_executor" not in text


def test_video_production_readme_registers_provider_stage_executor_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "provider_stage_executor.py" in text
    assert "ProviderStageExecutor" in text
    assert "PROVIDER_THROTTLE_DEPLOYMENT_CONTRACT" in text
    assert "app.services.provider_stage_executor" in text
    assert "app.domains.video_production.provider_stage_executor" in text
    assert 'rg "app\\.services\\.provider_stage_executor" server/app server/tests' in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

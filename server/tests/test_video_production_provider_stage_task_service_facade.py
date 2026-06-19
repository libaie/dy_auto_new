import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-provider-stage-task-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-provider-stage-task-service-domain-plan.md"
DOMAIN_TASK_SERVICE_PATH = REPO_ROOT / "server/app/domains/video_production/provider_stage_task_service.py"
LEGACY_TASK_SERVICE_PATH = REPO_ROOT / "server/app/services/provider_stage_task_service.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_provider_stage_task_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.provider_stage_task_service",
        "app.services.provider_stage_task_service",
        "request_hash",
        "provider_stage_idempotency_key",
        "get_or_create_stage_task",
        "set_task_status",
        "claim_stage_task_for_submit",
    ]:
        assert term in spec
        assert term in plan


def test_video_production_provider_stage_task_service_domain_file_exists():
    assert DOMAIN_TASK_SERVICE_PATH.exists()


def test_legacy_video_production_provider_stage_task_service_is_thin_facade():
    text = LEGACY_TASK_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def request_hash" not in text
    assert "def get_or_create_stage_task" not in text
    assert "def set_task_status" not in text
    assert "def claim_stage_task_for_submit" not in text
    assert _line_count(LEGACY_TASK_SERVICE_PATH) <= 20


def test_legacy_video_production_provider_stage_task_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.provider_stage_task_service")
        domain = importlib.import_module("app.domains.video_production.provider_stage_task_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"video production provider stage task service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.request_hash is domain.request_hash
    assert legacy.provider_stage_idempotency_key is domain.provider_stage_idempotency_key
    assert legacy.get_or_create_stage_task is domain.get_or_create_stage_task
    assert legacy.set_task_status is domain.set_task_status
    assert legacy.claim_stage_task_for_submit is domain.claim_stage_task_for_submit


def test_video_production_provider_stage_task_service_imports_domain_state_contract():
    text = DOMAIN_TASK_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production.production_state_contract" in text
    assert "app.services.production_state_contract" not in text


def test_video_production_readme_registers_provider_stage_task_service_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.provider_stage_task_service" in text
    assert "app.domains.video_production.provider_stage_task_service" in text
    assert 'rg "app\\.services\\.provider_stage_task_service" server/app server/tests' in text
    assert "get_or_create_stage_task" in text
    assert "claim_stage_task_for_submit" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

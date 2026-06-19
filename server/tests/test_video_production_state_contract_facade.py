import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-state-contract-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-state-contract-domain-plan.md"
DOMAIN_CONTRACT_PATH = REPO_ROOT / "server/app/domains/video_production/production_state_contract.py"
LEGACY_CONTRACT_PATH = REPO_ROOT / "server/app/services/production_state_contract.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_state_contract_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.production_state_contract",
        "app.services.production_state_contract",
        "PROVIDER_TASK_RESERVED",
        "COST_ACTIVE_UNSUBMITTED",
        "asset_is_reviewable",
        "provider_task_is_active",
        "validate_transition",
    ]:
        assert term in spec
        assert term in plan


def test_video_production_state_contract_domain_file_exists():
    assert DOMAIN_CONTRACT_PATH.exists()


def test_legacy_video_production_state_contract_is_thin_facade():
    text = LEGACY_CONTRACT_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "PROVIDER_TASK_RESERVED =" not in text
    assert "COST_ACTIVE_UNSUBMITTED =" not in text
    assert "def asset_is_reviewable" not in text
    assert "def validate_transition" not in text
    assert _line_count(LEGACY_CONTRACT_PATH) <= 20


def test_legacy_video_production_state_contract_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.production_state_contract")
        domain = importlib.import_module("app.domains.video_production.production_state_contract")
    except ModuleNotFoundError as exc:
        pytest.fail(f"video production state contract domain import failed: {exc}")

    assert legacy is domain
    assert legacy.PROVIDER_TASK_RESERVED is domain.PROVIDER_TASK_RESERVED
    assert legacy.COST_ACTIVE_UNSUBMITTED is domain.COST_ACTIVE_UNSUBMITTED
    assert legacy.PROVIDER_TASK_ACTIVE_STATUSES is domain.PROVIDER_TASK_ACTIVE_STATUSES
    assert legacy.asset_is_reviewable is domain.asset_is_reviewable
    assert legacy.provider_task_is_active is domain.provider_task_is_active
    assert legacy.validate_transition is domain.validate_transition


def test_video_production_readme_registers_state_contract_facade():
    text = README_PATH.read_text(encoding="utf-8")

    assert "app.services.production_state_contract" in text
    assert "app.domains.video_production.production_state_contract" in text
    assert 'rg "app\\.services\\.production_state_contract" server/app server/tests' in text
    assert "provider_task_is_active" in text
    assert "validate_transition" in text


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

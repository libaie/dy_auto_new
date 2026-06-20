import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-agency-repair-contracts-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-agency-repair-contracts-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/agency_operations/agency_repair_contracts.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/agency_repair_contracts.py"
README_PATH = REPO_ROOT / "server/app/domains/agency_operations/README.md"


def test_agency_repair_contracts_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.agency_operations.agency_repair_contracts",
        "app.services.agency_repair_contracts",
        "AUTO_REPAIR_STAGE",
        "AutoRepairPolicy",
        "RepairTask",
        "RepairClassificationResult",
        "action_for_task",
    ]:
        assert term in spec
        assert term in plan


def test_agency_repair_contracts_implementation_lives_in_agency_operations_domain():
    domain_text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "AUTO_REPAIR_STAGE" in domain_text
    assert "class AutoRepairPolicy" in domain_text
    assert "class RepairTask" in domain_text
    assert "class RepairClassificationResult" in domain_text
    assert "def action_for_task" in domain_text

    legacy_text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations" in legacy_text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in legacy_text
    assert "class RepairTask" not in legacy_text


def test_legacy_agency_repair_contracts_facade_resolves_to_domain_module():
    domain = importlib.import_module("app.domains.agency_operations.agency_repair_contracts")
    legacy = importlib.import_module("app.services.agency_repair_contracts")
    assert legacy is domain
    assert legacy.AUTO_REPAIR_STAGE == domain.AUTO_REPAIR_STAGE
    assert legacy.AutoRepairPolicy is domain.AutoRepairPolicy
    assert legacy.RepairTask is domain.RepairTask
    assert legacy.RepairClassificationResult is domain.RepairClassificationResult
    assert legacy.action_for_task is domain.action_for_task

    task = legacy.RepairTask(type="unknown", stage="image")
    assert task.type == "manual_incomplete_repair_task"
    assert legacy.action_for_task("image_generation_failed", "manual", None)[1] == "/ai-video-review"


def test_agency_operations_readme_registers_repair_contracts_facade():
    text = README_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations.agency_repair_contracts" in text
    assert "app.services.agency_repair_contracts" in text

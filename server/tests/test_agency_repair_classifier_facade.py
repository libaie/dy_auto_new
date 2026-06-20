import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-agency-repair-classifier-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-agency-repair-classifier-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/agency_operations/agency_repair_classifier.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/agency_repair_classifier.py"
README_PATH = REPO_ROOT / "server/app/domains/agency_operations/README.md"


def test_agency_repair_classifier_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.agency_operations.agency_repair_classifier",
        "app.services.agency_repair_classifier",
        "app.domains.agency_operations.agency_repair_contracts",
        "classify_repair_tasks",
    ]:
        assert term in spec
        assert term in plan


def test_agency_repair_classifier_implementation_lives_in_agency_operations_domain():
    domain_text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "def classify_repair_tasks" in domain_text
    assert "def _needs_manual_from_summary" in domain_text
    assert "app.domains.agency_operations.agency_repair_contracts" in domain_text
    assert "app.services.agency_repair_contracts" not in domain_text

    legacy_text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations" in legacy_text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in legacy_text
    assert "def classify_repair_tasks" not in legacy_text


def test_legacy_agency_repair_classifier_facade_resolves_to_domain_module():
    domain = importlib.import_module("app.domains.agency_operations.agency_repair_classifier")
    legacy = importlib.import_module("app.services.agency_repair_classifier")
    assert legacy is domain
    assert legacy.classify_repair_tasks is domain.classify_repair_tasks

    manual = legacy.classify_repair_tasks(
        {"summary": "已记录审查发现"},
        stage="style_lock",
        series_id="series-1",
    )
    assert manual.manual_gate_required is True
    assert manual.repair_tasks[0].type == "manual_incomplete_repair_task"

    paid = legacy.classify_repair_tasks(
        {"repair_tasks": [{"type": "image_generation_failed", "stage": "image", "target_id": "seg-1", "auto_execute": True}]},
        stage="image",
        series_id="series-1",
    )
    assert paid.repairable is True
    assert paid.repair_tasks[0].requires_paid_provider is True


def test_agency_operations_readme_registers_repair_classifier_facade():
    text = README_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations.agency_repair_classifier" in text
    assert "app.services.agency_repair_classifier" in text

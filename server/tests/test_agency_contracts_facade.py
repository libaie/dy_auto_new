import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-agency-contracts-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-agency-contracts-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/agency_operations/agency_contracts.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/agency_contracts.py"
README_PATH = REPO_ROOT / "server/app/domains/agency_operations/README.md"


def test_agency_contracts_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.agency_operations.agency_contracts",
        "app.services.agency_contracts",
        "AgencyConsoleResponse",
        "AgencyInvocationSummary",
        "AgencyExecutionStatus",
    ]:
        assert term in spec
        assert term in plan


def test_agency_contracts_implementation_lives_in_agency_operations_domain():
    domain_text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "class AgencyExecutionStatus" in domain_text
    assert "class AgencyInvocationSummary" in domain_text
    assert "class AgencyConsoleResponse" in domain_text

    legacy_text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations" in legacy_text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in legacy_text
    assert "class AgencyExecutionStatus" not in legacy_text


def test_legacy_agency_contracts_facade_resolves_to_domain_module():
    domain = importlib.import_module("app.domains.agency_operations.agency_contracts")
    legacy = importlib.import_module("app.services.agency_contracts")
    assert legacy is domain
    assert legacy.AgencyConsoleResponse is domain.AgencyConsoleResponse
    assert legacy.AgencyInvocationSummary is domain.AgencyInvocationSummary
    assert legacy.AgencyExecutionStatus is domain.AgencyExecutionStatus

    summary = legacy.AgencyInvocationSummary(
        id="inv-1",
        stage="script",
        expert_id="story-architect",
        role="reviewer",
        execution_status=legacy.AgencyExecutionStatus.running,
        result_status=legacy.AgencyInvocationResultStatus.pending,
    )
    assert summary.execution_status == "running"


def test_agency_operations_readme_registers_contracts_facade():
    text = README_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations.agency_contracts" in text
    assert "app.services.agency_contracts" in text

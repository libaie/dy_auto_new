import importlib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-agency-persistence-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-agency-persistence-domain-plan.md"
README_PATH = REPO_ROOT / "server/app/domains/agency_operations/README.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/agency_operations/agency_persistence.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/agency_persistence.py"


def test_agency_persistence_spec_plan_and_readme_document_boundary():
    combined = SPEC_PATH.read_text(encoding="utf-8") + PLAN_PATH.read_text(encoding="utf-8")
    for expected in (
        "app.domains.agency_operations.agency_persistence",
        "app.services.agency_persistence",
        "create_or_resume_invocation",
        "finalize_invocation_and_audit",
    ):
        assert expected in combined

    readme = README_PATH.read_text(encoding="utf-8")
    assert "agency_persistence.py" in readme
    assert "app.domains.agency_operations.agency_persistence" in readme
    assert "app.services.agency_persistence" in readme


def test_agency_persistence_domain_file_owns_invocation_persistence():
    text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "RETRYABLE_INVOCATION_ERROR_CODES" in text
    assert "def create_or_resume_invocation" in text
    assert "def finalize_invocation_and_audit" in text
    assert "record_production_event" in text


def test_agency_persistence_imports_already_migrated_helpers_from_domains():
    text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert (
        "from app.domains.production_observability.production_observability_service "
        "import record_production_event"
    ) in text
    assert (
        "from app.domains.agency_operations.agency_repair_classifier "
        "import classify_repair_tasks"
    ) in text
    assert (
        "from app.domains.agency_operations.agency_repair_orchestrator "
        "import enqueue_repair_tasks_for_invocation"
    ) in text
    assert "app.services.production_observability" not in text
    assert "app.services.agency_repair_classifier" not in text
    assert "app.services.agency_repair_orchestrator" not in text


def test_legacy_agency_persistence_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations import agency_persistence" in text
    assert "sys.modules[_LEGACY_MODULE_NAME] = _domain_module" in text
    assert "def create_or_resume_invocation" not in text
    assert "def finalize_invocation_and_audit" not in text


def test_legacy_agency_persistence_module_aliases_domain():
    for name in (
        "app.services.agency_persistence",
        "app.domains.agency_operations.agency_persistence",
    ):
        sys.modules.pop(name, None)

    legacy = importlib.import_module("app.services.agency_persistence")
    domain = importlib.import_module("app.domains.agency_operations.agency_persistence")

    assert sys.modules["app.services.agency_persistence"] is domain
    assert legacy.create_or_resume_invocation is domain.create_or_resume_invocation
    assert legacy.finalize_invocation_and_audit is domain.finalize_invocation_and_audit


def test_agency_persistence_exports_retryable_invocation_error_codes():
    domain = importlib.import_module("app.domains.agency_operations.agency_persistence")

    assert domain.RETRYABLE_INVOCATION_ERROR_CODES == {
        "EXPERT_MODEL_TIMEOUT",
        "EXPERT_MODEL_RATE_LIMITED",
        "EXPERT_MODEL_HTTP_ERROR",
    }

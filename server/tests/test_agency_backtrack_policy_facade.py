import importlib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-agency-backtrack-policy-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-agency-backtrack-policy-domain-plan.md"
README_PATH = REPO_ROOT / "server/app/domains/agency_operations/README.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/agency_operations/agency_backtrack_policy.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/agency_backtrack_policy.py"


def test_agency_backtrack_policy_spec_plan_and_readme_document_boundary():
    combined = SPEC_PATH.read_text(encoding="utf-8") + PLAN_PATH.read_text(encoding="utf-8")
    for expected in (
        "app.domains.agency_operations.agency_backtrack_policy",
        "app.services.agency_backtrack_policy",
        "trigger_backtrack_if_needed",
    ):
        assert expected in combined

    readme = README_PATH.read_text(encoding="utf-8")
    assert "agency_backtrack_policy.py" in readme
    assert "app.domains.agency_operations.agency_backtrack_policy" in readme
    assert "app.services.agency_backtrack_policy" in readme


def test_agency_backtrack_policy_domain_file_owns_policy():
    text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "def trigger_backtrack_if_needed" in text
    assert "BACKTRACK_FAILURE_THRESHOLD" in text
    assert "agency_backtrack_triggered" in text


def test_legacy_agency_backtrack_policy_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations import agency_backtrack_policy" in text
    assert "sys.modules[_LEGACY_MODULE_NAME] = _domain_module" in text
    assert "def trigger_backtrack_if_needed" not in text
    assert "ProductionAuditEvent" not in text


def test_legacy_agency_backtrack_policy_module_aliases_domain():
    for name in (
        "app.services.agency_backtrack_policy",
        "app.domains.agency_operations.agency_backtrack_policy",
    ):
        sys.modules.pop(name, None)

    legacy = importlib.import_module("app.services.agency_backtrack_policy")
    domain = importlib.import_module("app.domains.agency_operations.agency_backtrack_policy")

    assert sys.modules["app.services.agency_backtrack_policy"] is domain
    assert legacy.trigger_backtrack_if_needed is domain.trigger_backtrack_if_needed

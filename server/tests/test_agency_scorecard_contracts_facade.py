import importlib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-agency-scorecard-contracts-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-agency-scorecard-contracts-domain-plan.md"
README_PATH = REPO_ROOT / "server/app/domains/agency_operations/README.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/agency_operations/agency_scorecard_contracts.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/agency_scorecard_contracts.py"


def test_agency_scorecard_contracts_spec_plan_and_readme_document_boundary():
    combined = SPEC_PATH.read_text(encoding="utf-8") + PLAN_PATH.read_text(encoding="utf-8")
    for expected in (
        "app.domains.agency_operations.agency_scorecard_contracts",
        "app.services.agency_scorecard_contracts",
        "normalize_scorecard",
        "scorecard_blocks_stage",
    ):
        assert expected in combined

    readme = README_PATH.read_text(encoding="utf-8")
    assert "agency_scorecard_contracts.py" in readme
    assert "app.domains.agency_operations.agency_scorecard_contracts" in readme
    assert "app.services.agency_scorecard_contracts" in readme


def test_agency_scorecard_contracts_domain_file_owns_helpers():
    text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "def normalize_scorecard" in text
    assert "def scorecard_blocks_stage" in text
    assert "SCORECARD_SCHEMA_VERSION" in text


def test_legacy_agency_scorecard_contracts_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations import agency_scorecard_contracts" in text
    assert "sys.modules[_LEGACY_MODULE_NAME] = _domain_module" in text
    assert "def normalize_scorecard" not in text
    assert "def scorecard_blocks_stage" not in text


def test_legacy_agency_scorecard_contracts_module_is_domain_module():
    for name in (
        "app.services.agency_scorecard_contracts",
        "app.domains.agency_operations.agency_scorecard_contracts",
    ):
        sys.modules.pop(name, None)

    legacy = importlib.import_module("app.services.agency_scorecard_contracts")
    domain = importlib.import_module("app.domains.agency_operations.agency_scorecard_contracts")

    assert sys.modules["app.services.agency_scorecard_contracts"] is domain
    assert legacy.normalize_scorecard is domain.normalize_scorecard
    assert legacy.scorecard_blocks_stage is domain.scorecard_blocks_stage

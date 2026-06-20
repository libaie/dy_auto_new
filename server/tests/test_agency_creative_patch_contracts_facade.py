import importlib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-agency-creative-patch-contracts-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-agency-creative-patch-contracts-domain-plan.md"
README_PATH = REPO_ROOT / "server/app/domains/agency_operations/README.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/agency_operations/agency_creative_patch_contracts.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/agency_creative_patch_contracts.py"


def test_agency_creative_patch_contracts_spec_plan_and_readme_document_boundary():
    combined = SPEC_PATH.read_text(encoding="utf-8") + PLAN_PATH.read_text(encoding="utf-8")
    for expected in (
        "app.domains.agency_operations.agency_creative_patch_contracts",
        "app.services.agency_creative_patch_contracts",
        "CreativePatchProposal",
        "normalize_patch_payload",
    ):
        assert expected in combined

    readme = README_PATH.read_text(encoding="utf-8")
    assert "agency_creative_patch_contracts.py" in readme
    assert "app.domains.agency_operations.agency_creative_patch_contracts" in readme
    assert "app.services.agency_creative_patch_contracts" in readme


def test_agency_creative_patch_contracts_domain_file_owns_contracts():
    text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "class CreativePatchProposal" in text
    assert "def normalize_patch_payload" in text
    assert "creative patch after must include at least one executable allowed field" in text


def test_legacy_agency_creative_patch_contracts_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations import agency_creative_patch_contracts" in text
    assert "sys.modules[_LEGACY_MODULE_NAME] = _domain_module" in text
    assert "class CreativePatchProposal" not in text
    assert "def normalize_patch_payload" not in text


def test_legacy_agency_creative_patch_contracts_module_aliases_domain():
    for name in (
        "app.services.agency_creative_patch_contracts",
        "app.domains.agency_operations.agency_creative_patch_contracts",
    ):
        sys.modules.pop(name, None)

    legacy = importlib.import_module("app.services.agency_creative_patch_contracts")
    domain = importlib.import_module("app.domains.agency_operations.agency_creative_patch_contracts")

    assert sys.modules["app.services.agency_creative_patch_contracts"] is domain
    assert legacy.CreativePatchProposal is domain.CreativePatchProposal
    assert legacy.normalize_patch_payload is domain.normalize_patch_payload

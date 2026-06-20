import importlib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-agency-multimodal-review-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-agency-multimodal-review-domain-plan.md"
README_PATH = REPO_ROOT / "server/app/domains/agency_operations/README.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/agency_operations/agency_multimodal_review.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/agency_multimodal_review.py"
ROUTER_PATH = REPO_ROOT / "server/app/domains/agency_operations/agency_router.py"


def test_agency_multimodal_review_spec_plan_and_readme_document_boundary():
    combined = SPEC_PATH.read_text(encoding="utf-8") + PLAN_PATH.read_text(encoding="utf-8")
    for expected in (
        "app.domains.agency_operations.agency_multimodal_review",
        "app.services.agency_multimodal_review",
        "build_multimodal_asset_context",
        "run_multimodal_asset_review",
    ):
        assert expected in combined

    readme = README_PATH.read_text(encoding="utf-8")
    assert "agency_multimodal_review.py" in readme
    assert "app.domains.agency_operations.agency_multimodal_review" in readme
    assert "app.services.agency_multimodal_review" in readme


def test_agency_multimodal_review_domain_file_owns_helpers():
    text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "def build_multimodal_asset_context" in text
    assert "async def run_multimodal_asset_review" in text


def test_legacy_agency_multimodal_review_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations import agency_multimodal_review" in text
    assert "sys.modules[_LEGACY_MODULE_NAME] = _domain_module" in text
    assert "def build_multimodal_asset_context" not in text
    assert "async def run_multimodal_asset_review" not in text


def test_legacy_agency_multimodal_review_module_aliases_domain():
    for name in (
        "app.services.agency_multimodal_review",
        "app.domains.agency_operations.agency_multimodal_review",
    ):
        sys.modules.pop(name, None)

    legacy = importlib.import_module("app.services.agency_multimodal_review")
    domain = importlib.import_module("app.domains.agency_operations.agency_multimodal_review")

    assert sys.modules["app.services.agency_multimodal_review"] is domain
    assert legacy.build_multimodal_asset_context is domain.build_multimodal_asset_context
    assert legacy.run_multimodal_asset_review is domain.run_multimodal_asset_review


def test_agency_router_imports_multimodal_review_from_domain():
    text = ROUTER_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations.agency_multimodal_review" in text
    assert "app.services.agency_multimodal_review" not in text

import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-agency-manifest-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-agency-manifest-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/agency_operations/agency_manifest.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/agency_manifest.py"
AGENCY_ROUTER_PATH = REPO_ROOT / "server/app/domains/agency_operations/agency_router.py"
STORY_GENERATOR_PATH = REPO_ROOT / "server/app/domains/ai_video_series/story_generator_expert.py"
README_PATH = REPO_ROOT / "server/app/domains/agency_operations/README.md"


def test_agency_manifest_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.agency_operations.agency_manifest",
        "app.services.agency_manifest",
        "AgencyManifest",
        "verify_manifest",
    ]:
        assert term in spec
        assert term in plan


def test_agency_manifest_domain_file_exists():
    assert DOMAIN_PATH.exists()


def test_legacy_agency_manifest_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "class AgencyManifest" not in text
    assert "def verify_manifest" not in text
    assert _line_count(LEGACY_PATH) <= 12


def test_legacy_agency_manifest_module_is_domain_module():
    legacy = importlib.import_module("app.services.agency_manifest")
    domain = importlib.import_module("app.domains.agency_operations.agency_manifest")
    assert legacy is domain
    assert legacy.AgencyManifest is domain.AgencyManifest
    assert legacy.verify_manifest is domain.verify_manifest
    assert legacy.load_manifest is domain.load_manifest


def test_services_parent_package_agency_manifest_attribute_is_domain_module():
    from app.services import agency_manifest as parent_import

    domain = importlib.import_module("app.domains.agency_operations.agency_manifest")
    assert parent_import is domain


def test_agency_manifest_data_root_stays_under_app_data():
    domain = importlib.import_module("app.domains.agency_operations.agency_manifest")
    assert domain.DATA_ROOT == REPO_ROOT / "server/app/data/agency_agents_zh"
    assert domain.MANIFEST_PATH == domain.DATA_ROOT / "manifest.json"


def test_clean_domain_callers_import_domain_agency_manifest():
    for path in [AGENCY_ROUTER_PATH, STORY_GENERATOR_PATH]:
        text = path.read_text(encoding="utf-8")
        assert "app.domains.agency_operations.agency_manifest" in text
        assert "app.services.agency_manifest" not in text


def test_agency_operations_docs_register_agency_manifest_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.agency_operations.agency_manifest",
        "app.services.agency_manifest",
        "AgencyManifest",
        "approved compatibility imports",
    ]:
        assert term in readme


def test_read_expert_markdown_stays_legacy_compatible():
    legacy = importlib.import_module("app.services.agency_manifest")
    text = legacy.read_expert_markdown("story_generator")
    assert len(text) > 500
    assert legacy.verify_manifest()["ok"] is True


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

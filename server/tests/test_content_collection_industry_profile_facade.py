import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-industry-profile-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-industry-profile-domain-plan.md"
DOMAIN_PROFILE_PATH = REPO_ROOT / "server/app/domains/content_collection/industry_profile_service.py"
LEGACY_PROFILE_PATH = REPO_ROOT / "server/app/services/industry_profile_service.py"
MUTATIONS_PATH = REPO_ROOT / "server/app/domains/content_collection/mutations.py"
README_PATH = REPO_ROOT / "server/app/domains/content_collection/README.md"


def test_industry_profile_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.content_collection.industry_profile_service",
        "app.services.industry_profile_service",
        "load_profile",
    ]:
        assert term in spec
        assert term in plan


def test_industry_profile_domain_file_exists():
    assert DOMAIN_PROFILE_PATH.exists()


def test_legacy_industry_profile_is_thin_facade():
    text = LEGACY_PROFILE_PATH.read_text(encoding="utf-8")
    assert "app.domains.content_collection" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def load_profile" not in text
    assert "def list_industries" not in text
    assert _line_count(LEGACY_PROFILE_PATH) <= 12


def test_legacy_industry_profile_module_is_domain_module():
    legacy = importlib.import_module("app.services.industry_profile_service")
    domain = importlib.import_module("app.domains.content_collection.industry_profile_service")
    assert legacy is domain
    assert legacy.load_profile is domain.load_profile
    assert legacy.list_industries is domain.list_industries


def test_services_parent_package_industry_profile_attribute_is_domain_module():
    from app.services import industry_profile_service as parent_import

    domain = importlib.import_module("app.domains.content_collection.industry_profile_service")
    assert parent_import is domain


def test_content_collection_mutations_import_domain_industry_profile_only():
    text = MUTATIONS_PATH.read_text(encoding="utf-8")
    assert "app.domains.content_collection.industry_profile_service" in text
    assert "app.services.industry_profile_service" not in text


def test_content_collection_docs_register_industry_profile_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.content_collection.industry_profile_service",
        "app.services.industry_profile_service",
        "load_profile",
        "server/app/data/industry_profiles",
    ]:
        assert term in readme


def test_industry_profile_fallback_and_list_stay_legacy_compatible():
    legacy = importlib.import_module("app.services.industry_profile_service")
    domain = importlib.import_module("app.domains.content_collection.industry_profile_service")
    profile = legacy.load_profile("missing-industry")
    industries = legacy.list_industries()
    assert Path(domain.PROFILES_DIR).resolve() == (
        REPO_ROOT / "server/app/data/industry_profiles"
    ).resolve()
    assert profile["industry"] == "general"
    assert profile["label"] == "通用"
    assert any(item["key"] == "general" for item in industries)


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

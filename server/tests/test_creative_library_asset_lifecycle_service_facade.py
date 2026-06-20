import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-creative-asset-lifecycle-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-creative-asset-lifecycle-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/creative_library/asset_lifecycle_service.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/asset_lifecycle_service.py"
CHARACTERS_ROUTER_PATH = REPO_ROOT / "server/app/domains/creative_library/characters_router.py"
SCENES_ROUTER_PATH = REPO_ROOT / "server/app/domains/creative_library/scenes_router.py"
README_PATH = REPO_ROOT / "server/app/domains/creative_library/README.md"


def test_asset_lifecycle_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.creative_library.asset_lifecycle_service",
        "app.services.asset_lifecycle_service",
        "AssetLifecycleError",
        "archive_character_or_scene",
    ]:
        assert term in spec
        assert term in plan


def test_asset_lifecycle_domain_file_exists():
    assert DOMAIN_PATH.exists()


def test_legacy_asset_lifecycle_service_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.creative_library" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def archive_character_or_scene" not in text
    assert "class AssetLifecycleError" not in text
    assert _line_count(LEGACY_PATH) <= 12


def test_legacy_asset_lifecycle_module_is_domain_module():
    legacy = importlib.import_module("app.services.asset_lifecycle_service")
    domain = importlib.import_module("app.domains.creative_library.asset_lifecycle_service")
    assert legacy is domain
    assert legacy.AssetLifecycleError is domain.AssetLifecycleError
    assert legacy.archive_character_or_scene is domain.archive_character_or_scene


def test_services_parent_package_asset_lifecycle_attribute_is_domain_module():
    from app.services import asset_lifecycle_service as parent_import

    domain = importlib.import_module("app.domains.creative_library.asset_lifecycle_service")
    assert parent_import is domain


def test_creative_library_routers_import_domain_asset_lifecycle_service():
    for path in [CHARACTERS_ROUTER_PATH, SCENES_ROUTER_PATH]:
        text = path.read_text(encoding="utf-8")
        assert "app.domains.creative_library.asset_lifecycle_service" in text
        assert "app.services.asset_lifecycle_service" not in text


def test_creative_library_docs_register_asset_lifecycle_service_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "asset_lifecycle_service.py",
        "AssetLifecycleError",
        "app.services.asset_lifecycle_service",
        "app.domains.creative_library.asset_lifecycle_service",
    ]:
        assert term in readme


def test_legacy_path_exports_same_error_class():
    from app.services.asset_lifecycle_service import AssetLifecycleError as legacy_error

    domain = importlib.import_module("app.domains.creative_library.asset_lifecycle_service")
    err = legacy_error("CODE", "Message", {"id": "1"})
    assert isinstance(err, domain.AssetLifecycleError)
    assert err.details == {"id": "1"}


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

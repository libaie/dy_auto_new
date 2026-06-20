import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-creative-anchor-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-creative-anchor-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/creative_library/anchor_service.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/anchor_service.py"
README_PATH = REPO_ROOT / "server/app/domains/creative_library/README.md"
REFERENCE_ASSET_PATH = REPO_ROOT / "server/app/domains/creative_library/reference_asset_service.py"


def test_anchor_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.creative_library.anchor_service",
        "app.services.anchor_service",
        "AssetAnchorManager",
        "reference_asset_service",
    ]:
        assert term in spec
        assert term in plan


def test_anchor_service_domain_file_exists():
    assert DOMAIN_PATH.exists()


def test_legacy_anchor_service_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.creative_library" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "class AssetAnchorManager" not in text
    assert "def _resolve_seed" not in text
    assert _line_count(LEGACY_PATH) <= 12


def test_legacy_anchor_service_module_is_domain_module():
    legacy = importlib.import_module("app.services.anchor_service")
    domain = importlib.import_module("app.domains.creative_library.anchor_service")
    assert legacy is domain
    assert legacy.AssetAnchorManager is domain.AssetAnchorManager
    assert legacy._resolve_seed is domain._resolve_seed


def test_services_parent_package_anchor_service_attribute_is_domain_module():
    from app.services import anchor_service as parent_import

    domain = importlib.import_module("app.domains.creative_library.anchor_service")
    assert parent_import is domain


def test_domain_anchor_service_imports_domain_reference_asset_service():
    text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "app.domains.creative_library.reference_asset_service" in text
    assert "app.services.reference_asset_service" not in text


def test_same_domain_reference_asset_service_imports_domain_anchor_service():
    text = REFERENCE_ASSET_PATH.read_text(encoding="utf-8")
    assert "app.domains.creative_library.anchor_service" in text
    assert "app.services.anchor_service" not in text


def test_creative_library_docs_register_anchor_service_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "anchor_service.py",
        "AssetAnchorManager",
        "app.services.anchor_service",
        "app.domains.creative_library.anchor_service",
    ]:
        assert term in readme


def test_legacy_monkeypatch_is_visible_on_domain_module(monkeypatch):
    legacy = importlib.import_module("app.services.anchor_service")
    domain = importlib.import_module("app.domains.creative_library.anchor_service")

    def fake_resolve_seed(seed, existing_seed, fallback_key):
        return 123

    monkeypatch.setattr("app.services.anchor_service._resolve_seed", fake_resolve_seed)

    assert domain._resolve_seed(None, None, "x") == 123
    assert legacy._resolve_seed is domain._resolve_seed


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

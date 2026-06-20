import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-model-registry-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-model-registry-domain-plan.md"
DOMAIN_REGISTRY_PATH = REPO_ROOT / "server/app/domains/model_configuration/model_registry.py"
LEGACY_REGISTRY_PATH = REPO_ROOT / "server/app/services/model_registry.py"
AUDIT_ROUTER_PATH = REPO_ROOT / "server/app/domains/quality_audit/audit_router.py"
VIDEO_SERVICE_PATH = REPO_ROOT / "server/app/domains/video_production/video_production_service.py"
README_PATH = REPO_ROOT / "server/app/domains/model_configuration/README.md"


def test_model_registry_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.model_configuration.model_registry",
        "app.services.model_registry",
        "get_model_for_scene",
    ]:
        assert term in spec
        assert term in plan


def test_model_registry_domain_file_exists():
    assert DOMAIN_REGISTRY_PATH.exists()


def test_legacy_model_registry_is_thin_facade():
    text = LEGACY_REGISTRY_PATH.read_text(encoding="utf-8")
    assert "app.domains.model_configuration" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def get_model_for_scene" not in text
    assert "class ModelResolutionError" not in text
    assert _line_count(LEGACY_REGISTRY_PATH) <= 12


def test_legacy_model_registry_module_is_domain_module():
    legacy = importlib.import_module("app.services.model_registry")
    domain = importlib.import_module("app.domains.model_configuration.model_registry")
    assert legacy is domain
    assert legacy.ModelResolutionError is domain.ModelResolutionError
    assert legacy.get_model_for_scene is domain.get_model_for_scene
    assert legacy._get_scene_label is domain._get_scene_label


def test_services_parent_package_model_registry_attribute_is_domain_module():
    from app.services import model_registry as parent_import

    domain = importlib.import_module("app.domains.model_configuration.model_registry")
    assert parent_import is domain


def test_quality_audit_imports_domain_model_registry_only():
    text = AUDIT_ROUTER_PATH.read_text(encoding="utf-8")
    assert "app.domains.model_configuration.model_registry" in text
    assert "app.services.model_registry" not in text


def test_video_production_imports_domain_model_registry_directly():
    text = VIDEO_SERVICE_PATH.read_text(encoding="utf-8")
    assert "app.domains.model_configuration.model_registry" in text
    assert "app.services.model_registry" not in text


def test_model_configuration_docs_register_model_registry_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.model_configuration.model_registry",
        "app.services.model_registry",
        "get_model_for_scene",
        "remove only after import inventory shows no production legacy imports",
    ]:
        assert term in readme


def test_model_registry_error_identity_stays_legacy_compatible():
    legacy = importlib.import_module("app.services.model_registry")
    err = legacy.ModelResolutionError("quality_audit", "repair", status_code=409)
    assert err.scene_key == "quality_audit"
    assert err.repair_action == "repair"
    assert err.status_code == 409


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

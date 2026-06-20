import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-model-schema-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-model-schema-domain-plan.md"
DOMAIN_SCHEMA_PATH = REPO_ROOT / "server/app/domains/model_configuration/model_schema.py"
LEGACY_SCHEMA_PATH = REPO_ROOT / "server/app/services/model_schema.py"
ROUTER_PATH = REPO_ROOT / "server/app/domains/model_configuration/ai_models_router.py"
README_PATH = REPO_ROOT / "server/app/domains/model_configuration/README.md"


def test_model_schema_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.model_configuration.model_schema",
        "app.services.model_schema",
        "get_schema_payload",
    ]:
        assert term in spec
        assert term in plan


def test_model_schema_domain_file_exists():
    assert DOMAIN_SCHEMA_PATH.exists()


def test_legacy_model_schema_is_thin_facade():
    text = LEGACY_SCHEMA_PATH.read_text(encoding="utf-8")
    assert "app.domains.model_configuration" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def get_schema_payload" not in text
    assert "def get_provider_preset" not in text
    assert _line_count(LEGACY_SCHEMA_PATH) <= 12


def test_legacy_model_schema_module_is_domain_module():
    legacy = importlib.import_module("app.services.model_schema")
    domain = importlib.import_module("app.domains.model_configuration.model_schema")
    assert legacy is domain
    assert legacy.get_schema_payload is domain.get_schema_payload
    assert legacy.get_provider_preset is domain.get_provider_preset
    assert legacy.get_scene_by_key is domain.get_scene_by_key
    assert legacy.get_providers_for_scene is domain.get_providers_for_scene


def test_services_parent_package_model_schema_attribute_is_domain_module():
    from app.services import model_schema as parent_import

    domain = importlib.import_module("app.domains.model_configuration.model_schema")
    assert parent_import is domain


def test_ai_models_router_imports_domain_model_schema_only():
    text = ROUTER_PATH.read_text(encoding="utf-8")
    assert "app.domains.model_configuration.model_schema" in text
    assert "app.services.model_schema" not in text


def test_model_configuration_docs_register_model_schema_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.model_configuration.model_schema",
        "app.services.model_schema",
        "get_schema_payload",
        "raw schema data stays in `app.data.model_schema_data`",
    ]:
        assert term in readme


def test_model_schema_provider_fallback_stays_legacy_compatible():
    legacy = importlib.import_module("app.services.model_schema")
    preset = legacy.get_provider_preset("unknown_provider_xyz")
    assert preset["label"] == "unknown_provider_xyz"
    assert preset["test_strategy"] == "health_check"


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

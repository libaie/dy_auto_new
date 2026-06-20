import importlib
from pathlib import Path

from app.db_models import AIModel
from app.services.crypto import encrypt


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-runtime-model-config-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-runtime-model-config-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/model_configuration/runtime_model_config.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/runtime_model_config.py"
README_PATH = REPO_ROOT / "server/app/domains/model_configuration/README.md"
DOMAIN_CALLER_PATHS = [
    REPO_ROOT / "server/app/domains/image_generation/image_model_selection_service.py",
    REPO_ROOT / "server/app/domains/script_pipeline/script_pipeline_service.py",
    REPO_ROOT / "server/app/domains/script_pipeline/pipeline_router.py",
    REPO_ROOT / "server/app/domains/director_planning/director_router.py",
    REPO_ROOT / "server/app/domains/ai_video_series/story_generator_expert.py",
    REPO_ROOT / "server/app/domains/ai_video_series/style_lock.py",
]


def test_runtime_model_config_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.model_configuration.runtime_model_config",
        "app.services.runtime_model_config",
        "resolve_runtime_model_config",
        "resolve_image_model_for_capability",
        "redact_runtime_model_config",
    ]:
        assert term in spec
        assert term in plan


def test_runtime_model_config_domain_file_exists():
    assert DOMAIN_PATH.exists()


def test_legacy_runtime_model_config_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.model_configuration" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def resolve_runtime_model_config" not in text
    assert "def redact_runtime_model_config" not in text
    assert _line_count(LEGACY_PATH) <= 12


def test_legacy_runtime_model_config_module_is_domain_module():
    legacy = importlib.import_module("app.services.runtime_model_config")
    domain = importlib.import_module("app.domains.model_configuration.runtime_model_config")
    assert legacy is domain
    assert legacy.RuntimeModelConfigError is domain.RuntimeModelConfigError
    assert legacy.resolve_runtime_model_config is domain.resolve_runtime_model_config
    assert legacy.resolve_image_model_for_capability is domain.resolve_image_model_for_capability
    assert legacy.redact_runtime_model_config is domain.redact_runtime_model_config


def test_services_parent_package_runtime_model_config_attribute_is_domain_module():
    from app.services import runtime_model_config as parent_import

    domain = importlib.import_module("app.domains.model_configuration.runtime_model_config")
    assert parent_import is domain


def test_clean_domain_callers_import_domain_runtime_model_config():
    for path in DOMAIN_CALLER_PATHS:
        text = path.read_text(encoding="utf-8")
        assert "app.domains.model_configuration.runtime_model_config" in text
        assert "app.services.runtime_model_config" not in text


def test_model_configuration_docs_register_runtime_model_config_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.model_configuration.runtime_model_config",
        "app.services.runtime_model_config",
        "resolve_runtime_model_config",
        "approved compatibility imports",
    ]:
        assert term in readme


def test_resolve_runtime_model_config_stays_legacy_compatible(db):
    from app.services.runtime_model_config import resolve_runtime_model_config

    model = AIModel(
        name="Runtime config test",
        model_type="llm",
        provider="openai-compatible",
        base_url="https://llm.example.test/v1",
        api_key=encrypt("runtime-secret"),
        model_name="runtime-model",
        enabled=True,
        config_json={"scene_key": "script_generation", "config_version": 11},
    )
    db.add(model)
    db.commit()

    resolved = resolve_runtime_model_config(db, "script_generation")

    assert resolved["model_id"] == model.id
    assert resolved["api_key"] == "runtime-secret"
    assert resolved["config_version"] == 11


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

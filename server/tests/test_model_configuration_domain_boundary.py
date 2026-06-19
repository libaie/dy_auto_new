import importlib.util
from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-model-configuration-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-model-configuration-domain-plan.md"
MAIN_PATH = REPO_ROOT / "server/app/main.py"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/model_configuration"
README_PATH = DOMAIN_PATH / "README.md"
LEGACY_AI_CONFIG_PATH = REPO_ROOT / "server/app/routers/ai_config.py"
SYSTEM_OPERATIONS_PATH = REPO_ROOT / "server/app/domains/system_operations"


def test_model_configuration_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.model_configuration",
        "ai_models_router.py",
        "app.routers.ai_config",
        "/api/ai-models",
        "AIModel",
        "DEFAULT_MODELS",
        "seed_ai_models",
        "ModelCreate",
        "ModelUpdate",
    ]:
        assert term in spec
        assert term in plan


def test_model_configuration_domain_exports_metadata():
    spec = importlib.util.find_spec("app.domains.model_configuration")
    assert spec is not None

    import app.domains.model_configuration as domain

    assert domain.DOMAIN_NAME == "model_configuration"
    assert domain.PUBLIC_ROUTE_PREFIX == "/api/ai-models"


def test_model_configuration_readme_documents_facade_and_cleanup_gates():
    assert README_PATH.exists()
    text = README_PATH.read_text(encoding="utf-8")

    for term in [
        "Facade Register",
        "app.routers.ai_config",
        "app.domains.model_configuration.ai_models_router",
        "DEFAULT_MODELS",
        "seed_ai_models",
        "AIModel",
        "Compatibility Cleanup Gates",
    ]:
        assert term in text


def test_model_configuration_owns_router_module():
    assert (DOMAIN_PATH / "ai_models_router.py").exists()


def test_model_configuration_legacy_router_file_is_thin_facade():
    text = LEGACY_AI_CONFIG_PATH.read_text(encoding="utf-8")

    assert "app.domains.model_configuration" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "APIRouter(" not in text
    assert _line_count(LEGACY_AI_CONFIG_PATH) <= 20


def test_model_configuration_main_wires_domain_router_and_seed_helper():
    text = MAIN_PATH.read_text(encoding="utf-8")

    assert "from app.domains.model_configuration import ai_models_router" in text
    assert "from app.domains.model_configuration.ai_models_router import seed_ai_models" in text
    assert "app.include_router(ai_models_router.router)" in text
    assert "app.include_router(ai_config.router)" not in text
    assert "from app.routers.ai_config import seed_ai_models" not in text


def test_model_configuration_keeps_system_operations_separate():
    operations_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in SYSTEM_OPERATIONS_PATH.glob("*.py")
    )

    assert "app.domains.model_configuration" not in operations_text
    assert "ai_models_router" not in operations_text


def test_app_import_smoke_keeps_model_configuration_routes_registered_once():
    from app.main import app

    route_keys = [
        (route.path, tuple(sorted(route.methods)))
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/ai-models")
    ]
    paths = {path for path, _methods in route_keys}

    assert len(route_keys) == len(set(route_keys))
    assert "/api/ai-models" in paths
    assert "/api/ai-models/options" in paths
    assert "/api/ai-models/schema" in paths
    assert "/api/ai-models/{model_id}" in paths
    assert "/api/ai-models/{model_id}/test" in paths


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

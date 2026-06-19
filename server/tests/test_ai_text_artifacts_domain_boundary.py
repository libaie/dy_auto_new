import importlib.util
from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-ai-text-artifacts-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-ai-text-artifacts-domain-plan.md"
MAIN_PATH = REPO_ROOT / "server/app/main.py"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/ai_text_artifacts"
README_PATH = DOMAIN_PATH / "README.md"
LEGACY_ROUTER_PATH = REPO_ROOT / "server/app/routers/ai_text_artifacts.py"


def test_ai_text_artifacts_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.ai_text_artifacts",
        "ai_text_artifacts_router.py",
        "app.routers.ai_text_artifacts",
        "/api/ai-text-artifacts",
        "ArtifactEditRequest",
        "ArtifactRegenerateRequest",
        "_actor_id",
        "_artifact_dict",
        "AITextArtifactService",
    ]:
        assert term in spec
        assert term in plan


def test_ai_text_artifacts_domain_exports_metadata():
    spec = importlib.util.find_spec("app.domains.ai_text_artifacts")
    assert spec is not None

    import app.domains.ai_text_artifacts as domain

    assert domain.DOMAIN_NAME == "ai_text_artifacts"
    assert domain.PUBLIC_ROUTE_PREFIX == "/api/ai-text-artifacts"


def test_ai_text_artifacts_readme_documents_facade_and_cleanup_gates():
    assert README_PATH.exists()
    text = README_PATH.read_text(encoding="utf-8")

    for term in [
        "Facade Register",
        "app.routers.ai_text_artifacts",
        "app.domains.ai_text_artifacts.ai_text_artifacts_router",
        "ArtifactEditRequest",
        "ArtifactRegenerateRequest",
        "_actor_id",
        "_artifact_dict",
        "Compatibility Cleanup Gates",
    ]:
        assert term in text


def test_ai_text_artifacts_domain_owns_router_module():
    assert (DOMAIN_PATH / "ai_text_artifacts_router.py").exists()


def test_ai_text_artifacts_legacy_router_file_is_thin_facade():
    text = LEGACY_ROUTER_PATH.read_text(encoding="utf-8")

    assert "app.domains.ai_text_artifacts" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "APIRouter(" not in text
    assert _line_count(LEGACY_ROUTER_PATH) <= 20


def test_ai_text_artifacts_main_wires_domain_router():
    text = MAIN_PATH.read_text(encoding="utf-8")

    assert "from app.domains.ai_text_artifacts import ai_text_artifacts_router" in text
    assert "app.include_router(ai_text_artifacts_router.router)" in text
    assert "app.include_router(ai_text_artifacts.router)" not in text


def test_app_import_smoke_keeps_ai_text_artifact_routes_registered_once():
    from app.main import app

    route_keys = [
        (route.path, tuple(sorted(route.methods)))
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/ai-text-artifacts")
    ]
    paths = {path for path, _methods in route_keys}

    assert len(route_keys) == len(set(route_keys))
    assert "/api/ai-text-artifacts" in paths
    assert "/api/ai-text-artifacts/{artifact_id}" in paths
    assert "/api/ai-text-artifacts/{artifact_id}/lineage" in paths
    assert "/api/ai-text-artifacts/{artifact_id}/edit" in paths
    assert "/api/ai-text-artifacts/{artifact_id}/approve" in paths
    assert "/api/ai-text-artifacts/{artifact_id}/regenerate" in paths


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

import importlib.util
from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-director-planning-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-director-planning-domain-plan.md"
MAIN_PATH = REPO_ROOT / "server/app/main.py"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/director_planning"
README_PATH = DOMAIN_PATH / "README.md"
LEGACY_DIRECTOR_PATH = REPO_ROOT / "server/app/routers/director.py"
SCRIPT_PIPELINE_PATH = REPO_ROOT / "server/app/domains/script_pipeline/pipeline_router.py"


def test_director_planning_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.director_planning",
        "director_router.py",
        "app.routers.director",
        "/api/director",
        "DirectorAutoPlanRequest",
        "EpisodePlanRequest",
        "generate_auto_storyboard",
        "_normalize_auto_frames",
        "AITextArtifactService",
    ]:
        assert term in spec
        assert term in plan


def test_director_planning_domain_exports_metadata():
    spec = importlib.util.find_spec("app.domains.director_planning")
    assert spec is not None

    import app.domains.director_planning as domain

    assert domain.DOMAIN_NAME == "director_planning"
    assert domain.PUBLIC_ROUTE_PREFIX == "/api/director"


def test_director_planning_readme_documents_facade_and_cleanup_gates():
    assert README_PATH.exists()
    text = README_PATH.read_text(encoding="utf-8")

    for term in [
        "Facade Register",
        "app.routers.director",
        "app.domains.director_planning.director_router",
        "DirectorAutoPlanRequest",
        "EpisodePlanRequest",
        "_normalize_auto_frames",
        "AITextArtifactService",
        "Compatibility Cleanup Gates",
    ]:
        assert term in text


def test_director_planning_owns_router_module():
    assert (DOMAIN_PATH / "director_router.py").exists()


def test_director_planning_legacy_router_file_is_thin_facade():
    text = LEGACY_DIRECTOR_PATH.read_text(encoding="utf-8")

    assert "app.domains.director_planning" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "APIRouter(" not in text
    assert _line_count(LEGACY_DIRECTOR_PATH) <= 20


def test_director_planning_main_wires_domain_router():
    text = MAIN_PATH.read_text(encoding="utf-8")

    assert "from app.domains.director_planning import director_router" in text
    assert "app.include_router(director_router.router)" in text
    assert "app.include_router(director.router)" not in text


def test_script_pipeline_keeps_director_route_as_external_dependency_only():
    text = SCRIPT_PIPELINE_PATH.read_text(encoding="utf-8")

    assert "app.domains.director_planning" not in text
    assert "/api/director/auto-plan" in text


def test_app_import_smoke_keeps_director_planning_routes_registered_once():
    from app.main import app

    route_keys = [
        (route.path, tuple(sorted(route.methods)))
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/director")
    ]
    paths = {path for path, _methods in route_keys}

    assert len(route_keys) == len(set(route_keys))
    assert "/api/director/auto-plan" in paths
    assert "/api/director/episode-production-plan" in paths
    assert "/api/director/episode-plan" in paths
    assert "/api/director/shot-segments" in paths
    assert "/api/director/plan" in paths


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

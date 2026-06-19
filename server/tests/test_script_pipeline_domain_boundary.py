import importlib.util
from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-script-pipeline-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-script-pipeline-domain-plan.md"
MAIN_PATH = REPO_ROOT / "server/app/main.py"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/script_pipeline"
SERVICE_SCRIPT_PIPELINE_PATH = REPO_ROOT / "server/app/services/script_pipeline.py"
README_PATH = DOMAIN_PATH / "README.md"
LEGACY_PIPELINE_PATH = REPO_ROOT / "server/app/routers/pipeline.py"


def test_script_pipeline_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.script_pipeline",
        "pipeline_router.py",
        "app.routers.pipeline",
        "/api/pipeline",
        "PipelineStartRequest",
        "PipelineRun",
        "Episode.storyboard_json",
        "_run_all_layers",
        "app.services.script_pipeline",
    ]:
        assert term in spec
        assert term in plan


def test_script_pipeline_domain_exports_metadata():
    spec = importlib.util.find_spec("app.domains.script_pipeline")
    assert spec is not None

    import app.domains.script_pipeline as domain

    assert domain.DOMAIN_NAME == "script_pipeline"
    assert domain.PUBLIC_ROUTE_PREFIX == "/api/pipeline"


def test_script_pipeline_readme_documents_facade_and_cleanup_gates():
    assert README_PATH.exists()
    text = README_PATH.read_text(encoding="utf-8")

    for term in [
        "Facade Register",
        "app.routers.pipeline",
        "app.domains.script_pipeline.pipeline_router",
        "PipelineStartRequest",
        "_run_all_layers",
        "_submit_and_poll",
        "app.services.script_pipeline",
        "Compatibility Cleanup Gates",
    ]:
        assert term in text


def test_script_pipeline_owns_router_module():
    assert (DOMAIN_PATH / "pipeline_router.py").exists()


def test_script_pipeline_legacy_router_file_is_thin_facade():
    text = LEGACY_PIPELINE_PATH.read_text(encoding="utf-8")

    assert "app.domains.script_pipeline" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "APIRouter(" not in text
    assert _line_count(LEGACY_PIPELINE_PATH) <= 20


def test_script_pipeline_main_keeps_legacy_router_until_direct_wiring_step():
    text = MAIN_PATH.read_text(encoding="utf-8")

    assert "from app.routers import" in text
    assert "pipeline" in text
    assert "app.include_router(pipeline.router)" in text
    assert "from app.domains.script_pipeline import pipeline_router" not in text
    assert "app.include_router(pipeline_router.router)" not in text


def test_script_pipeline_service_layer_stays_router_free():
    text = SERVICE_SCRIPT_PIPELINE_PATH.read_text(encoding="utf-8")

    assert "app.domains.script_pipeline" not in text
    assert "pipeline_router" not in text


def test_app_import_smoke_keeps_script_pipeline_routes_registered_once():
    from app.main import app

    route_keys = [
        (route.path, tuple(sorted(route.methods)))
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/pipeline")
    ]
    paths = {path for path, _methods in route_keys}

    assert len(route_keys) == len(set(route_keys))
    assert "/api/pipeline/start" in paths
    assert "/api/pipeline/runs/{series_id}" in paths
    assert "/api/pipeline/runs/by-id/{run_id}" in paths
    assert "/api/pipeline/runs/{series_id}/{run_id}" in paths


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

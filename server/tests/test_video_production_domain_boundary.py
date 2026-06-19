import importlib.util
from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-domain-plan.md"
MAIN_PATH = REPO_ROOT / "server/app/main.py"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/video_production"
README_PATH = DOMAIN_PATH / "README.md"
LEGACY_ROUTER_PATH = REPO_ROOT / "server/app/routers/video_production.py"


def test_video_production_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production",
        "video_production_router.py",
        "app.routers.video_production",
        "/api/video-production",
        "StartRunRequest",
        "OneSentenceVideoRequest",
        "_run_payload",
        "_asset_payload",
        "_provider_stage_task_payload",
        "create_one_sentence_video",
        "start_image_stage",
    ]:
        assert term in spec
        assert term in plan


def test_video_production_domain_exports_metadata():
    spec = importlib.util.find_spec("app.domains.video_production")
    assert spec is not None

    import app.domains.video_production as domain

    assert domain.DOMAIN_NAME == "video_production"
    assert domain.PUBLIC_ROUTE_PREFIX == "/api/video-production"


def test_video_production_readme_documents_facade_and_cleanup_gates():
    assert README_PATH.exists()
    text = README_PATH.read_text(encoding="utf-8")

    for term in [
        "Facade Register",
        "app.routers.video_production",
        "app.domains.video_production.video_production_router",
        "StartRunRequest",
        "OneSentenceVideoRequest",
        "_run_payload",
        "_asset_payload",
        "Compatibility Cleanup Gates",
    ]:
        assert term in text


def test_video_production_domain_owns_router_module():
    assert (DOMAIN_PATH / "video_production_router.py").exists()


def test_video_production_legacy_router_file_is_thin_facade():
    text = LEGACY_ROUTER_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_production" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "APIRouter(" not in text
    assert _line_count(LEGACY_ROUTER_PATH) <= 20


def test_video_production_main_wires_domain_router():
    text = MAIN_PATH.read_text(encoding="utf-8")

    assert "from app.domains.video_production import video_production_router" in text
    assert "app.include_router(video_production_router.router)" in text
    assert "app.include_router(video_production.router)" not in text


def test_app_import_smoke_keeps_video_production_routes_registered_once():
    from app.main import app

    route_keys = [
        (route.path, tuple(sorted(route.methods)))
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/video-production")
    ]

    assert len(route_keys) == len(set(route_keys))
    assert len(route_keys) == 33
    assert ("/api/video-production/runs/start", ("POST",)) in route_keys
    assert ("/api/video-production/one-sentence", ("POST",)) in route_keys
    assert ("/api/video-production/review-items", ("GET",)) in route_keys
    assert ("/api/video-production/assets/{asset_id}/image-edit", ("POST",)) in route_keys
    assert ("/api/video-production/runs/{run_id}/worker-step", ("POST",)) in route_keys


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

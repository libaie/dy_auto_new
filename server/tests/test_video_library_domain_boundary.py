import importlib.util
from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-library-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-library-domain-plan.md"
MAIN_PATH = REPO_ROOT / "server/app/main.py"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/video_library"
README_PATH = DOMAIN_PATH / "README.md"
LEGACY_VIDEOS_PATH = REPO_ROOT / "server/app/routers/videos.py"


def test_video_library_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_library",
        "videos_router.py",
        "app.routers.videos",
        "/api/videos",
        "app.routers.video_production",
        "Pixelle",
        "Seedance",
    ]:
        assert term in spec
        assert term in plan


def test_video_library_domain_exports_metadata():
    spec = importlib.util.find_spec("app.domains.video_library")
    assert spec is not None

    import app.domains.video_library as domain

    assert domain.DOMAIN_NAME == "video_library"
    assert domain.PUBLIC_ROUTE_PREFIX == "/api/videos"


def test_video_library_readme_documents_facade_and_cleanup_gates():
    assert README_PATH.exists()
    text = README_PATH.read_text(encoding="utf-8")

    for term in [
        "Facade Register",
        "app.routers.videos",
        "app.domains.video_library.videos_router",
        "app.routers.video_production",
        "Pixelle",
        "Seedance",
        "Compatibility Cleanup Gates",
    ]:
        assert term in text


def test_video_library_owns_router_module():
    assert (DOMAIN_PATH / "videos_router.py").exists()


def test_video_library_legacy_router_file_is_thin_facade():
    text = LEGACY_VIDEOS_PATH.read_text(encoding="utf-8")

    assert "app.domains.video_library" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "APIRouter(" not in text
    assert _line_count(LEGACY_VIDEOS_PATH) <= 20


def test_video_library_main_wires_domain_router():
    text = MAIN_PATH.read_text(encoding="utf-8")

    assert "from app.domains.video_library import videos_router" in text
    assert "app.include_router(videos_router.router)" in text
    assert "app.include_router(videos.router)" not in text


def test_video_library_does_not_own_production_or_provider_routes():
    if not DOMAIN_PATH.exists():
        assert True
        return

    domain_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in DOMAIN_PATH.glob("*.py")
    )

    assert "app.routers.video_production" not in domain_text
    assert "app.routers.pixelle" not in domain_text
    assert "app.routers.seedance" not in domain_text
    assert "include_router(" not in domain_text


def test_app_import_smoke_keeps_video_library_routes_registered_once():
    from app.main import app

    route_keys = [
        (route.path, tuple(sorted(route.methods)))
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/videos")
    ]
    paths = {path for path, _methods in route_keys}

    assert len(route_keys) == len(set(route_keys))
    assert "/api/videos" in paths
    assert "/api/videos/{video_id}" in paths
    assert "/api/videos/{video_id}/download" in paths


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

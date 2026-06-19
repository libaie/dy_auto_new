import importlib.util
from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-storyboard-images-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-storyboard-images-domain-plan.md"
MAIN_PATH = REPO_ROOT / "server/app/main.py"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/storyboard_images"
README_PATH = DOMAIN_PATH / "README.md"
LEGACY_ROUTER_PATH = REPO_ROOT / "server/app/routers/storyboard_images.py"


def test_storyboard_images_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.storyboard_images",
        "storyboard_images_router.py",
        "app.routers.storyboard_images",
        "/api/storyboard-images",
        "StoryboardImageTaskRequest",
        "PromoteStoryboardImageRequest",
        "_auth_user_id",
        "create_storyboard_frame_image_task",
        "promote_storyboard_image_asset",
    ]:
        assert term in spec
        assert term in plan


def test_storyboard_images_domain_exports_metadata():
    spec = importlib.util.find_spec("app.domains.storyboard_images")
    assert spec is not None

    import app.domains.storyboard_images as domain

    assert domain.DOMAIN_NAME == "storyboard_images"
    assert domain.PUBLIC_ROUTE_PREFIX == "/api/storyboard-images"


def test_storyboard_images_readme_documents_facade_and_cleanup_gates():
    assert README_PATH.exists()
    text = README_PATH.read_text(encoding="utf-8")

    for term in [
        "Facade Register",
        "app.routers.storyboard_images",
        "app.domains.storyboard_images.storyboard_images_router",
        "StoryboardImageTaskRequest",
        "PromoteStoryboardImageRequest",
        "_auth_user_id",
        "Compatibility Cleanup Gates",
    ]:
        assert term in text


def test_storyboard_images_domain_owns_router_module():
    assert (DOMAIN_PATH / "storyboard_images_router.py").exists()


def test_storyboard_images_legacy_router_file_is_thin_facade():
    text = LEGACY_ROUTER_PATH.read_text(encoding="utf-8")

    assert "app.domains.storyboard_images" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "APIRouter(" not in text
    assert _line_count(LEGACY_ROUTER_PATH) <= 20


def test_storyboard_images_main_wires_domain_router():
    text = MAIN_PATH.read_text(encoding="utf-8")

    assert "from app.domains.storyboard_images import storyboard_images_router" in text
    assert "app.include_router(storyboard_images_router.router)" in text
    assert "app.include_router(storyboard_images.router)" not in text


def test_app_import_smoke_keeps_storyboard_image_routes_registered_once():
    from app.main import app

    route_keys = [
        (route.path, tuple(sorted(route.methods)))
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/storyboard-images")
    ]
    paths = {path for path, _methods in route_keys}

    assert len(route_keys) == len(set(route_keys))
    assert "/api/storyboard-images/episodes/{episode_id}/frames/{frame_id}/tasks" in paths
    assert "/api/storyboard-images/episodes/{episode_id}/tasks:batch" in paths
    assert "/api/storyboard-images/episodes/{episode_id}" in paths
    assert "/api/storyboard-images/assets/{asset_id}/promote" in paths


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

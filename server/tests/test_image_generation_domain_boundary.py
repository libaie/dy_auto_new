from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-image-generation-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-image-generation-domain-plan.md"
MAIN_PATH = REPO_ROOT / "server/app/main.py"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/image_generation"
README_PATH = DOMAIN_PATH / "README.md"
LEGACY_IMAGE_CREATION_PATH = REPO_ROOT / "server/app/routers/image_creation.py"
LEGACY_IMAGE_PRODUCTION_PATH = REPO_ROOT / "server/app/routers/image_production.py"


def test_image_generation_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.image_generation",
        "image_creation_router.py",
        "image_production_router.py",
        "app.routers.image_creation",
        "app.routers.image_production",
        "/api/image-creation",
        "/api/image-production",
    ]:
        assert term in spec
        assert term in plan


def test_image_generation_domain_exports_metadata():
    import app.domains.image_generation as domain

    assert domain.DOMAIN_NAME == "image_generation"
    assert domain.PUBLIC_ROUTE_PREFIXES == ("/api/image-creation", "/api/image-production")


def test_image_generation_readme_documents_facades_and_cleanup_gates():
    text = README_PATH.read_text(encoding="utf-8")

    for term in [
        "Facade Register",
        "app.routers.image_creation",
        "app.routers.image_production",
        "app.domains.image_generation.image_creation_router",
        "app.domains.image_generation.image_production_router",
        "Compatibility Cleanup Gates",
    ]:
        assert term in text


def test_image_generation_owns_router_modules():
    assert (DOMAIN_PATH / "image_creation_router.py").exists()
    assert (DOMAIN_PATH / "image_production_router.py").exists()


def test_image_generation_legacy_router_files_are_thin_facades():
    creation_text = LEGACY_IMAGE_CREATION_PATH.read_text(encoding="utf-8")
    production_text = LEGACY_IMAGE_PRODUCTION_PATH.read_text(encoding="utf-8")

    assert "app.domains.image_generation" in creation_text
    assert "app.domains.image_generation" in production_text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in creation_text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in production_text
    assert 'APIRouter(prefix="/api/image-creation"' not in creation_text
    assert 'APIRouter(prefix="/api/image-production"' not in production_text
    assert _line_count(LEGACY_IMAGE_CREATION_PATH) <= 20
    assert _line_count(LEGACY_IMAGE_PRODUCTION_PATH) <= 20


def test_image_generation_main_wiring_remains_legacy_until_pr4():
    text = MAIN_PATH.read_text(encoding="utf-8")

    assert "from app.routers import image_creation, image_production" in text
    assert "app.include_router(image_creation.router)" in text
    assert "app.include_router(image_production.router)" in text


def test_app_import_smoke_keeps_image_generation_routes_registered_once():
    from app.main import app

    route_keys = [
        (route.path, tuple(sorted(route.methods)))
        for route in app.routes
        if isinstance(route, APIRoute)
        and (route.path.startswith("/api/image-creation") or route.path.startswith("/api/image-production"))
    ]
    paths = {path for path, _methods in route_keys}

    assert len(route_keys) == len(set(route_keys))
    assert "/api/image-creation/tasks" in paths
    assert "/api/image-creation/assets/{asset_id}/edit" in paths
    assert "/api/image-production/strategies" in paths
    assert "/api/image-production/ab-tests/{group_id}/winner/{attempt_id}" in paths


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

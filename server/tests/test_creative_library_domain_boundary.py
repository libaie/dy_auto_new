from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-creative-library-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-creative-library-domain-plan.md"
MAIN_PATH = REPO_ROOT / "server/app/main.py"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/creative_library"
README_PATH = DOMAIN_PATH / "README.md"
LEGACY_CHARACTERS_PATH = REPO_ROOT / "server/app/routers/characters.py"
LEGACY_SCENES_PATH = REPO_ROOT / "server/app/routers/scenes.py"
LEGACY_REFERENCE_DATA_PATH = REPO_ROOT / "server/app/routers/reference_data.py"


def test_creative_library_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.creative_library",
        "characters_router.py",
        "scenes_router.py",
        "reference_data_router.py",
        "app.routers.characters",
        "app.routers.scenes",
        "app.routers.reference_data",
        "/api/characters",
        "/api/scenes",
        "/api/reference-data",
    ]:
        assert term in spec
        assert term in plan


def test_creative_library_domain_exports_metadata():
    import app.domains.creative_library as domain

    assert domain.DOMAIN_NAME == "creative_library"
    assert domain.PUBLIC_ROUTE_PREFIXES == (
        "/api/characters",
        "/api/scenes",
        "/api/reference-categories",
        "/api/reference-data",
    )


def test_creative_library_readme_documents_facades_and_cleanup_gates():
    text = README_PATH.read_text(encoding="utf-8")

    for term in [
        "Facade Register",
        "app.routers.characters",
        "app.routers.scenes",
        "app.routers.reference_data",
        "app.domains.creative_library.characters_router",
        "app.domains.creative_library.scenes_router",
        "app.domains.creative_library.reference_data_router",
        "Compatibility Cleanup Gates",
    ]:
        assert term in text


def test_creative_library_owns_router_modules():
    assert (DOMAIN_PATH / "characters_router.py").exists()
    assert (DOMAIN_PATH / "scenes_router.py").exists()
    assert (DOMAIN_PATH / "reference_data_router.py").exists()


def test_creative_library_legacy_router_files_are_thin_facades():
    for path in [LEGACY_CHARACTERS_PATH, LEGACY_SCENES_PATH, LEGACY_REFERENCE_DATA_PATH]:
        text = path.read_text(encoding="utf-8")
        assert "app.domains.creative_library" in text
        assert "sys.modules[_LEGACY_MODULE_NAME]" in text
        assert "APIRouter(" not in text
        assert _line_count(path) <= 20


def test_creative_library_main_wires_domain_routers():
    text = MAIN_PATH.read_text(encoding="utf-8")

    assert "from app.domains.creative_library import characters_router, reference_data_router, scenes_router" in text
    assert "from app.domains.creative_library.reference_data_router import seed_reference_data" in text
    assert "app.include_router(characters_router.router)" in text
    assert "app.include_router(scenes_router.router)" in text
    assert "app.include_router(reference_data_router.router)" in text
    assert "app.include_router(characters.router)" not in text
    assert "app.include_router(scenes.router)" not in text
    assert "app.include_router(reference_data.router)" not in text


def test_app_import_smoke_keeps_creative_library_routes_registered_once():
    from app.main import app

    route_keys = [
        (route.path, tuple(sorted(route.methods)))
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path.startswith((
            "/api/characters",
            "/api/scenes",
            "/api/reference-categories",
            "/api/reference-data",
        ))
    ]
    paths = {path for path, _methods in route_keys}

    assert len(route_keys) == len(set(route_keys))
    assert "/api/characters" in paths
    assert "/api/scenes" in paths
    assert "/api/reference-categories" in paths
    assert "/api/reference-data/{category}" in paths


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

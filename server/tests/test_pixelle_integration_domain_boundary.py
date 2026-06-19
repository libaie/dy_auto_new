import importlib.util
from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-pixelle-integration-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-pixelle-integration-domain-plan.md"
MAIN_PATH = REPO_ROOT / "server/app/main.py"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/pixelle_integration"
README_PATH = DOMAIN_PATH / "README.md"
LEGACY_PIXELLE_PATH = REPO_ROOT / "server/app/routers/pixelle.py"
VIDEO_LIBRARY_PATH = REPO_ROOT / "server/app/domains/video_library"


def test_pixelle_integration_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.pixelle_integration",
        "pixelle_router.py",
        "app.routers.pixelle",
        "/api/pixelle",
        "/api/pixelle-proxy",
        "PixelleConfigUpdate",
        "_serialize_ai_models",
        "_redact_secrets",
        "_get_proxy_client",
    ]:
        assert term in spec
        assert term in plan


def test_pixelle_integration_domain_exports_metadata():
    spec = importlib.util.find_spec("app.domains.pixelle_integration")
    assert spec is not None

    import app.domains.pixelle_integration as domain

    assert domain.DOMAIN_NAME == "pixelle_integration"
    assert domain.PUBLIC_ROUTE_PREFIX == "/api/pixelle"
    assert domain.PUBLIC_PROXY_PREFIX == "/api/pixelle-proxy"


def test_pixelle_integration_readme_documents_facade_and_cleanup_gates():
    assert README_PATH.exists()
    text = README_PATH.read_text(encoding="utf-8")

    for term in [
        "Facade Register",
        "app.routers.pixelle",
        "app.domains.pixelle_integration.pixelle_router",
        "PixelleConfigUpdate",
        "_serialize_ai_models",
        "_redact_secrets",
        "_get_proxy_client",
        "Compatibility Cleanup Gates",
    ]:
        assert term in text


def test_pixelle_integration_owns_router_module():
    assert (DOMAIN_PATH / "pixelle_router.py").exists()


def test_pixelle_integration_legacy_router_file_is_thin_facade():
    text = LEGACY_PIXELLE_PATH.read_text(encoding="utf-8")

    assert "app.domains.pixelle_integration" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "APIRouter(" not in text
    assert _line_count(LEGACY_PIXELLE_PATH) <= 20


def test_pixelle_integration_main_wires_domain_router():
    text = MAIN_PATH.read_text(encoding="utf-8")

    assert "from app.domains.pixelle_integration import pixelle_router" in text
    assert "app.include_router(pixelle_router.router)" in text
    assert "app.include_router(pixelle_router.proxy_router)" in text
    assert "app.include_router(pixelle.router)" not in text
    assert "app.include_router(pixelle.proxy_router)" not in text


def test_pixelle_integration_keeps_video_library_separate():
    domain_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in VIDEO_LIBRARY_PATH.glob("*.py")
    )

    assert "app.domains.pixelle_integration" not in domain_text
    assert "pixelle_router" not in domain_text


def test_app_import_smoke_keeps_pixelle_routes_registered_once():
    from app.main import app

    route_keys = [
        (route.path, tuple(sorted(route.methods)))
        for route in app.routes
        if isinstance(route, APIRoute)
        and (route.path.startswith("/api/pixelle") or route.path.startswith("/api/pixelle-proxy"))
    ]
    paths = {path for path, _methods in route_keys}

    assert len(route_keys) == len(set(route_keys))
    assert "/api/pixelle/config" in paths
    assert "/api/pixelle/template-preview/{size}/{filename}" in paths
    assert "/api/pixelle/test-connection" in paths
    assert "/api/pixelle-proxy/{path:path}" in paths
    assert "/api/pixelle-proxy/" in paths


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

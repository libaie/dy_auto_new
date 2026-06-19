from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-system-operations-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-system-operations-domain-plan.md"
MAIN_PATH = REPO_ROOT / "server/app/main.py"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/system_operations"
README_PATH = DOMAIN_PATH / "README.md"
LEGACY_SYSTEM_HEALTH_PATH = REPO_ROOT / "server/app/routers/system_health.py"


def test_system_operations_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.system_operations",
        "system_health_router.py",
        "app.routers.system_health",
        "/api/system",
        "/api/system/health",
        "Root `/health`",
    ]:
        assert term in spec
        assert term in plan


def test_system_operations_domain_exports_metadata():
    import app.domains.system_operations as domain

    assert domain.DOMAIN_NAME == "system_operations"
    assert domain.PUBLIC_ROUTE_PREFIX == "/api/system"


def test_system_operations_readme_documents_facade_and_cleanup_gates():
    text = README_PATH.read_text(encoding="utf-8")

    for term in [
        "Facade Register",
        "app.routers.system_health",
        "app.domains.system_operations.system_health_router",
        "Root `/health`",
        "Compatibility Cleanup Gates",
    ]:
        assert term in text


def test_system_operations_owns_router_module():
    assert (DOMAIN_PATH / "system_health_router.py").exists()


def test_system_operations_legacy_router_file_is_thin_facade():
    text = LEGACY_SYSTEM_HEALTH_PATH.read_text(encoding="utf-8")

    assert "app.domains.system_operations" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "APIRouter(" not in text
    assert _line_count(LEGACY_SYSTEM_HEALTH_PATH) <= 20


def test_system_operations_main_wiring_remains_legacy_until_pr4():
    text = MAIN_PATH.read_text(encoding="utf-8")

    assert "from app.routers import system_health" in text
    assert "app.include_router(system_health.router)" in text


def test_app_import_smoke_keeps_system_operations_routes_registered_once():
    from app.main import app

    route_keys = [
        (route.path, tuple(sorted(route.methods)))
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/system")
    ]

    assert route_keys == [("/api/system/health", ("GET",))]


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

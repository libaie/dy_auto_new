from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-selector-management-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-selector-management-domain-plan.md"
MAIN_PATH = REPO_ROOT / "server/app/main.py"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/selector_management"
README_PATH = DOMAIN_PATH / "README.md"
LEGACY_SELECTORS_PATH = REPO_ROOT / "server/app/routers/selectors.py"
DEVICE_OPERATIONS_PATH = REPO_ROOT / "server/app/domains/device_operations"


def test_selector_management_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.selector_management",
        "selectors_router.py",
        "app.routers.selectors",
        "/api/selectors",
        "/api/device/selectors",
        "selectors_updated",
        "selectors_changed",
    ]:
        assert term in spec
        assert term in plan


def test_selector_management_domain_exports_metadata():
    import app.domains.selector_management as domain

    assert domain.DOMAIN_NAME == "selector_management"
    assert domain.PUBLIC_ROUTE_PREFIX == "/api/selectors"


def test_selector_management_readme_documents_facade_and_cleanup_gates():
    text = README_PATH.read_text(encoding="utf-8")

    for term in [
        "Facade Register",
        "app.routers.selectors",
        "app.domains.selector_management.selectors_router",
        "/api/device/selectors",
        "selectors_updated",
        "selectors_changed",
        "Compatibility Cleanup Gates",
    ]:
        assert term in text


def test_selector_management_owns_router_module():
    assert (DOMAIN_PATH / "selectors_router.py").exists()


def test_selector_management_legacy_router_file_is_thin_facade():
    text = LEGACY_SELECTORS_PATH.read_text(encoding="utf-8")

    assert "app.domains.selector_management" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "APIRouter(" not in text
    assert _line_count(LEGACY_SELECTORS_PATH) <= 20


def test_selector_management_main_wiring_remains_legacy_until_pr4():
    text = MAIN_PATH.read_text(encoding="utf-8")

    assert "selectors" in text
    assert "app.include_router(selectors.router)" in text


def test_selector_management_keeps_device_selector_routes_in_device_operations():
    script_assets = (DEVICE_OPERATIONS_PATH / "script_assets.py").read_text(encoding="utf-8")

    assert '@router.get("/selectors")' in script_assets
    assert "app.domains.selector_management" not in script_assets


def test_app_import_smoke_keeps_selector_management_routes_registered_once():
    from app.main import app

    route_keys = [
        (route.path, tuple(sorted(route.methods)))
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/selectors")
    ]
    paths = {path for path, _methods in route_keys}

    assert len(route_keys) == len(set(route_keys))
    assert "/api/selectors" in paths
    assert "/api/selectors/templates" in paths
    assert "/api/selectors/templates/upload" in paths
    assert "/api/selectors/{action_name}/toggle" in paths


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

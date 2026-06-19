import importlib.util
from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-system-configuration-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-system-configuration-domain-plan.md"
MAIN_PATH = REPO_ROOT / "server/app/main.py"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/system_configuration"
SYSTEM_OPERATIONS_PATH = REPO_ROOT / "server/app/domains/system_operations"
README_PATH = DOMAIN_PATH / "README.md"
LEGACY_SETTINGS_PATH = REPO_ROOT / "server/app/routers/settings.py"


def test_system_configuration_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.system_configuration",
        "settings_router.py",
        "app.routers.settings",
        "/api/settings",
        "SystemSetting",
        "SettingUpdate",
        "system_operations",
    ]:
        assert term in spec
        assert term in plan


def test_system_configuration_domain_exports_metadata():
    spec = importlib.util.find_spec("app.domains.system_configuration")
    assert spec is not None

    import app.domains.system_configuration as domain

    assert domain.DOMAIN_NAME == "system_configuration"
    assert domain.PUBLIC_ROUTE_PREFIX == "/api/settings"


def test_system_configuration_readme_documents_facade_and_cleanup_gates():
    assert README_PATH.exists()
    text = README_PATH.read_text(encoding="utf-8")

    for term in [
        "Facade Register",
        "app.routers.settings",
        "app.domains.system_configuration.settings_router",
        "SystemSetting",
        "SettingUpdate",
        "system_operations",
        "Compatibility Cleanup Gates",
    ]:
        assert term in text


def test_system_configuration_owns_router_module():
    assert (DOMAIN_PATH / "settings_router.py").exists()


def test_system_configuration_legacy_router_file_is_thin_facade():
    text = LEGACY_SETTINGS_PATH.read_text(encoding="utf-8")

    assert "app.domains.system_configuration" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "APIRouter(" not in text
    assert _line_count(LEGACY_SETTINGS_PATH) <= 20


def test_system_configuration_main_keeps_legacy_router_until_direct_wiring():
    text = MAIN_PATH.read_text(encoding="utf-8")

    assert "app.include_router(settings.router)" in text


def test_system_configuration_stays_separate_from_system_operations():
    operations_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in SYSTEM_OPERATIONS_PATH.glob("*.py")
    )

    assert "app.domains.system_configuration" not in operations_text
    assert "settings_router" not in operations_text


def test_app_import_smoke_keeps_system_configuration_routes_registered_once():
    from app.main import app

    route_keys = [
        (route.path, tuple(sorted(route.methods)))
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/settings")
    ]
    paths = {path for path, _methods in route_keys}

    assert len(route_keys) == len(set(route_keys))
    assert "/api/settings" in paths
    assert len(route_keys) == 2


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

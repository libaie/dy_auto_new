from pathlib import Path

from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-19-device-operations-domain-design.md"
MAIN_PATH = REPO_ROOT / "server/app/main.py"
LEGACY_DEVICE_ROUTER_PATH = REPO_ROOT / "server/app/routers/device.py"
LEGACY_ADMIN_DEVICE_ROUTER_PATH = REPO_ROOT / "server/app/routers/devices.py"
FUTURE_DOMAIN_PATH = REPO_ROOT / "server/app/domains/device_operations"
FUTURE_DOMAIN_README_PATH = FUTURE_DOMAIN_PATH / "README.md"


def test_device_operations_future_contract_is_documented_in_spec():
    text = SPEC_PATH.read_text(encoding="utf-8")

    required_contract_terms = [
        "app.domains.device_operations",
        "__init__.py",
        "device_router.py",
        "admin_router.py",
        "pairing.py",
        "status_ws.py",
        "status_lifecycle.py",
        "polling.py",
        "reporting.py",
        "script_assets.py",
        "content_bridge.py",
        "adapters.py",
        'DOMAIN_NAME = "device_operations"',
        '("/api/device", "/api/devices")',
    ]
    for term in required_contract_terms:
        assert term in text


def test_device_operations_bridge_ownership_is_documented_as_temporary():
    text = SPEC_PATH.read_text(encoding="utf-8")

    assert "temporary bridge" in text
    assert "content/collection/DM" in text
    assert "content_collection" in text
    assert "do not move content/collection/DM bridge ownership" in text


def test_device_operations_migration_keeps_legacy_router_files_active():
    device_text = LEGACY_DEVICE_ROUTER_PATH.read_text(encoding="utf-8")
    admin_text = LEGACY_ADMIN_DEVICE_ROUTER_PATH.read_text(encoding="utf-8")

    assert "app.domains.device_operations.device_router" in device_text
    assert "app.domains.device_operations.admin_router" in admin_text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in device_text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in admin_text
    assert _line_count(LEGACY_DEVICE_ROUTER_PATH) <= 20
    assert _line_count(LEGACY_ADMIN_DEVICE_ROUTER_PATH) <= 20


def test_device_operations_domain_package_exports_metadata_only_skeleton():
    import app.domains.device_operations as domain

    assert domain.DOMAIN_NAME == "device_operations"
    assert domain.PUBLIC_ROUTE_PREFIXES == ("/api/device", "/api/devices")


def test_device_operations_readme_documents_facades_and_cleanup_gates():
    text = FUTURE_DOMAIN_README_PATH.read_text(encoding="utf-8")

    required_terms = [
        "Facade Register",
        "app.routers.device",
        "app.domains.device_operations.device_router",
        "app.routers.devices",
        "app.domains.device_operations.admin_router",
        "app.main._offline_checker",
        "app.domains.device_operations.status_lifecycle",
        "content_collection",
        "Compatibility Cleanup Gates",
    ]
    for term in required_terms:
        assert term in text


def test_device_operations_pr3_owns_router_modules_but_not_lifecycle_module():
    assert (FUTURE_DOMAIN_PATH / "device_router.py").exists()
    assert (FUTURE_DOMAIN_PATH / "admin_router.py").exists()
    assert not (FUTURE_DOMAIN_PATH / "status_lifecycle.py").exists()


def test_main_continues_to_wire_legacy_device_routers_during_pr2():
    text = MAIN_PATH.read_text(encoding="utf-8")

    assert "from app.routers import device" in text
    assert "app.include_router(device.router)" in text
    assert "app.include_router(devices.router)" in text
    assert "device_operations" not in text


def test_app_import_smoke_keeps_device_routes_registered():
    from app.main import app

    paths = {route.path for route in app.routes if isinstance(route, APIRoute)}

    assert "/api/device/poll" in paths
    assert "/api/device/report" in paths
    assert "/api/devices" in paths
    assert "/api/devices/{device_id}/disconnect" in paths


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

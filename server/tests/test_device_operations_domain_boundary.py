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


def test_device_operations_pr3_owns_router_modules():
    assert (FUTURE_DOMAIN_PATH / "device_router.py").exists()
    assert (FUTURE_DOMAIN_PATH / "admin_router.py").exists()


def test_device_operations_pr4a_extracts_pairing_and_status_ws_modules():
    import app.domains.device_operations.device_router as device_router
    import app.domains.device_operations.pairing as pairing
    import app.domains.device_operations.status_ws as status_ws

    assert hasattr(pairing, "create_pair_request")
    assert hasattr(pairing, "check_pair_status")
    assert hasattr(pairing, "ws_pair_status")
    assert hasattr(status_ws, "ws_device_status")
    assert hasattr(status_ws, "_notify_pending_tasks")
    endpoint_modules = {
        f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
        for route in device_router.router.routes
        if hasattr(route, "endpoint")
    }
    assert "app.domains.device_operations.pairing.create_pair_request" in endpoint_modules
    assert "app.domains.device_operations.pairing.check_pair_status" in endpoint_modules
    assert "app.domains.device_operations.pairing.ws_pair_status" in endpoint_modules
    assert "app.domains.device_operations.status_ws.ws_device_status" in endpoint_modules


def test_device_operations_pr4b_extracts_polling_and_reporting_modules():
    import app.domains.device_operations.device_router as device_router
    import app.domains.device_operations.polling as polling
    import app.domains.device_operations.reporting as reporting

    assert hasattr(polling, "poll_tasks")
    assert hasattr(reporting, "report_progress")
    assert hasattr(reporting, "report_result")
    assert hasattr(reporting, "stats_increment")
    assert hasattr(reporting, "heartbeat")
    assert hasattr(reporting, "report_risk")
    endpoint_modules = {
        f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
        for route in device_router.router.routes
        if hasattr(route, "endpoint")
    }
    assert "app.domains.device_operations.polling.poll_tasks" in endpoint_modules
    assert "app.domains.device_operations.reporting.report_progress" in endpoint_modules
    assert "app.domains.device_operations.reporting.report_result" in endpoint_modules
    assert "app.domains.device_operations.reporting.stats_increment" in endpoint_modules
    assert "app.domains.device_operations.reporting.heartbeat" in endpoint_modules
    assert "app.domains.device_operations.reporting.report_risk" in endpoint_modules


def test_device_operations_pr4c_extracts_script_assets_module():
    import app.domains.device_operations.device_router as device_router
    import app.domains.device_operations.script_assets as script_assets

    assert hasattr(script_assets, "get_selectors")
    assert hasattr(script_assets, "get_prompt_templates")
    assert hasattr(script_assets, "script_version")
    assert hasattr(script_assets, "script_download")
    assert hasattr(script_assets, "script_upload")
    assert hasattr(script_assets, "device_list_templates")
    assert hasattr(script_assets, "device_download_template")
    assert hasattr(script_assets, "device_calibrate")
    endpoint_modules = {
        f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
        for route in device_router.router.routes
        if hasattr(route, "endpoint")
    }
    assert "app.domains.device_operations.script_assets.get_selectors" in endpoint_modules
    assert "app.domains.device_operations.script_assets.get_prompt_templates" in endpoint_modules
    assert "app.domains.device_operations.script_assets.script_version" in endpoint_modules
    assert "app.domains.device_operations.script_assets.script_download" in endpoint_modules
    assert "app.domains.device_operations.script_assets.script_upload" in endpoint_modules
    assert "app.domains.device_operations.script_assets.device_list_templates" in endpoint_modules
    assert "app.domains.device_operations.script_assets.device_download_template" in endpoint_modules
    assert "app.domains.device_operations.script_assets.device_calibrate" in endpoint_modules


def test_device_operations_pr4d_extracts_content_bridge_module():
    import app.domains.device_operations.content_bridge as content_bridge
    import app.domains.device_operations.device_router as device_router

    assert hasattr(content_bridge, "claim_comment_reply")
    assert hasattr(content_bridge, "release_comment_claim")
    assert hasattr(content_bridge, "generate_content")
    assert hasattr(content_bridge, "ai_proxy")
    assert hasattr(content_bridge, "collect_report")
    assert hasattr(content_bridge, "dm_claim_recipient")
    assert hasattr(content_bridge, "dm_send_report")
    assert hasattr(content_bridge, "dm_release_recipient")
    assert hasattr(content_bridge, "save_comment_ai_reply")
    assert hasattr(content_bridge, "save_user_profile")
    assert hasattr(content_bridge, "upload_user_avatar")
    assert hasattr(content_bridge, "get_user_avatar")
    endpoint_modules = {
        f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
        for route in device_router.router.routes
        if hasattr(route, "endpoint")
    }
    assert "app.domains.device_operations.content_bridge.claim_comment_reply" in endpoint_modules
    assert "app.domains.device_operations.content_bridge.release_comment_claim" in endpoint_modules
    assert "app.domains.device_operations.content_bridge.generate_content" in endpoint_modules
    assert "app.domains.device_operations.content_bridge.ai_proxy" in endpoint_modules
    assert "app.domains.device_operations.content_bridge.collect_report" in endpoint_modules
    assert "app.domains.device_operations.content_bridge.dm_claim_recipient" in endpoint_modules
    assert "app.domains.device_operations.content_bridge.dm_send_report" in endpoint_modules
    assert "app.domains.device_operations.content_bridge.dm_release_recipient" in endpoint_modules
    assert "app.domains.device_operations.content_bridge.save_comment_ai_reply" in endpoint_modules
    assert "app.domains.device_operations.content_bridge.save_user_profile" in endpoint_modules
    assert "app.domains.device_operations.content_bridge.upload_user_avatar" in endpoint_modules
    assert "app.domains.device_operations.content_bridge.get_user_avatar" in endpoint_modules


def test_device_operations_pr5_extracts_status_lifecycle_module():
    import inspect

    import app.main as main
    import app.domains.device_operations.status_lifecycle as status_lifecycle

    assert hasattr(status_lifecycle, "offline_checker")
    assert (FUTURE_DOMAIN_PATH / "status_lifecycle.py").exists()
    main_checker_source = inspect.getsource(main._offline_checker)
    assert "status_lifecycle import offline_checker" in main_checker_source
    assert "drain_heartbeats" not in main_checker_source
    assert "TASK_STALE_MINUTES" not in main_checker_source


def test_main_wires_device_operation_domain_routers_after_cleanup_gate():
    text = MAIN_PATH.read_text(encoding="utf-8")

    assert "from app.domains.device_operations import admin_router, device_router" in text
    assert "app.include_router(device_router.router)" in text
    assert "app.include_router(admin_router.router)" in text
    assert "app.include_router(device.router)" not in text
    assert "app.include_router(devices.router)" not in text


def test_app_import_smoke_keeps_device_routes_registered():
    from app.main import app

    paths = {route.path for route in app.routes if isinstance(route, APIRoute)}

    assert "/api/device/poll" in paths
    assert "/api/device/report" in paths
    assert "/api/devices" in paths
    assert "/api/devices/{device_id}/disconnect" in paths


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())

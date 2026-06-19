import importlib
from pathlib import Path

from fastapi.routing import APIRoute, APIWebSocketRoute


REPO_ROOT = Path(__file__).resolve().parents[2]


EXPECTED_DEVICE_ROUTER_SNAPSHOT = [
    ("POST", "/api/device/pair-request", "create_pair_request"),
    ("GET", "/api/device/pair-status", "check_pair_status"),
    ("WEBSOCKET", "/api/device/ws/pair/{token}", "ws_pair_status"),
    ("WEBSOCKET", "/api/device/ws/status", "ws_device_status"),
    ("GET", "/api/device/poll", "poll_tasks"),
    ("POST", "/api/device/progress", "report_progress"),
    ("POST", "/api/device/report", "report_result"),
    ("POST", "/api/device/stats/increment", "stats_increment"),
    ("POST", "/api/device/heartbeat", "heartbeat"),
    ("POST", "/api/device/register", "register_device"),
    ("GET", "/api/device/selectors", "get_selectors"),
    ("GET", "/api/device/prompt-templates", "get_prompt_templates"),
    ("GET", "/api/device/script-version", "script_version"),
    ("GET", "/api/device/script-download", "script_download"),
    ("POST", "/api/device/script-upload", "script_upload"),
    ("POST", "/api/device/risk-report", "report_risk"),
    ("POST", "/api/device/comment-claim-reply", "claim_comment_reply"),
    ("POST", "/api/device/comment-claim-release", "release_comment_claim"),
    ("POST", "/api/device/generate-content", "generate_content"),
    ("GET", "/api/device/templates", "device_list_templates"),
    ("GET", "/api/device/templates/{filename}", "device_download_template"),
    ("POST", "/api/device/calibrate", "device_calibrate"),
    ("POST", "/api/device/ai-proxy", "ai_proxy"),
    ("POST", "/api/device/collect-report", "collect_report"),
    ("POST", "/api/device/dm-claim-recipient", "dm_claim_recipient"),
    ("POST", "/api/device/dm-send-report", "dm_send_report"),
    ("POST", "/api/device/dm-release-recipient", "dm_release_recipient"),
    ("POST", "/api/device/comment-ai-reply", "save_comment_ai_reply"),
    ("POST", "/api/device/user-profile", "save_user_profile"),
    ("POST", "/api/device/user-avatar", "upload_user_avatar"),
    ("GET", "/api/device/avatar/{douyin_id}", "get_user_avatar"),
]


EXPECTED_ADMIN_ROUTER_SNAPSHOT = [
    ("WEBSOCKET", "/api/devices/ws/pair-events", "ws_pair_events"),
    ("POST", "/api/devices", "create_device"),
    ("GET", "/api/devices", "list_devices"),
    ("GET", "/api/devices/pair-requests", "list_pair_requests"),
    ("POST", "/api/devices/pair-requests/{request_id}/approve", "approve_pair_request"),
    ("POST", "/api/devices/pair-requests/{request_id}/reject", "reject_pair_request"),
    ("GET", "/api/devices/{device_id}", "get_device"),
    ("PUT", "/api/devices/{device_id}", "update_device"),
    ("POST", "/api/devices/{device_id}/disconnect", "disconnect_device"),
    ("DELETE", "/api/devices/{device_id}", "delete_device"),
]


def test_domain_device_router_matches_current_route_snapshot():
    domain_router = importlib.import_module("app.domains.device_operations.device_router")

    assert _router_snapshot(domain_router.router) == EXPECTED_DEVICE_ROUTER_SNAPSHOT


def test_domain_admin_router_matches_current_route_snapshot():
    domain_router = importlib.import_module("app.domains.device_operations.admin_router")

    assert _router_snapshot(domain_router.router) == EXPECTED_ADMIN_ROUTER_SNAPSHOT


def test_legacy_device_router_module_is_domain_router_module():
    legacy_router = importlib.import_module("app.routers.device")
    domain_router = importlib.import_module("app.domains.device_operations.device_router")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router


def test_legacy_admin_device_router_module_is_domain_router_module():
    legacy_router = importlib.import_module("app.routers.devices")
    domain_router = importlib.import_module("app.domains.device_operations.admin_router")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router


def test_router_facade_cleanup_gates_are_documented():
    readme = (REPO_ROOT / "server/app/domains/device_operations/README.md").read_text(encoding="utf-8")

    assert "Compatibility Cleanup Gates" in readme
    assert "Do not remove `app.routers.device` or `app.routers.devices` until all of these are true" in readme


def _router_snapshot(router):
    snapshot = []
    for route in router.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods or []):
                snapshot.append((method, route.path, route.name))
        elif isinstance(route, APIWebSocketRoute):
            snapshot.append(("WEBSOCKET", route.path, route.name))
    return snapshot

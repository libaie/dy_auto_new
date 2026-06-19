from fastapi.routing import APIRoute, APIWebSocketRoute

from app.main import app


EXPECTED_DEVICE_OPERATION_HTTP_ROUTES = [
    ("/api/device/pair-request", ("POST",), "create_pair_request", ("get_db",)),
    ("/api/device/pair-status", ("GET",), "check_pair_status", ("get_db",)),
    ("/api/device/poll", ("GET",), "poll_tasks", ("get_db", "verify_device_secret")),
    ("/api/device/progress", ("POST",), "report_progress", ("get_db", "verify_device_secret")),
    ("/api/device/report", ("POST",), "report_result", ("get_db", "verify_device_secret")),
    ("/api/device/stats/increment", ("POST",), "stats_increment", ("get_db", "verify_device_secret")),
    ("/api/device/heartbeat", ("POST",), "heartbeat", ("get_db", "verify_device_secret")),
    ("/api/device/register", ("POST",), "register_device", ("get_db", "verify_device_secret")),
    ("/api/device/selectors", ("GET",), "get_selectors", ("get_db", "verify_device_secret")),
    ("/api/device/prompt-templates", ("GET",), "get_prompt_templates", ("get_db", "verify_device_secret")),
    ("/api/device/script-version", ("GET",), "script_version", ("verify_device_secret",)),
    ("/api/device/script-download", ("GET",), "script_download", ("verify_device_secret",)),
    ("/api/device/script-upload", ("POST",), "script_upload", ("verify_admin_token",)),
    ("/api/device/risk-report", ("POST",), "report_risk", ("get_db", "verify_device_secret")),
    ("/api/device/comment-claim-reply", ("POST",), "claim_comment_reply", ("get_db", "verify_device_secret")),
    ("/api/device/comment-claim-release", ("POST",), "release_comment_claim", ("get_db", "verify_device_secret")),
    ("/api/device/generate-content", ("POST",), "generate_content", ("get_db", "verify_device_secret")),
    ("/api/device/templates", ("GET",), "device_list_templates", ("verify_device_secret", "get_db")),
    ("/api/device/templates/{filename}", ("GET",), "device_download_template", ("verify_device_secret", "get_db")),
    ("/api/device/calibrate", ("POST",), "device_calibrate", ("get_db", "verify_device_secret")),
    ("/api/device/ai-proxy", ("POST",), "ai_proxy", ("get_db", "verify_device_secret")),
    ("/api/device/collect-report", ("POST",), "collect_report", ("get_db", "verify_device_secret")),
    ("/api/device/dm-claim-recipient", ("POST",), "dm_claim_recipient", ("get_db", "verify_device_secret")),
    ("/api/device/dm-send-report", ("POST",), "dm_send_report", ("get_db", "verify_device_secret")),
    ("/api/device/dm-release-recipient", ("POST",), "dm_release_recipient", ("get_db", "verify_device_secret")),
    ("/api/device/comment-ai-reply", ("POST",), "save_comment_ai_reply", ("get_db", "verify_device_secret")),
    ("/api/device/user-profile", ("POST",), "save_user_profile", ("get_db", "verify_device_secret")),
    ("/api/device/user-avatar", ("POST",), "upload_user_avatar", ("get_db", "verify_device_secret")),
    ("/api/device/avatar/{douyin_id}", ("GET",), "get_user_avatar", ()),
    ("/api/devices", ("POST",), "create_device", ("get_db", "require_role:admin")),
    ("/api/devices", ("GET",), "list_devices", ("get_db", "verify_admin_token")),
    ("/api/devices/pair-requests", ("GET",), "list_pair_requests", ("get_db", "verify_admin_token")),
    ("/api/devices/pair-requests/{request_id}/approve", ("POST",), "approve_pair_request", ("get_db", "verify_admin_token")),
    ("/api/devices/pair-requests/{request_id}/reject", ("POST",), "reject_pair_request", ("get_db", "verify_admin_token")),
    ("/api/devices/{device_id}", ("GET",), "get_device", ("get_db", "verify_admin_token")),
    ("/api/devices/{device_id}", ("PUT",), "update_device", ("get_db", "verify_admin_token")),
    ("/api/devices/{device_id}/disconnect", ("POST",), "disconnect_device", ("get_db", "verify_admin_token")),
    ("/api/devices/{device_id}", ("DELETE",), "delete_device", ("get_db", "verify_admin_token")),
]


EXPECTED_DEVICE_OPERATION_WEBSOCKETS = [
    ("/api/device/ws/pair/{token}", "ws_pair_status", "app.routers.device.ws_pair_status", "device"),
    ("/api/device/ws/status", "ws_device_status", "app.routers.device.ws_device_status", "device"),
    ("/api/devices/ws/pair-events", "ws_pair_events", "app.routers.devices.ws_pair_events", "admin"),
]


def test_device_operation_route_table_snapshot():
    routes = [(path, methods, name) for path, methods, name, _dependencies in _device_operation_http_routes()]

    assert routes == [
        (path, methods, name)
        for path, methods, name, _dependencies in EXPECTED_DEVICE_OPERATION_HTTP_ROUTES
    ]


def test_device_operation_auth_dependency_snapshot():
    assert _device_operation_http_routes() == EXPECTED_DEVICE_OPERATION_HTTP_ROUTES


def test_device_operation_websocket_snapshot():
    assert _device_operation_websockets() == EXPECTED_DEVICE_OPERATION_WEBSOCKETS


def _device_operation_http_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and _is_device_operation_route(route.path):
            dependency_names = [
                _dependency_identity(dep.call)
                for dep in route.dependant.dependencies
                if dep.call
            ]
            routes.append((route.path, tuple(sorted(route.methods)), route.name, tuple(dependency_names)))
    return routes


def _device_operation_websockets():
    websockets = []
    for route in app.routes:
        if isinstance(route, APIWebSocketRoute) and _is_device_operation_route(route.path):
            endpoint = f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
            audience = "admin" if route.path.startswith("/api/devices") else "device"
            websockets.append((route.path, route.name, endpoint, audience))
    return websockets


def _is_device_operation_route(path):
    return (
        path == "/api/device"
        or path.startswith("/api/device/")
        or path == "/api/devices"
        or path.startswith("/api/devices/")
    )


def _dependency_identity(call):
    name = getattr(call, "__name__", repr(call))
    qualname = getattr(call, "__qualname__", "")
    if name == "checker" and qualname.endswith("require_role.<locals>.checker"):
        closure = getattr(call, "__closure__", None) or ()
        for cell in closure:
            try:
                value = cell.cell_contents
            except ValueError:
                continue
            if isinstance(value, str):
                return f"require_role:{value}"
            if isinstance(value, (frozenset, set, tuple, list)) and value:
                roles = ",".join(sorted(str(role) for role in value))
                return f"require_role:{roles}"
    return name

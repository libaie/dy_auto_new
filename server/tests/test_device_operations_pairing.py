from fastapi.routing import APIRoute, APIWebSocketRoute
from fastapi.testclient import TestClient

from app.main import app


PAIRING_ENDPOINTS = {
    "/api/device/pair-request": "app.domains.device_operations.pairing.create_pair_request",
    "/api/device/pair-status": "app.domains.device_operations.pairing.check_pair_status",
    "/api/device/ws/pair/{token}": "app.domains.device_operations.pairing.ws_pair_status",
    "/api/devices/pair-requests": "app.domains.device_operations.admin_router.list_pair_requests",
    "/api/devices/pair-requests/{request_id}/approve": "app.domains.device_operations.admin_router.approve_pair_request",
    "/api/devices/pair-requests/{request_id}/reject": "app.domains.device_operations.admin_router.reject_pair_request",
    "/api/devices/ws/pair-events": "app.domains.device_operations.admin_router.ws_pair_events",
}


def test_pairing_routes_are_owned_by_domain_modules():
    assert {
        route.path: f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
        for route in app.routes
        if isinstance(route, (APIRoute, APIWebSocketRoute)) and route.path in PAIRING_ENDPOINTS
    } == PAIRING_ENDPOINTS


def test_pair_request_approval_and_status_response_shapes():
    device_id = "device-pair-approval-shape"
    with TestClient(app) as client:
        pair = client.post(
            "/api/device/pair-request",
            json={"device_id": device_id, "device_name": "Approval Shape Phone"},
            headers={"X-Forwarded-For": "10.10.10.101"},
        )
        token = pair.json()["pairing_token"]

        pending_status = client.get("/api/device/pair-status", params={"token": token})
        list_response = client.get("/api/devices/pair-requests", params={"status": "pending"})
        request_id = next(
            request["id"]
            for request in list_response.json()["requests"]
            if request["device_id"] == device_id
        )
        approval = client.post(f"/api/devices/pair-requests/{request_id}/approve")
        approved_status = client.get("/api/device/pair-status", params={"token": token})

    assert pair.status_code == 200
    assert pair.json()["status"] == "pending"
    assert isinstance(token, str)

    assert pending_status.status_code == 200
    assert pending_status.json()["status"] == "pending"

    assert set(list_response.json()) == {"requests", "total"}
    assert approval.status_code == 200
    assert approval.json() == {"status": "approved", "device_id": device_id}

    assert approved_status.status_code == 200
    assert approved_status.json()["status"] == "approved"
    assert isinstance(approved_status.json()["secret"], str)
    assert isinstance(approved_status.json()["config"], dict)


def test_pair_request_rejection_response_shape():
    device_id = "device-pair-rejection-shape"
    with TestClient(app) as client:
        pair = client.post(
            "/api/device/pair-request",
            json={"device_id": device_id, "device_name": "Rejection Shape Phone"},
            headers={"X-Forwarded-For": "10.10.10.102"},
        )
        token = pair.json()["pairing_token"]
        list_response = client.get("/api/devices/pair-requests", params={"status": "pending"})
        request_id = next(
            request["id"]
            for request in list_response.json()["requests"]
            if request["device_id"] == device_id
        )
        rejection = client.post(f"/api/devices/pair-requests/{request_id}/reject")
        rejected_status = client.get("/api/device/pair-status", params={"token": token})

    assert rejection.status_code == 200
    assert rejection.json() == {"status": "rejected"}

    assert rejected_status.status_code == 200
    assert rejected_status.json()["status"] == "rejected"

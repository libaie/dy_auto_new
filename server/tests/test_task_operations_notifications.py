from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app


def test_single_task_create_broadcasts_device_and_admin_updates():
    with (
        patch("app.domains.task_operations.realtime_events.pair_ws_manager.broadcast_to_devices", new_callable=AsyncMock) as device_broadcast,
        patch("app.domains.task_operations.realtime_events.pair_ws_manager.broadcast_to_admins", new_callable=AsyncMock) as admin_broadcast,
    ):
        with TestClient(app) as client:
            response = client.post(
                "/api/tasks",
                json={
                    "type": "nurture",
                    "account_id": "acc-001",
                    "params": {"duration": 15},
                },
            )

    assert response.status_code == 200
    device_broadcast.assert_awaited_once_with({"event": "new_task_available"})
    admin_broadcast.assert_awaited_once_with({
        "event": "task_updated",
        "task_id": response.json()["id"],
        "status": "pending",
    })


def test_batch_direct_task_create_broadcasts_tasks_changed():
    with (
        patch("app.domains.task_operations.realtime_events.pair_ws_manager.broadcast_to_devices", new_callable=AsyncMock) as device_broadcast,
        patch("app.domains.task_operations.realtime_events.pair_ws_manager.broadcast_to_admins", new_callable=AsyncMock) as admin_broadcast,
    ):
        with TestClient(app) as client:
            response = client.post(
                "/api/tasks/batch",
                json={
                    "type": "nurture",
                    "account_ids": ["acc-001"],
                    "params": {"duration": 20},
                },
            )

    assert response.status_code == 200
    device_broadcast.assert_awaited_once_with({"event": "new_task_available"})
    admin_broadcast.assert_awaited_once_with({"event": "tasks_changed"})


def test_cancel_task_sends_device_cancel_and_broadcasts_updates():
    with TestClient(app) as client:
        created = client.post(
            "/api/tasks",
            json={
                "type": "nurture",
                "account_id": "acc-001",
                "device_id": "task-ops-device",
                "params": {"duration": 15},
            },
        )
        task_id = created.json()["id"]

        with (
            patch("app.domains.task_operations.realtime_events.pair_ws_manager.send_to_device", new_callable=AsyncMock) as send_to_device,
            patch("app.domains.task_operations.realtime_events.pair_ws_manager.broadcast_to_devices", new_callable=AsyncMock) as device_broadcast,
            patch("app.domains.task_operations.realtime_events.pair_ws_manager.broadcast_to_admins", new_callable=AsyncMock) as admin_broadcast,
        ):
            response = client.post(f"/api/tasks/{task_id}/cancel")

    assert created.status_code == 200
    assert response.status_code == 200
    send_to_device.assert_awaited_once_with("task-ops-device", {
        "event": "cancel_task",
        "task_id": task_id,
    })
    device_broadcast.assert_awaited_once_with({"event": "new_task_available"})
    admin_broadcast.assert_awaited_once_with({
        "event": "task_updated",
        "task_id": task_id,
        "status": "cancelled",
    })


def test_delete_and_batch_delete_broadcast_tasks_changed():
    with TestClient(app) as client:
        first = client.post(
            "/api/tasks",
            json={"type": "nurture", "account_id": "acc-001", "params": {"duration": 10}},
        )
        second = client.post(
            "/api/tasks",
            json={"type": "nurture", "account_id": "acc-001", "params": {"duration": 11}},
        )

        with patch("app.domains.task_operations.realtime_events.pair_ws_manager.broadcast_to_admins", new_callable=AsyncMock) as delete_broadcast:
            deleted = client.delete(f"/api/tasks/{first.json()['id']}")

        with patch("app.domains.task_operations.realtime_events.pair_ws_manager.broadcast_to_admins", new_callable=AsyncMock) as batch_broadcast:
            batch_deleted = client.post("/api/tasks/batch-delete", json={"task_ids": [second.json()["id"]]})

    assert deleted.status_code == 200
    delete_broadcast.assert_awaited_once_with({"event": "tasks_changed"})

    assert batch_deleted.status_code == 200
    batch_broadcast.assert_awaited_once_with({"event": "tasks_changed"})

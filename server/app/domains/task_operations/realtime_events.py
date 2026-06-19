"""Realtime event helpers for task operations."""

from .adapters import pair_ws_manager


async def broadcast_new_task_available():
    await pair_ws_manager.broadcast_to_devices({"event": "new_task_available"})


async def broadcast_task_updated(task_id: str, status: str):
    await pair_ws_manager.broadcast_to_admins({
        "event": "task_updated",
        "task_id": task_id,
        "status": status,
    })


async def broadcast_tasks_changed():
    await pair_ws_manager.broadcast_to_admins({"event": "tasks_changed"})


async def send_cancel_task(device_id: str, task_id: str):
    await pair_ws_manager.send_to_device(device_id, {
        "event": "cancel_task",
        "task_id": task_id,
    })

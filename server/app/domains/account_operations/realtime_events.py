"""Realtime event helpers for account operations."""

from app.ws_manager import pair_ws_manager


async def broadcast_accounts_changed():
    await pair_ws_manager.broadcast_to_admins({"event": "accounts_changed"})


async def broadcast_account_groups_changed():
    await pair_ws_manager.broadcast_to_admins({"event": "account_groups_changed"})


async def broadcast_channels_changed():
    await pair_ws_manager.broadcast_to_admins({"event": "channels_changed"})


async def broadcast_new_task_available():
    await pair_ws_manager.broadcast_to_devices({"event": "new_task_available"})


async def broadcast_chains_changed():
    await pair_ws_manager.broadcast_to_admins({"event": "chains_changed"})


async def send_cancel_task(device_id: str, task_id: str):
    await pair_ws_manager.send_to_device(device_id, {
        "event": "cancel_task",
        "task_id": task_id,
    })

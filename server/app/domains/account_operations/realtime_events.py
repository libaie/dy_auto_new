"""账号运营业务域模块。

账号运营业务域，负责账号、分组、频道、链路和账号侧读写用例。本文件负责 realtime_events 相关业务规则、状态转换和外部系统边界。
"""

from app.ws_manager import pair_ws_manager


async def broadcast_accounts_changed():
    """业务函数：处理 broadcast_accounts_changed 对应的业务流程、校验或数据转换。"""
    await pair_ws_manager.broadcast_to_admins({"event": "accounts_changed"})


async def broadcast_account_groups_changed():
    """业务函数：处理 broadcast_account_groups_changed 对应的业务流程、校验或数据转换。"""
    await pair_ws_manager.broadcast_to_admins({"event": "account_groups_changed"})


async def broadcast_channels_changed():
    """业务函数：处理 broadcast_channels_changed 对应的业务流程、校验或数据转换。"""
    await pair_ws_manager.broadcast_to_admins({"event": "channels_changed"})


async def broadcast_new_task_available():
    """业务函数：处理 broadcast_new_task_available 对应的业务流程、校验或数据转换。"""
    await pair_ws_manager.broadcast_to_devices({"event": "new_task_available"})


async def broadcast_chains_changed():
    """业务函数：处理 broadcast_chains_changed 对应的业务流程、校验或数据转换。"""
    await pair_ws_manager.broadcast_to_admins({"event": "chains_changed"})


async def send_cancel_task(device_id: str, task_id: str):
    """业务函数：处理 send_cancel_task 对应的业务流程、校验或数据转换。"""
    await pair_ws_manager.send_to_device(device_id, {
        "event": "cancel_task",
        "task_id": task_id,
    })

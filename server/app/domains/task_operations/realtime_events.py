"""任务运营业务域模块。

任务运营业务域，负责任务参数解析、执行用例、实时事件和路由接口。本文件负责 realtime_events 相关业务规则、状态转换和外部系统边界。
"""

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

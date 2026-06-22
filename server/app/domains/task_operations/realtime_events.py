"""任务运营业务域模块。

任务运营业务域，负责任务参数解析、执行用例、实时事件和路由接口。本文件负责 realtime_events 相关业务规则、状态转换和外部系统边界。
"""

from .adapters import pair_ws_manager


async def broadcast_new_task_available():
    """业务函数：处理 broadcast_new_task_available 对应的业务流程、校验或数据转换。

    入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    await pair_ws_manager.broadcast_to_devices({"event": "new_task_available"})


async def broadcast_task_updated(task_id: str, status: str):
    """业务函数：处理 broadcast_task_updated 对应的业务流程、校验或数据转换。

    入参：task_id、status 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    await pair_ws_manager.broadcast_to_admins({
        "event": "task_updated",
        "task_id": task_id,
        "status": status,
    })


async def broadcast_tasks_changed():
    """业务函数：处理 broadcast_tasks_changed 对应的业务流程、校验或数据转换。

    入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    await pair_ws_manager.broadcast_to_admins({"event": "tasks_changed"})


async def send_cancel_task(device_id: str, task_id: str):
    """业务函数：处理 send_cancel_task 对应的业务流程、校验或数据转换。

    入参：device_id、task_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    await pair_ws_manager.send_to_device(device_id, {
        "event": "cancel_task",
        "task_id": task_id,
    })

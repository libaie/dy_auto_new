"""任务运营业务域模块。

任务运营业务域，负责任务参数解析、执行用例、实时事件和路由接口。本文件负责 read_models 相关业务规则、状态转换和外部系统边界。
"""

def task_list_response(tasks, total: int) -> dict:
    return {"tasks": tasks, "total": total}


def batch_create_response(created_count: int, mode: str) -> dict:
    return {"created": created_count, "mode": mode}


def batch_delete_response(deleted_count: int) -> dict:
    return {"deleted": deleted_count}


def delete_response(task_id: str) -> dict:
    return {"deleted": True, "task_id": task_id}

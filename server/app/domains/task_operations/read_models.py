"""任务运营业务域模块。

任务运营业务域，负责任务参数解析、执行用例、实时事件和路由接口。本文件负责 read_models 相关业务规则、状态转换和外部系统边界。
"""

def task_list_response(tasks, total: int) -> dict:
    """业务函数：处理 task_list_response 对应的业务流程、校验或数据转换。"""
    return {"tasks": tasks, "total": total}


def batch_create_response(created_count: int, mode: str) -> dict:
    """业务函数：处理 batch_create_response 对应的业务流程、校验或数据转换。"""
    return {"created": created_count, "mode": mode}


def batch_delete_response(deleted_count: int) -> dict:
    """业务函数：处理 batch_delete_response 对应的业务流程、校验或数据转换。"""
    return {"deleted": deleted_count}


def delete_response(task_id: str) -> dict:
    """业务函数：处理 delete_response 对应的业务流程、校验或数据转换。"""
    return {"deleted": True, "task_id": task_id}

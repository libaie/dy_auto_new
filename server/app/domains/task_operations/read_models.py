"""Payload shaping helpers for task operations routes."""


def task_list_response(tasks, total: int) -> dict:
    return {"tasks": tasks, "total": total}


def batch_create_response(created_count: int, mode: str) -> dict:
    return {"created": created_count, "mode": mode}


def batch_delete_response(deleted_count: int) -> dict:
    return {"deleted": deleted_count}


def delete_response(task_id: str) -> dict:
    return {"deleted": True, "task_id": task_id}

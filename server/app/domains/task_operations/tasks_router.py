"""任务运营业务域模块。

任务运营业务域，负责任务参数解析、执行用例、实时事件和路由接口。本文件负责 tasks_router 相关业务规则、状态转换和外部系统边界。
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_admin_token

from . import param_resolution, realtime_events, task_use_cases
from .schemas import BatchDeleteRequest, TaskBatchCreateRequest, TaskCreateRequest

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

_maybe_resolve_content_template = param_resolution.maybe_resolve_content_template
_maybe_resolve_dm_sequence = param_resolution.maybe_resolve_dm_sequence
_maybe_expand_keywords = param_resolution.maybe_expand_keywords
_maybe_resolve_nurture_subtask_templates = param_resolution.maybe_resolve_nurture_subtask_templates
_resolve_task_type = param_resolution.resolve_task_type
_validate_and_normalize_params = param_resolution.validate_and_normalize_params


@router.post("")
async def create_task(
    request: TaskCreateRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    try:
        task = await task_use_cases.create_task(db, request, user)
    except task_use_cases.TaskParamsError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except task_use_cases.TaskValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await realtime_events.broadcast_new_task_available()
    await realtime_events.broadcast_task_updated(task.id, "pending")
    return task


@router.post("/batch")
async def batch_create_tasks(
    request: TaskBatchCreateRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    try:
        outcome = await task_use_cases.batch_create_tasks(db, request, user)
    except task_use_cases.TaskParamsError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except task_use_cases.TaskValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if outcome.notify_devices:
        await realtime_events.broadcast_new_task_available()
    if outcome.notify_admins:
        await realtime_events.broadcast_tasks_changed()
    return outcome.payload


@router.get("")
def list_tasks(
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None, alias="type"),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    return task_use_cases.list_tasks(
        db=db,
        status=status,
        task_type=type,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        skip=skip,
        limit=limit,
        user=user,
    )


@router.post("/batch-delete")
async def batch_delete_tasks(
    body: BatchDeleteRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    result = task_use_cases.batch_delete_tasks(db, body.task_ids)
    await realtime_events.broadcast_tasks_changed()
    return result


@router.get("/{task_id}")
def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    try:
        return task_use_cases.get_task(db, task_id)
    except task_use_cases.TaskNotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    try:
        task = task_use_cases.cancel_task(db, task_id)
    except task_use_cases.TaskNotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")
    except task_use_cases.TaskValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if task.device_id:
        await realtime_events.send_cancel_task(task.device_id, task.id)

    await realtime_events.broadcast_new_task_available()
    await realtime_events.broadcast_task_updated(task.id, "cancelled")
    return task


@router.delete("/{task_id}")
async def delete_task(task_id: str, db=Depends(get_db), _=Depends(verify_admin_token)):
    try:
        result = task_use_cases.delete_task(db, task_id)
    except task_use_cases.TaskNotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")
    except task_use_cases.TaskValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await realtime_events.broadcast_tasks_changed()
    return result

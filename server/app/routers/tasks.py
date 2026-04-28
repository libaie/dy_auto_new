"""Task management API -- create, list, get tasks."""
from fastapi import APIRouter, HTTPException, Header, Query
from typing import Optional

from app.config import DEVICE_SECRET
from app.models import TaskCreateRequest, TaskStatus
from app.services.task_service import task_service

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _verify_device_secret(x_device_secret: Optional[str] = Header(None)):
    if x_device_secret != DEVICE_SECRET:
        raise HTTPException(status_code=401, detail="Invalid device secret")


@router.post("")
def create_task(
    request: TaskCreateRequest,
    x_device_secret: Optional[str] = Header(None, alias="X-Device-Secret"),
):
    _verify_device_secret(x_device_secret)
    task = task_service.create_task(
        task_type=request.type,
        account_id=request.account_id,
        params=request.params,
        scheduled_at=request.scheduled_at,
    )
    return task


@router.get("")
def list_tasks(
    status: Optional[TaskStatus] = Query(None),
    x_device_secret: Optional[str] = Header(None, alias="X-Device-Secret"),
):
    _verify_device_secret(x_device_secret)
    tasks = task_service.list_tasks(status=status)
    return {"tasks": tasks, "total": len(tasks)}


@router.get("/{task_id}")
def get_task(
    task_id: str,
    x_device_secret: Optional[str] = Header(None, alias="X-Device-Secret"),
):
    _verify_device_secret(x_device_secret)
    task = task_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

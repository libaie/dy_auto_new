"""Task management API -- create, list, get tasks."""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
from sqlalchemy.orm import Session

from app.models import TaskCreateRequest, TaskStatus
from app.database import get_db
from app.deps import verify_device_secret
from app.services.task_service import task_service

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("")
def create_task(
    request: TaskCreateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    task = task_service.create_task(
        db=db,
        task_type=request.type,
        account_id=request.account_id,
        params=request.params,
        scheduled_at=request.scheduled_at,
    )
    return task


@router.get("")
def list_tasks(
    status: Optional[TaskStatus] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    limit = min(limit, 100)
    tasks = task_service.list_tasks(db=db, status=status, skip=skip, limit=limit)
    total = task_service.count_tasks(db=db, status=status)
    return {"tasks": tasks, "total": total}


@router.get("/{task_id}")
def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    task = task_service.get_task(db=db, task_id=task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/{task_id}/cancel")
def cancel_task(
    task_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    try:
        task = task_service.cancel_task(db=db, task_id=task_id)
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail="Task not found")
        raise HTTPException(status_code=400, detail=str(e))
    return task

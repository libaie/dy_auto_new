"""Minimal tasks router stub -- Task 7 will flesh this out."""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional

from app.config import DEVICE_SECRET
from app.models import TaskCreateRequest
from app.services.task_service import task_service

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _verify_device_secret(x_device_secret: Optional[str] = Header(None)):
    if x_device_secret != DEVICE_SECRET:
        raise HTTPException(status_code=401, detail="Invalid device secret")


@router.post("")
def create_task(
    req: TaskCreateRequest,
    x_device_secret: str = Header(..., alias="X-Device-Secret"),
):
    _verify_device_secret(x_device_secret)
    task = task_service.create_task(
        task_type=req.type,
        account_id=req.account_id,
        params=req.params,
        scheduled_at=req.scheduled_at,
    )
    return task

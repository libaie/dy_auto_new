"""Request schemas for admin task operations."""

from typing import Optional

from pydantic import BaseModel

from app.models import TaskType


class TaskCreateRequest(BaseModel):
    type: TaskType
    account_id: Optional[str] = None
    device_id: Optional[str] = None
    params: dict = {}


class TaskBatchCreateRequest(BaseModel):
    type: TaskType
    group_ids: list[str] = []
    account_ids: list[str] = []
    device_id: Optional[str] = None
    params: dict = {}


class BatchDeleteRequest(BaseModel):
    task_ids: list[str]

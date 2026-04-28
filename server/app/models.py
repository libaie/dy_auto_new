from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
import uuid


class TaskType(str, Enum):
    NURTURE = "nurture"
    SEARCH_COMMENT = "search_comment"
    SEARCH_LIKE = "search_like"
    SEARCH_DM = "search_dm"
    REPLY_COMMENT = "reply_comment"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: TaskType
    account_id: str
    device_id: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[dict[str, Any]] = None
    retry_count: int = 0


class AccountConfig(BaseModel):
    id: str
    nickname: str
    douyin_id: str
    status: str = "active"
    daily_limits: dict[str, int] = Field(default_factory=lambda: {
        "likes": 50,
        "comments": 20,
        "follows": 20,
        "dms": 10,
        "replies": 15,
    })


class SelectorStrategy(BaseModel):
    type: str  # text, id, desc, coordinate
    value: Optional[str] = None
    x_percent: Optional[float] = None
    y_percent: Optional[float] = None
    priority: int


class SelectorConfig(BaseModel):
    action_name: str
    platform_version: str = "default"
    strategies: list[SelectorStrategy]
    version: int = 1


class TaskCreateRequest(BaseModel):
    type: TaskType
    account_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    scheduled_at: Optional[datetime] = None


class TaskResultReport(BaseModel):
    task_id: str
    status: TaskStatus
    result: Optional[dict[str, Any]] = None
    ui_snapshot: Optional[dict[str, Any]] = None


class PollResponse(BaseModel):
    task: Optional[Task] = None
    selectors_version: int = 1
    proxy: Optional[dict[str, Any]] = None


class DeviceRegisterRequest(BaseModel):
    device_id: str
    name: str
    os_version: str = ""
    app_version: str = ""

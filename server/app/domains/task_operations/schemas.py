"""任务运营业务域模块。

任务运营业务域，负责任务参数解析、执行用例、实时事件和路由接口。本文件负责 schemas 相关业务规则、状态转换和外部系统边界。
"""

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

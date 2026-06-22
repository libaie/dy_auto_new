"""任务运营业务域模块。

任务运营业务域，负责任务参数解析、执行用例、实时事件和路由接口。本文件负责 schemas 相关业务规则、状态转换和外部系统边界。
"""

from typing import Optional

from pydantic import BaseModel

from app.models import TaskType


class TaskCreateRequest(BaseModel):
    """业务类：承载 TaskCreateRequest 相关的数据结构、状态或业务协作。

    类参数：account_id、device_id、params、type 承载该类的业务配置、状态或数据字段。
    """
    type: TaskType
    account_id: Optional[str] = None
    device_id: Optional[str] = None
    params: dict = {}


class TaskBatchCreateRequest(BaseModel):
    """业务类：承载 TaskBatchCreateRequest 相关的数据结构、状态或业务协作。

    类参数：account_ids、device_id、group_ids、params、type 承载该类的业务配置、状态或数据字段。
    """
    type: TaskType
    group_ids: list[str] = []
    account_ids: list[str] = []
    device_id: Optional[str] = None
    params: dict = {}


class BatchDeleteRequest(BaseModel):
    """业务类：承载 BatchDeleteRequest 相关的数据结构、状态或业务协作。

    类参数：task_ids 承载该类的业务配置、状态或数据字段。
    """
    task_ids: list[str]

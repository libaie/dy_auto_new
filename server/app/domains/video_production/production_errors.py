"""视频生产业务域模块。

视频生产业务域，负责生产计划、作业队列、provider 执行、审核门禁和资产状态流转。本文件负责 production_errors 相关业务规则、状态转换和外部系统边界。
"""

from dataclasses import dataclass, field
from enum import Enum


class ProductionErrorCode(str, Enum):
    """业务类：承载 ProductionErrorCode 相关的数据结构、状态或业务协作。

    类参数：ASSET_COPY_FAILED、ASSET_STORAGE_FAILED、ASSET_URL_MISSING、BUDGET_BLOCKED、BUDGET_EXCEEDED、BUDGET_EXHAUSTED_AFTER_ACTUAL_COST、EPISODE_ASSET_SCOPE_MISSING、INVALID_RUN_TYPE、MIGRATION_HEALTH_BLOCKED、PAUSED_BY_OPERATOR、PROVIDER_STAGE_TASK_EXISTS、PROVIDER_STAGE_TASK_SYNC_REQUIRED、PROVIDER_SUBMIT_FAILED、PROVIDER_TASK_FAILED、PROVIDER_TASK_PENDING、PROVIDER_THROTTLED、RETRY_IMPACT_BLOCKED、REVIEW_GATE_BLOCKED、REVIEW_PERMISSION_DENIED、RUN_LINK_AMBIGUOUS、RUN_LINK_MISSING、RUN_NOT_FOUND、SEGMENT_PLAN_MISSING、STALE_ASSET_VERSION、STORYBOARD_MISSING、STYLE_LOCK_MISSING、TEXT_ARTIFACT_REVIEW_REQUIRED 承载该类的业务配置、状态或数据字段。
    """
    INVALID_RUN_TYPE = "INVALID_RUN_TYPE"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    STYLE_LOCK_MISSING = "STYLE_LOCK_MISSING"
    STORYBOARD_MISSING = "STORYBOARD_MISSING"
    SEGMENT_PLAN_MISSING = "SEGMENT_PLAN_MISSING"
    RUN_LINK_AMBIGUOUS = "RUN_LINK_AMBIGUOUS"
    RUN_LINK_MISSING = "RUN_LINK_MISSING"
    PROVIDER_TASK_PENDING = "PROVIDER_TASK_PENDING"
    PROVIDER_TASK_FAILED = "PROVIDER_TASK_FAILED"
    ASSET_URL_MISSING = "ASSET_URL_MISSING"
    ASSET_COPY_FAILED = "ASSET_COPY_FAILED"
    STALE_ASSET_VERSION = "STALE_ASSET_VERSION"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    BUDGET_BLOCKED = "BUDGET_BLOCKED"
    BUDGET_EXHAUSTED_AFTER_ACTUAL_COST = "BUDGET_EXHAUSTED_AFTER_ACTUAL_COST"
    PAUSED_BY_OPERATOR = "PAUSED_BY_OPERATOR"
    RETRY_IMPACT_BLOCKED = "RETRY_IMPACT_BLOCKED"
    PROVIDER_STAGE_TASK_EXISTS = "PROVIDER_STAGE_TASK_EXISTS"
    PROVIDER_STAGE_TASK_SYNC_REQUIRED = "PROVIDER_STAGE_TASK_SYNC_REQUIRED"
    PROVIDER_SUBMIT_FAILED = "PROVIDER_SUBMIT_FAILED"
    PROVIDER_THROTTLED = "PROVIDER_THROTTLED"
    ASSET_STORAGE_FAILED = "ASSET_STORAGE_FAILED"
    REVIEW_PERMISSION_DENIED = "REVIEW_PERMISSION_DENIED"
    REVIEW_GATE_BLOCKED = "REVIEW_GATE_BLOCKED"
    MIGRATION_HEALTH_BLOCKED = "MIGRATION_HEALTH_BLOCKED"
    TEXT_ARTIFACT_REVIEW_REQUIRED = "TEXT_ARTIFACT_REVIEW_REQUIRED"
    EPISODE_ASSET_SCOPE_MISSING = "EPISODE_ASSET_SCOPE_MISSING"


@dataclass
class ProductionRepairableError(ValueError):
    """业务类：承载 ProductionRepairableError 相关的数据结构、状态或业务协作。

    类参数：affected_ids、cause、code、message、repair_action、repair_route、retryable 承载该类的业务配置、状态或数据字段。
    """
    code: ProductionErrorCode
    message: str
    repair_action: str
    repair_route: str | None = None
    retryable: bool = False
    affected_ids: list[str] = field(default_factory=list)
    cause: str | None = None


def to_http_detail(error: ProductionRepairableError) -> dict:
    """业务函数：处理 to_http_detail 对应的业务流程、校验或数据转换。

    入参：error 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return {
        "code": error.code.value,
        "error_code": error.code.value,
        "message": error.message,
        "cause": error.cause,
        "repair_action": error.repair_action,
        "repair_route": error.repair_route,
        "retryable": error.retryable,
        "affected_ids": error.affected_ids,
    }

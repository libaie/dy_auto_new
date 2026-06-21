"""视频生产业务域模块。

视频生产业务域，负责生产计划、作业队列、provider 执行、审核门禁和资产状态流转。本文件负责 production_errors 相关业务规则、状态转换和外部系统边界。
"""

from dataclasses import dataclass, field
from enum import Enum


class ProductionErrorCode(str, Enum):
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
    code: ProductionErrorCode
    message: str
    repair_action: str
    repair_route: str | None = None
    retryable: bool = False
    affected_ids: list[str] = field(default_factory=list)
    cause: str | None = None


def to_http_detail(error: ProductionRepairableError) -> dict:
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

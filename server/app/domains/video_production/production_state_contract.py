"""视频生产业务域模块。

视频生产业务域，负责生产计划、作业队列、provider 执行、审核门禁和资产状态流转。本文件负责 production_state_contract 相关业务规则、状态转换和外部系统边界。
"""

PROVIDER_TASK_RESERVED = "reserved"
PROVIDER_TASK_SUBMITTED = "submitted"
PROVIDER_TASK_RUNNING = "running"
PROVIDER_TASK_SUCCEEDED = "succeeded"
PROVIDER_TASK_FAILED = "failed"
PROVIDER_TASK_CANCELLED = "cancelled"
PROVIDER_TASK_BLOCKED = "blocked"
PROVIDER_TASK_SYNC_REQUIRED = "sync_required"
PROVIDER_TASK_MANUAL_REPAIR_REQUIRED = "manual_repair_required"

PROVIDER_TASK_ACTIVE_STATUSES = {
    PROVIDER_TASK_RESERVED,
    PROVIDER_TASK_SUBMITTED,
    PROVIDER_TASK_RUNNING,
    PROVIDER_TASK_SYNC_REQUIRED,
    PROVIDER_TASK_MANUAL_REPAIR_REQUIRED,
}

PROVIDER_TASK_TERMINAL_STATUSES = {
    PROVIDER_TASK_SUCCEEDED,
    PROVIDER_TASK_FAILED,
    PROVIDER_TASK_CANCELLED,
}

COST_ACTIVE_UNSUBMITTED = "active_unsubmitted"
COST_SUBMITTED = "submitted"
COST_SETTLED = "settled"
COST_RELEASED = "released"
COST_STALE_NEEDS_REPAIR = "stale_needs_repair"

ASSET_REVIEWABLE_STATUSES = {
    "review_pending",
}

TRANSITIONS = {
    "provider_stage_task": {
        PROVIDER_TASK_RESERVED: {
            PROVIDER_TASK_SUBMITTED,
            PROVIDER_TASK_SYNC_REQUIRED,
            PROVIDER_TASK_MANUAL_REPAIR_REQUIRED,
            PROVIDER_TASK_CANCELLED,
        },
        PROVIDER_TASK_SUBMITTED: {
            PROVIDER_TASK_RUNNING,
            PROVIDER_TASK_SUCCEEDED,
            PROVIDER_TASK_FAILED,
            PROVIDER_TASK_CANCELLED,
            PROVIDER_TASK_SYNC_REQUIRED,
            PROVIDER_TASK_MANUAL_REPAIR_REQUIRED,
        },
        PROVIDER_TASK_RUNNING: {
            PROVIDER_TASK_SUCCEEDED,
            PROVIDER_TASK_FAILED,
            PROVIDER_TASK_CANCELLED,
            PROVIDER_TASK_SYNC_REQUIRED,
            PROVIDER_TASK_MANUAL_REPAIR_REQUIRED,
        },
        PROVIDER_TASK_SYNC_REQUIRED: {
            PROVIDER_TASK_SUBMITTED,
            PROVIDER_TASK_RUNNING,
            PROVIDER_TASK_MANUAL_REPAIR_REQUIRED,
            PROVIDER_TASK_FAILED,
            PROVIDER_TASK_CANCELLED,
        },
        PROVIDER_TASK_MANUAL_REPAIR_REQUIRED: {
            PROVIDER_TASK_SYNC_REQUIRED,
            PROVIDER_TASK_SUBMITTED,
            PROVIDER_TASK_CANCELLED,
            PROVIDER_TASK_FAILED,
        },
        PROVIDER_TASK_BLOCKED: {PROVIDER_TASK_SUBMITTED, PROVIDER_TASK_CANCELLED},
        PROVIDER_TASK_FAILED: set(),
        PROVIDER_TASK_SUCCEEDED: set(),
        PROVIDER_TASK_CANCELLED: set(),
    },
}


def provider_task_is_active(status: str) -> bool:
    """业务函数：处理 provider_task_is_active 对应的业务流程、校验或数据转换。"""
    return status in PROVIDER_TASK_ACTIVE_STATUSES


def asset_is_reviewable(asset_or_status: object) -> bool:
    """业务函数：处理 asset_is_reviewable 对应的业务流程、校验或数据转换。"""
    status = getattr(asset_or_status, "status", asset_or_status)
    return status in ASSET_REVIEWABLE_STATUSES


def validate_transition(entity: str, from_status: str, to_status: str) -> bool:
    """业务函数：处理 validate_transition 对应的业务流程、校验或数据转换。"""
    return to_status in TRANSITIONS.get(entity, {}).get(from_status, set())

"""视频生产业务域模块。

视频生产业务域，负责生产计划、作业队列、provider 执行、审核门禁和资产状态流转。本文件负责 production_cost_service 相关业务规则、状态转换和外部系统边界。
"""

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import bj_now
from app.db.models.video_production import ProductionCostEvent, ProductionJob, ProductionPlan
from app.domains.video_production.production_status import JOB_BLOCKED, JOB_QUEUED, JOB_RETRY_WAIT, PLAN_BLOCKED


def _get_plan(db: Session, plan_id: str) -> ProductionPlan:
    """业务函数：处理 _get_plan 对应的业务流程、校验或数据转换。

    入参：db、plan_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    plan = db.query(ProductionPlan).filter(ProductionPlan.id == plan_id).first()
    if not plan:
        raise ValueError("Production plan not found")
    return plan


def assert_budget_available(db: Session, plan_id: str, estimated_cost: float) -> None:
    """业务函数：处理 assert_budget_available 对应的业务流程、校验或数据转换。

    入参：db、plan_id、estimated_cost 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    plan = _get_plan(db, plan_id)
    if plan.budget_limit is None:
        return

    current_cost = float(plan.current_cost or 0.0)
    if current_cost + float(estimated_cost or 0.0) > plan.budget_limit:
        raise ValueError("budget exceeded")


def record_cost_event(
    db: Session,
    *,
    plan_id: str,
    stage: str,
    provider: str,
    model_name: str,
    estimated_cost: float,
    actual_cost: float,
    currency: str,
    units_json: dict[str, Any],
    episode_plan_id: str | None = None,
    segment_id: str | None = None,
    model_config_id: str | None = None,
    config_version: int = 1,
    provider_task_id: str | None = None,
) -> ProductionCostEvent:
    """业务函数：处理 record_cost_event 对应的业务流程、校验或数据转换。

    入参：db、plan_id、stage、provider、model_name、estimated_cost、actual_cost、currency、units_json、episode_plan_id、segment_id、model_config_id、config_version、provider_task_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    plan = _get_plan(db, plan_id)
    actual_cost_value = float(actual_cost or 0.0)
    event = ProductionCostEvent(
        plan_id=plan_id,
        episode_plan_id=episode_plan_id,
        segment_id=segment_id,
        stage=stage,
        model_config_id=model_config_id,
        config_version=config_version,
        provider_task_id=provider_task_id,
        provider=provider,
        model_name=model_name,
        estimated_cost=float(estimated_cost or 0.0),
        actual_cost=actual_cost_value,
        currency=currency,
        units_json=units_json or {},
    )
    db.add(event)
    db.flush()
    now = bj_now()
    db.query(ProductionPlan).filter(ProductionPlan.id == plan.id).update(
        {
            "current_cost": func.coalesce(ProductionPlan.current_cost, 0.0) + actual_cost_value,
            "updated_at": now,
        },
        synchronize_session=False,
    )
    db.commit()
    db.refresh(event)
    return event


def pause_plan_for_budget(db: Session, plan_id: str, reason: str = "budget_exceeded") -> int:
    """业务函数：处理 pause_plan_for_budget 对应的业务流程、校验或数据转换。

    入参：db、plan_id、reason 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    plan = _get_plan(db, plan_id)
    now = bj_now()
    blocked_count = (
        db.query(ProductionJob)
        .filter(ProductionJob.plan_id == plan_id, ProductionJob.status.in_([JOB_QUEUED, JOB_RETRY_WAIT]))
        .update({"status": JOB_BLOCKED, "error_code": reason, "updated_at": now}, synchronize_session=False)
    )
    plan.status = PLAN_BLOCKED
    plan.error_message = reason
    plan.updated_at = now
    db.commit()
    db.refresh(plan)
    return blocked_count

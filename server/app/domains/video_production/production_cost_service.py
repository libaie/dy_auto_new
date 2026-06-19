from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import ProductionCostEvent, ProductionJob, ProductionPlan
from app.services.production_status import JOB_BLOCKED, JOB_QUEUED, JOB_RETRY_WAIT, PLAN_BLOCKED


def _get_plan(db: Session, plan_id: str) -> ProductionPlan:
    plan = db.query(ProductionPlan).filter(ProductionPlan.id == plan_id).first()
    if not plan:
        raise ValueError("Production plan not found")
    return plan


def assert_budget_available(db: Session, plan_id: str, estimated_cost: float) -> None:
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

from __future__ import annotations

from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.image_production import ImageProductionCostEvent
from app.db_models import ImageCreationTask


def _usage_from_provider_response(task: ImageCreationTask) -> dict[str, Any]:
    response = task.provider_response_json or {}
    usage = response.get("usage") if isinstance(response, dict) else {}
    if isinstance(usage, dict) and usage:
        return usage
    stored_usage = task.usage_json or {}
    return stored_usage if isinstance(stored_usage, dict) else {}


def _event_key(task: ImageCreationTask, event_type: str) -> str:
    if event_type == "actual":
        return f"{task.id}:actual:{task.provider_task_id or task.pixelle_task_id or 'current'}"
    return f"{task.id}:{event_type}"


def _existing(db: Session, event_key: str) -> ImageProductionCostEvent | None:
    return (
        db.query(ImageProductionCostEvent)
        .filter(ImageProductionCostEvent.event_key == event_key)
        .first()
    )


def record_estimated_cost_event(db: Session, task: ImageCreationTask) -> ImageProductionCostEvent:
    event_key = _event_key(task, "estimate")
    existing = _existing(db, event_key)
    if existing:
        return existing
    estimate = task.estimated_cost_json or {}
    event = ImageProductionCostEvent(
        event_key=event_key,
        task_id=task.id,
        event_type="estimate",
        stage="image_generation",
        strategy_id=task.strategy_id,
        strategy_version=task.strategy_version,
        model_id=task.model_id,
        provider=task.provider,
        provider_task_id=task.provider_task_id,
        estimated_cost=float(estimate.get("amount") or 0.0),
        actual_cost=0.0,
        currency=estimate.get("currency") or "CNY",
        units_json=estimate.get("units") or {},
        estimate_source=estimate.get("estimate_source") or "policy",
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = _existing(db, event_key)
        if existing:
            return existing
        raise
    db.refresh(event)
    return event


def record_actual_cost_event(db: Session, task: ImageCreationTask) -> ImageProductionCostEvent | None:
    event_key = _event_key(task, "actual")
    existing = _existing(db, event_key)
    if existing:
        return existing
    usage = _usage_from_provider_response(task)
    if "actual_cost" in usage:
        actual_cost = usage["actual_cost"]
    elif "cost" in usage:
        actual_cost = usage["cost"]
    else:
        return None
    event = ImageProductionCostEvent(
        event_key=event_key,
        task_id=task.id,
        event_type="actual",
        stage="image_generation",
        strategy_id=task.strategy_id,
        strategy_version=task.strategy_version,
        model_id=task.model_id,
        provider=task.provider,
        provider_task_id=task.provider_task_id,
        estimated_cost=float((task.estimated_cost_json or {}).get("amount") or 0.0),
        actual_cost=float(actual_cost),
        currency=usage.get("currency") or (task.estimated_cost_json or {}).get("currency") or "CNY",
        units_json=usage,
        estimate_source=(task.estimated_cost_json or {}).get("estimate_source") or "policy",
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = _existing(db, event_key)
        if existing:
            return existing
        raise
    db.refresh(event)
    return event

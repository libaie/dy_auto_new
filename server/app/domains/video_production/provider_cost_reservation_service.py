"""视频生产业务域模块。

视频生产业务域，负责生产计划、作业队列、provider 执行、审核门禁和资产状态流转。本文件负责 provider_cost_reservation_service 相关业务规则、状态转换和外部系统边界。
"""

import threading

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import bj_now
from app.db.models.video_production import ProviderCostReservation, ProductionPlan
from app.domains.video_production.production_errors import ProductionErrorCode, ProductionRepairableError
from app.domains.video_production.production_state_contract import (
    COST_ACTIVE_UNSUBMITTED,
    COST_RELEASED,
    COST_SETTLED,
    COST_STALE_NEEDS_REPAIR,
    COST_SUBMITTED,
)

_ACTIVE_RESERVATION_STATUSES = (
    COST_ACTIVE_UNSUBMITTED,
    COST_SUBMITTED,
    COST_STALE_NEEDS_REPAIR,
)
_PLAN_LOCKS: dict[str, threading.RLock] = {}
_PLAN_LOCKS_GUARD = threading.Lock()


def _plan_lock(plan_id: str) -> threading.RLock:
    with _PLAN_LOCKS_GUARD:
        lock = _PLAN_LOCKS.get(plan_id)
        if lock is None:
            lock = threading.RLock()
            _PLAN_LOCKS[plan_id] = lock
        return lock


def _plan(db: Session, plan_id: str) -> ProductionPlan:
    plan = db.query(ProductionPlan).filter(ProductionPlan.id == plan_id).first()
    if not plan:
        raise ValueError("Production plan not found")
    return plan


def _locked_plan(db: Session, plan_id: str) -> ProductionPlan:
    query = db.query(ProductionPlan).filter(ProductionPlan.id == plan_id)
    if db.get_bind().dialect.name == "sqlite":
        plan = query.first()
    else:
        plan = query.with_for_update().first()
    if not plan:
        raise ValueError("Production plan not found")
    return plan


def _reservation(db: Session, reservation_id: str) -> ProviderCostReservation:
    reservation = (
        db.query(ProviderCostReservation)
        .filter(ProviderCostReservation.id == reservation_id)
        .first()
    )
    if not reservation:
        raise ValueError("Provider cost reservation not found")
    return reservation


def _repairable_state_error(message: str, reservation: ProviderCostReservation) -> ProductionRepairableError:
    return ProductionRepairableError(
        code=ProductionErrorCode.BUDGET_BLOCKED,
        message=message,
        cause="provider_cost_reservation_state_invalid",
        repair_action="Inspect the provider task state and reconcile the cost reservation manually.",
        repair_route="/video-production",
        retryable=True,
        affected_ids=[reservation.id],
    )


def active_reserved_cost(db: Session, plan_id: str) -> float:
    total = (
        db.query(func.coalesce(func.sum(ProviderCostReservation.reserved_cost), 0.0))
        .filter(
            ProviderCostReservation.plan_id == plan_id,
            ProviderCostReservation.status.in_(_ACTIVE_RESERVATION_STATUSES),
        )
        .scalar()
    )
    return float(total or 0.0)


def create_cost_reservation(
    db: Session,
    *,
    plan_id: str,
    provider_stage_task_id: str,
    estimated_cost: float,
    currency: str = "CNY",
    expires_at=None,
) -> ProviderCostReservation:
    with _plan_lock(plan_id):
        plan = _locked_plan(db, plan_id)
        estimated = float(estimated_cost)
        reserved = active_reserved_cost(db, plan_id)
        current = float(plan.current_cost or 0.0)

        if plan.budget_limit is not None and current + reserved + estimated > float(plan.budget_limit):
            raise ProductionRepairableError(
                code=ProductionErrorCode.BUDGET_BLOCKED,
                message="Provider cost reservation would exceed the production plan budget.",
                cause="budget_reserved_cost_limit_exceeded",
                repair_action="Increase the budget, release stale reservations, or reduce provider usage before retrying.",
                repair_route="/video-production",
                retryable=True,
                affected_ids=[plan.id],
            )

        reservation = ProviderCostReservation(
            plan_id=plan_id,
            provider_stage_task_id=provider_stage_task_id,
            status=COST_ACTIVE_UNSUBMITTED,
            estimated_cost=estimated,
            reserved_cost=estimated,
            currency=currency,
            expires_at=expires_at,
        )
        db.add(reservation)
        db.commit()
        db.refresh(reservation)
        return reservation


def mark_reservation_submitted(db: Session, reservation_id: str) -> ProviderCostReservation:
    reservation = _reservation(db, reservation_id)
    if reservation.status == COST_SUBMITTED:
        return reservation
    if reservation.status != COST_ACTIVE_UNSUBMITTED:
        raise _repairable_state_error(
            "Only active unsubmitted cost reservations can be marked submitted.",
            reservation,
        )

    reservation.status = COST_SUBMITTED
    reservation.submitted_at = reservation.submitted_at or bj_now()
    db.commit()
    db.refresh(reservation)
    return reservation


def mark_reservation_stale_needs_repair(db: Session, reservation_id: str) -> ProviderCostReservation:
    reservation = _reservation(db, reservation_id)
    if reservation.status == COST_STALE_NEEDS_REPAIR:
        return reservation
    if reservation.status not in (COST_ACTIVE_UNSUBMITTED, COST_SUBMITTED):
        raise _repairable_state_error(
            "Only active unsubmitted or submitted cost reservations can be marked stale.",
            reservation,
        )

    reservation.status = COST_STALE_NEEDS_REPAIR
    db.commit()
    db.refresh(reservation)
    return reservation


def settle_reservation(
    db: Session,
    reservation_id: str,
    *,
    actual_cost: float,
    units_json=None,
) -> ProviderCostReservation:
    with db.no_autoflush:
        plan_id = (
            db.query(ProviderCostReservation.plan_id)
            .filter(ProviderCostReservation.id == reservation_id)
            .scalar()
        )
    if not plan_id:
        raise ValueError("Provider cost reservation not found")

    with _plan_lock(plan_id):
        with db.no_autoflush:
            reservation = (
                db.query(ProviderCostReservation)
                .populate_existing()
                .filter(ProviderCostReservation.id == reservation_id)
                .first()
            )
        if not reservation:
            raise ValueError("Provider cost reservation not found")
        if reservation.status == COST_SETTLED:
            return reservation
        if reservation.status not in (COST_SUBMITTED, COST_STALE_NEEDS_REPAIR):
            raise _repairable_state_error(
                "Only submitted or stale cost reservations can be settled.",
                reservation,
            )

        actual = float(actual_cost)
        updated = (
            db.query(ProviderCostReservation)
            .filter(
                ProviderCostReservation.id == reservation_id,
                ProviderCostReservation.status.in_((COST_SUBMITTED, COST_STALE_NEEDS_REPAIR)),
            )
            .update(
                {
                    "status": COST_SETTLED,
                    "actual_cost": actual,
                    "units_json": units_json or {},
                    "settled_at": bj_now(),
                },
                synchronize_session=False,
            )
        )
        if updated:
            db.query(ProductionPlan).filter(ProductionPlan.id == plan_id).update(
                {"current_cost": func.coalesce(ProductionPlan.current_cost, 0.0) + actual},
                synchronize_session=False,
            )
            db.commit()

        return (
            db.query(ProviderCostReservation)
            .populate_existing()
            .filter(ProviderCostReservation.id == reservation_id)
            .first()
        )


def release_unsubmitted_reservation(db: Session, reservation_id: str) -> ProviderCostReservation:
    reservation = _reservation(db, reservation_id)
    if reservation.status == COST_RELEASED:
        return reservation
    if reservation.status != COST_ACTIVE_UNSUBMITTED:
        raise _repairable_state_error(
            "Only active unsubmitted cost reservations can be released.",
            reservation,
        )

    reservation.status = COST_RELEASED
    db.commit()
    db.refresh(reservation)
    return reservation


def expire_unsubmitted_reservations(db: Session) -> int:
    now = bj_now()
    expired = (
        db.query(ProviderCostReservation)
        .filter(
            ProviderCostReservation.expires_at.isnot(None),
            ProviderCostReservation.expires_at <= now,
            ProviderCostReservation.status.in_((COST_ACTIVE_UNSUBMITTED, COST_SUBMITTED)),
        )
        .all()
    )

    for reservation in expired:
        if reservation.status == COST_ACTIVE_UNSUBMITTED:
            reservation.status = COST_RELEASED
        elif reservation.status == COST_SUBMITTED:
            reservation.status = COST_STALE_NEEDS_REPAIR

    if expired:
        db.commit()
    return len(expired)

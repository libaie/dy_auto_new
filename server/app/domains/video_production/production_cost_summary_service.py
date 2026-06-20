from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.db.models.video_production import ProviderCostReservation
from app.db_models import ProductionCostEvent, VideoProductionRun
from app.domains.video_production.production_state_contract import (
    COST_ACTIVE_UNSUBMITTED,
    COST_RELEASED,
    COST_SETTLED,
    COST_STALE_NEEDS_REPAIR,
    COST_SUBMITTED,
)

_ZERO_RESERVATION_COSTS = {
    "active_reserved_cost": 0.0,
    "stale_needs_repair_cost": 0.0,
    "settled_cost": 0.0,
    "released_cost": 0.0,
}
_ACTIVE_RESERVATION_STATUSES = (
    COST_ACTIVE_UNSUBMITTED,
    COST_SUBMITTED,
    COST_STALE_NEEDS_REPAIR,
)


def _reservation_costs(db: Session, plan_id: str) -> dict:
    active_reserved, stale, settled, released = (
        db.query(
            func.coalesce(
                func.sum(
                    case(
                        (
                            ProviderCostReservation.status.in_(_ACTIVE_RESERVATION_STATUSES),
                            ProviderCostReservation.reserved_cost,
                        ),
                        else_=0.0,
                    )
                ),
                0.0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (
                            ProviderCostReservation.status == COST_STALE_NEEDS_REPAIR,
                            ProviderCostReservation.reserved_cost,
                        ),
                        else_=0.0,
                    )
                ),
                0.0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (
                            ProviderCostReservation.status == COST_SETTLED,
                            func.coalesce(ProviderCostReservation.actual_cost, 0.0),
                        ),
                        else_=0.0,
                    )
                ),
                0.0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (
                            ProviderCostReservation.status == COST_RELEASED,
                            ProviderCostReservation.reserved_cost,
                        ),
                        else_=0.0,
                    )
                ),
                0.0,
            ),
        )
        .filter(ProviderCostReservation.plan_id == plan_id)
        .one()
    )
    return {
        "active_reserved_cost": float(active_reserved or 0.0),
        "stale_needs_repair_cost": float(stale or 0.0),
        "settled_cost": float(settled or 0.0),
        "released_cost": float(released or 0.0),
    }


def get_run_costs(db: Session, run_id: str) -> dict:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise ValueError("Run not found")
    plan_id = run.production_plan_id
    if not plan_id:
        return {
            "actual_cost": 0.0,
            "estimated_remaining_cost": 0.0,
            "estimate_status": "unknown",
            "unknown_estimate_reasons": ["run is not linked"],
            "by_stage": [],
            "by_provider_model": [],
            "budget_status": "ok",
            **_ZERO_RESERVATION_COSTS,
        }

    actual = (
        db.query(func.coalesce(func.sum(ProductionCostEvent.actual_cost), 0.0))
        .filter(ProductionCostEvent.plan_id == plan_id)
        .scalar()
    )
    by_stage = (
        db.query(ProductionCostEvent.stage, func.sum(ProductionCostEvent.actual_cost))
        .filter(ProductionCostEvent.plan_id == plan_id)
        .group_by(ProductionCostEvent.stage)
        .all()
    )
    by_provider = (
        db.query(ProductionCostEvent.provider, ProductionCostEvent.model_name, func.sum(ProductionCostEvent.actual_cost))
        .filter(ProductionCostEvent.plan_id == plan_id)
        .group_by(ProductionCostEvent.provider, ProductionCostEvent.model_name)
        .all()
    )
    reservation_costs = _reservation_costs(db, plan_id)
    return {
        "actual_cost": float(actual or 0.0),
        "estimated_remaining_cost": 0.0,
        "estimate_status": "unknown",
        "unknown_estimate_reasons": ["pricing metadata unavailable"],
        "by_stage": [{"stage": stage, "actual_cost": float(cost or 0.0)} for stage, cost in by_stage],
        "by_provider_model": [
            {"provider": provider, "model_name": model, "actual_cost": float(cost or 0.0)}
            for provider, model, cost in by_provider
        ],
        "budget_status": "ok",
        **reservation_costs,
    }

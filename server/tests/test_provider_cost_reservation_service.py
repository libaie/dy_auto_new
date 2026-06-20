from datetime import timedelta

import pytest
from sqlalchemy.orm import Query, sessionmaker

from app.config import bj_now
from app.db.models import (
    Episode,
    ProductionPlan,
    ProviderCostReservation,
    ProviderStageTask,
    Series,
    VideoProductionRun,
)
from app.domains.video_production import provider_cost_reservation_service as reservations
from app.domains.video_production.production_cost_summary_service import get_run_costs
from app.domains.video_production.production_errors import ProductionErrorCode, ProductionRepairableError
from app.domains.video_production.production_state_contract import (
    COST_ACTIVE_UNSUBMITTED,
    COST_RELEASED,
    COST_SETTLED,
    COST_STALE_NEEDS_REPAIR,
    COST_SUBMITTED,
)


@pytest.fixture(autouse=True)
def _clean_provider_reservation_tables(db):
    db.query(ProviderCostReservation).delete()
    db.query(ProviderStageTask).delete()
    db.commit()
    yield
    db.query(ProviderCostReservation).delete()
    db.query(ProviderStageTask).delete()
    db.commit()


def _plan(db, budget_limit=1.0, current_cost=0.0):
    series = Series(title="Reservation Show", logline="Cost boundary", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    plan = ProductionPlan(
        series_id=series.id,
        status="ready",
        target_total_duration_seconds=60,
        budget_limit=budget_limit,
        current_cost=current_cost,
    )
    db.add(plan)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        production_plan_id=plan.id,
        production_link_status="linked",
    )
    db.add(run)
    db.commit()
    return plan, run


def _stage_task(db, plan, run, target_id="seg-1", key_suffix="seg-1"):
    task = ProviderStageTask(
        run_id=run.id,
        plan_id=plan.id,
        target_type="production_segment",
        target_id=target_id,
        stage="image_generation",
        provider="seedance",
        model_name="seedream",
        request_hash=f"hash-{key_suffix}",
        idempotency_key=f"{run.id}:image_generation:{key_suffix}",
        status="reserved",
    )
    db.add(task)
    db.commit()
    return task


def _reservation(db, plan, task, status, reserved_cost, **overrides):
    reservation = ProviderCostReservation(
        plan_id=plan.id,
        provider_stage_task_id=task.id,
        status=status,
        estimated_cost=overrides.pop("estimated_cost", reserved_cost),
        reserved_cost=reserved_cost,
        currency=overrides.pop("currency", "CNY"),
        **overrides,
    )
    db.add(reservation)
    db.commit()
    return reservation


def test_create_cost_reservation_blocks_budget_and_creates_no_reservation(db):
    plan, run = _plan(db, budget_limit=1.0, current_cost=0.8)
    task = _stage_task(db, plan, run)

    with pytest.raises(ProductionRepairableError) as exc_info:
        reservations.create_cost_reservation(
            db,
            plan_id=plan.id,
            provider_stage_task_id=task.id,
            estimated_cost=0.21,
        )

    assert exc_info.value.code == ProductionErrorCode.BUDGET_BLOCKED
    assert db.query(ProviderCostReservation).count() == 0


def test_active_reserved_cost_counts_only_active_reservation_statuses(db):
    plan, run = _plan(db)
    costs_by_status = {
        COST_ACTIVE_UNSUBMITTED: 0.2,
        COST_SUBMITTED: 0.3,
        COST_STALE_NEEDS_REPAIR: 0.4,
        COST_SETTLED: 9.0,
        COST_RELEASED: 8.0,
    }
    for index, (status, cost) in enumerate(costs_by_status.items(), start=1):
        task = _stage_task(db, plan, run, target_id=f"seg-{index}", key_suffix=f"seg-{index}")
        _reservation(db, plan, task, status, cost)

    assert reservations.active_reserved_cost(db, plan.id) == pytest.approx(0.9)


def test_create_cost_reservation_counts_existing_active_reservations(db):
    plan, run = _plan(db, budget_limit=1.0, current_cost=0.2)
    active_task = _stage_task(db, plan, run, target_id="seg-1", key_suffix="seg-1")
    _reservation(db, plan, active_task, COST_SUBMITTED, 0.6)
    new_task = _stage_task(db, plan, run, target_id="seg-2", key_suffix="seg-2")

    with pytest.raises(ProductionRepairableError) as exc_info:
        reservations.create_cost_reservation(
            db,
            plan_id=plan.id,
            provider_stage_task_id=new_task.id,
            estimated_cost=0.25,
        )

    assert exc_info.value.code == ProductionErrorCode.BUDGET_BLOCKED
    assert db.query(ProviderCostReservation).count() == 1


def test_create_cost_reservation_uses_locked_plan_path(db, monkeypatch):
    plan, run = _plan(db, budget_limit=1.0, current_cost=0.1)
    task = _stage_task(db, plan, run)
    locked_plan_calls = []

    def fake_locked_plan(inner_db, plan_id):
        locked_plan_calls.append(plan_id)
        return inner_db.query(ProductionPlan).filter(ProductionPlan.id == plan_id).first()

    monkeypatch.setattr(reservations, "_locked_plan", fake_locked_plan)

    reservation = reservations.create_cost_reservation(
        db,
        plan_id=plan.id,
        provider_stage_task_id=task.id,
        estimated_cost=0.2,
    )

    assert locked_plan_calls == [plan.id]
    assert reservation.status == COST_ACTIVE_UNSUBMITTED
    assert reservation.reserved_cost == pytest.approx(0.2)


def test_locked_plan_uses_plain_query_for_sqlite(db, monkeypatch):
    plan, _run = _plan(db)
    with_for_update_calls = []

    def fail_with_for_update(self, *args, **kwargs):
        with_for_update_calls.append((args, kwargs))
        raise AssertionError("sqlite path should not call with_for_update")

    monkeypatch.setattr(Query, "with_for_update", fail_with_for_update)

    locked_plan = reservations._locked_plan(db, plan.id)

    assert locked_plan.id == plan.id
    assert with_for_update_calls == []


def test_get_run_costs_includes_reservation_accounting_for_linked_run(db):
    plan, run = _plan(db)
    status_costs = (
        (COST_ACTIVE_UNSUBMITTED, 0.2, None),
        (COST_SUBMITTED, 0.3, None),
        (COST_STALE_NEEDS_REPAIR, 0.4, None),
        (COST_SETTLED, 0.5, 0.45),
        (COST_RELEASED, 0.6, None),
    )
    for index, (status, reserved_cost, actual_cost) in enumerate(status_costs, start=1):
        task = _stage_task(db, plan, run, target_id=f"seg-{index}", key_suffix=f"seg-{index}")
        overrides = {}
        if actual_cost is not None:
            overrides["actual_cost"] = actual_cost
        _reservation(db, plan, task, status, reserved_cost, **overrides)

    costs = get_run_costs(db, run.id)

    assert costs["active_reserved_cost"] == pytest.approx(0.9)
    assert costs["stale_needs_repair_cost"] == pytest.approx(0.4)
    assert costs["settled_cost"] == pytest.approx(0.45)
    assert costs["released_cost"] == pytest.approx(0.6)


def test_get_run_costs_returns_zero_reservation_accounting_for_unlinked_run(db):
    _plan(db)
    unlinked_plan, unlinked_run = _plan(db)
    unlinked_run.production_plan_id = None
    db.commit()
    task = _stage_task(db, unlinked_plan, unlinked_run)
    _reservation(db, unlinked_plan, task, COST_SUBMITTED, 0.5)

    costs = get_run_costs(db, unlinked_run.id)

    assert costs["active_reserved_cost"] == pytest.approx(0.0)
    assert costs["stale_needs_repair_cost"] == pytest.approx(0.0)
    assert costs["settled_cost"] == pytest.approx(0.0)
    assert costs["released_cost"] == pytest.approx(0.0)


def test_settle_reservation_updates_plan_once_and_is_idempotent(db):
    plan, run = _plan(db, budget_limit=5.0, current_cost=1.0)
    task = _stage_task(db, plan, run)
    reservation = _reservation(db, plan, task, COST_SUBMITTED, 0.5)

    settled = reservations.settle_reservation(
        db,
        reservation.id,
        actual_cost=0.42,
        units_json={"images": 1},
    )
    db.refresh(plan)
    assert settled.status == COST_SETTLED
    assert settled.actual_cost == pytest.approx(0.42)
    assert settled.units_json == {"images": 1}
    assert plan.current_cost == pytest.approx(1.42)

    settled_again = reservations.settle_reservation(
        db,
        reservation.id,
        actual_cost=99.0,
        units_json={"images": 99},
    )
    db.refresh(plan)
    assert settled_again.status == COST_SETTLED
    assert settled_again.actual_cost == pytest.approx(0.42)
    assert settled_again.units_json == {"images": 1}
    assert plan.current_cost == pytest.approx(1.42)


def test_settle_stale_needs_repair_reservation_updates_plan_once_and_is_idempotent(db):
    plan, run = _plan(db, budget_limit=5.0, current_cost=1.0)
    task = _stage_task(db, plan, run)
    reservation = _reservation(db, plan, task, COST_ACTIVE_UNSUBMITTED, 0.5)
    reservation = reservations.mark_reservation_submitted(db, reservation.id)
    reservation.status = COST_STALE_NEEDS_REPAIR
    db.commit()

    settled = reservations.settle_reservation(
        db,
        reservation.id,
        actual_cost=0.4,
        units_json={"repair": True},
    )
    db.refresh(plan)
    assert settled.status == COST_SETTLED
    assert settled.actual_cost == pytest.approx(0.4)
    assert settled.units_json == {"repair": True}
    assert plan.current_cost == pytest.approx(1.4)

    settled_again = reservations.settle_reservation(
        db,
        reservation.id,
        actual_cost=99.0,
        units_json={"repair": False},
    )
    db.refresh(plan)
    assert settled_again.status == COST_SETTLED
    assert settled_again.actual_cost == pytest.approx(0.4)
    assert settled_again.units_json == {"repair": True}
    assert plan.current_cost == pytest.approx(1.4)


def test_settle_reservation_does_not_double_increment_from_stale_session(db, monkeypatch):
    plan, run = _plan(db, budget_limit=5.0, current_cost=1.0)
    task = _stage_task(db, plan, run)
    reservation = _reservation(db, plan, task, COST_SUBMITTED, 0.5)
    Session = sessionmaker(bind=db.get_bind(), autocommit=False, autoflush=False, expire_on_commit=False)
    first_session = Session()
    stale_session = Session()
    fresh_session = Session()
    try:
        stale_reservation = stale_session.query(ProviderCostReservation).filter(
            ProviderCostReservation.id == reservation.id
        ).first()

        reservations.settle_reservation(
            first_session,
            reservation.id,
            actual_cost=0.4,
            units_json={"race": "first"},
        )
        monkeypatch.setattr(
            reservations,
            "_reservation",
            lambda inner_db, reservation_id: stale_reservation,
        )
        reservations.settle_reservation(
            stale_session,
            reservation.id,
            actual_cost=0.4,
            units_json={"race": "second"},
        )
        settled = fresh_session.query(ProviderCostReservation).filter(
            ProviderCostReservation.id == reservation.id
        ).first()
        fresh_plan = fresh_session.query(ProductionPlan).filter(ProductionPlan.id == plan.id).first()
    finally:
        first_session.close()
        stale_session.close()
        fresh_session.close()

    assert settled.status == COST_SETTLED
    assert settled.actual_cost == pytest.approx(0.4)
    assert settled.units_json == {"race": "first"}
    assert fresh_plan.current_cost == pytest.approx(1.4)


def test_settle_reservation_rejects_unsubmitted_reservation(db):
    plan, run = _plan(db)
    task = _stage_task(db, plan, run)
    reservation = _reservation(db, plan, task, COST_ACTIVE_UNSUBMITTED, 0.5)

    with pytest.raises(ProductionRepairableError):
        reservations.settle_reservation(db, reservation.id, actual_cost=0.5)


def test_release_unsubmitted_reservation_releases_only_active_unsubmitted(db):
    plan, run = _plan(db)
    active_task = _stage_task(db, plan, run, target_id="seg-1", key_suffix="seg-1")
    active = _reservation(db, plan, active_task, COST_ACTIVE_UNSUBMITTED, 0.5)
    submitted_task = _stage_task(db, plan, run, target_id="seg-2", key_suffix="seg-2")
    submitted = _reservation(db, plan, submitted_task, COST_SUBMITTED, 0.5)

    released = reservations.release_unsubmitted_reservation(db, active.id)
    assert released.status == COST_RELEASED

    with pytest.raises(ProductionRepairableError):
        reservations.release_unsubmitted_reservation(db, submitted.id)
    db.refresh(submitted)
    assert submitted.status == COST_SUBMITTED


def test_expire_unsubmitted_reservations_releases_unsubmitted_and_marks_submitted_stale(db):
    plan, run = _plan(db)
    expired = bj_now() - timedelta(minutes=1)
    future = bj_now() + timedelta(minutes=1)
    unsubmitted_task = _stage_task(db, plan, run, target_id="seg-1", key_suffix="seg-1")
    submitted_task = _stage_task(db, plan, run, target_id="seg-2", key_suffix="seg-2")
    future_task = _stage_task(db, plan, run, target_id="seg-3", key_suffix="seg-3")
    unsubmitted = _reservation(
        db,
        plan,
        unsubmitted_task,
        COST_ACTIVE_UNSUBMITTED,
        0.2,
        expires_at=expired,
    )
    submitted = _reservation(db, plan, submitted_task, COST_SUBMITTED, 0.3, expires_at=expired)
    future_unsubmitted = _reservation(
        db,
        plan,
        future_task,
        COST_ACTIVE_UNSUBMITTED,
        0.4,
        expires_at=future,
    )

    changed_count = reservations.expire_unsubmitted_reservations(db)

    db.refresh(unsubmitted)
    db.refresh(submitted)
    db.refresh(future_unsubmitted)
    assert changed_count == 2
    assert unsubmitted.status == COST_RELEASED
    assert submitted.status == COST_STALE_NEEDS_REPAIR
    assert future_unsubmitted.status == COST_ACTIVE_UNSUBMITTED

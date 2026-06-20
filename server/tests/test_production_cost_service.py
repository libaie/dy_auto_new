import pytest

from app.db.models import ProductionCostEvent, ProductionJob, ProductionPlan, Series
from app.domains.video_production.production_cost_service import (
    assert_budget_available,
    pause_plan_for_budget,
    record_cost_event,
)
from app.domains.video_production.production_queue_service import claim_next_job, enqueue_job


def _plan(db, budget_limit=10.0, current_cost=0.0):
    series = Series(title="Cost Show", logline="Cost test", genre="drama")
    db.add(series)
    db.flush()
    plan = ProductionPlan(
        series_id=series.id,
        status="ready",
        target_total_duration_seconds=60,
        budget_limit=budget_limit,
        current_cost=current_cost,
    )
    db.add(plan)
    db.commit()
    return plan


def test_record_cost_event_updates_plan_total(db):
    plan = _plan(db, budget_limit=20.0, current_cost=1.25)

    event = record_cost_event(
        db,
        plan_id=plan.id,
        stage="image_generation",
        provider="seedance",
        model_name="doubao-seedream",
        estimated_cost=3.0,
        actual_cost=2.75,
        currency="CNY",
        units_json={"images": 1},
        model_config_id="config-1",
        config_version=2,
        provider_task_id="provider-task-1",
    )

    db.refresh(plan)
    assert isinstance(event, ProductionCostEvent)
    assert event.plan_id == plan.id
    assert event.stage == "image_generation"
    assert event.provider == "seedance"
    assert event.model_name == "doubao-seedream"
    assert event.estimated_cost == 3.0
    assert event.actual_cost == 2.75
    assert event.currency == "CNY"
    assert event.units_json == {"images": 1}
    assert event.model_config_id == "config-1"
    assert event.config_version == 2
    assert event.provider_task_id == "provider-task-1"
    assert plan.current_cost == pytest.approx(4.0)


def test_assert_budget_available_blocks_overspend(db):
    plan = _plan(db, budget_limit=5.0, current_cost=4.0)

    with pytest.raises(ValueError, match="budget exceeded"):
        assert_budget_available(db, plan.id, estimated_cost=1.01)


def test_assert_budget_available_rejects_missing_plan(db):
    with pytest.raises(ValueError, match="Production plan not found"):
        assert_budget_available(db, "missing-plan", estimated_cost=1.0)


def test_assert_budget_available_allows_when_no_budget(db):
    plan = _plan(db, budget_limit=None, current_cost=100.0)

    assert_budget_available(db, plan.id, estimated_cost=999.0)


def test_pause_plan_for_budget_blocks_jobs_and_plan(db):
    plan = _plan(db, budget_limit=5.0, current_cost=5.0)
    queued = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")
    retry_wait = enqueue_job(db, plan.id, "segment", "seg-2", "image_generation", "seg-2:image:v1")
    leased = enqueue_job(db, plan.id, "segment", "seg-3", "image_generation", "seg-3:image:v1")
    retry_wait.status = "retry_wait"
    leased.status = "leased"
    db.commit()

    blocked_count = pause_plan_for_budget(db, plan.id)

    db.refresh(plan)
    statuses = {job.target_id: job.status for job in db.query(ProductionJob).all()}
    assert blocked_count == 2
    assert statuses[queued.target_id] == "blocked"
    assert statuses[retry_wait.target_id] == "blocked"
    assert statuses[leased.target_id] == "leased"
    assert plan.status == "blocked"
    assert plan.error_message == "budget_exceeded"

    with pytest.raises(ValueError, match="not accepting jobs"):
        enqueue_job(db, plan.id, "segment", "seg-4", "image_generation", "seg-4:image:v1")
    assert claim_next_job(db, lease_id="worker-a") is None

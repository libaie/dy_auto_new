import pytest

from app.db_models import Character, ProductionAuditEvent, ProductionJob, ProductionPlan, Series
from app.services.agency_repair_executor import execute_repair_job
from app.services.production_status import JOB_QUEUED


@pytest.mark.asyncio
async def test_storyboard_repair_records_recheck_without_approval(db):
    series = Series(title="老李控糖", logline="控糖系列", genre="health")
    db.add(series)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready", budget_limit=5.0, current_cost=0.0)
    db.add(plan)
    db.flush()
    job = ProductionJob(
        plan_id=plan.id,
        target_type="episode",
        target_id="episode-1",
        stage="agency_auto_repair:storyboard_missing_references",
        status=JOB_QUEUED,
        idempotency_key="repair:executor:storyboard",
    )
    db.add(job)
    db.flush()

    result = await execute_repair_job(db, job)

    assert result.status == "success"
    assert result.data["repair_recheck_pending"] is True
    event = db.query(ProductionAuditEvent).filter_by(event_type="agency_repair_recheck_required").one()
    assert event.payload_json["result"]["next_gate"] == "人工审查"


@pytest.mark.asyncio
async def test_paid_reference_repair_blocks_for_manual_confirmation(db):
    series = Series(title="老李控糖", logline="控糖系列", genre="health")
    db.add(series)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready", budget_limit=5.0, current_cost=0.0)
    db.add(plan)
    db.flush()
    character = Character(name="老李", role_type="protagonist", gender="male")
    db.add(character)
    db.flush()
    job = ProductionJob(
        plan_id=plan.id,
        target_type="character",
        target_id=character.id,
        stage="agency_auto_repair:missing_character_reference",
        status=JOB_QUEUED,
        idempotency_key="repair:executor:character",
    )
    db.add(job)
    db.flush()

    result = await execute_repair_job(db, job)

    assert result.status == "blocked"
    assert result.repair_route == f"/characters/{character.id}"
    assert "人工确认" in result.message

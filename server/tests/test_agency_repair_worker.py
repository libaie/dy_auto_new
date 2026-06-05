from app.db_models import ProductionAuditEvent, ProductionJob
from app.services.production_status import JOB_COMPLETED, JOB_QUEUED
from app.services.production_worker_service import run_real_worker_step
from tests.test_agency_repair_loop import _series_plan_run


def test_real_worker_dispatches_agency_repair_job(db):
    _, plan, run = _series_plan_run(db)
    job = ProductionJob(
        plan_id=plan.id,
        target_type="episode",
        target_id="episode-1",
        stage="agency_auto_repair:storyboard_missing_references",
        status=JOB_QUEUED,
        idempotency_key="repair:worker:dispatch",
    )
    db.add(job)
    db.commit()

    result = run_real_worker_step(db, run.id, lease_id="agency-repair-worker", batch_size=1)

    db.refresh(job)
    assert result["processed"] == 1
    assert job.status == JOB_COMPLETED
    assert db.query(ProductionAuditEvent).filter_by(event_type="agency_repair_recheck_required").count() == 1

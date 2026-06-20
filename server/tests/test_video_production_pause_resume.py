from fastapi.testclient import TestClient

from app.db.models import ProductionJob, ProductionPlan, ProductionScene, ProductionShot, ProductionEpisode
from app.main import app
from tests.video_production_control_plane_helpers import linked_segment_context


def _job(db, *, plan_id, segment_id, status, key):
    job = ProductionJob(
        plan_id=plan_id,
        target_type="production_segment",
        target_id=segment_id,
        stage="image_generation",
        status=status,
        idempotency_key=key,
    )
    db.add(job)
    db.flush()
    return job


def test_pause_and_resume_linked_run_preserves_job_resume_status(db):
    ctx = linked_segment_context(db)
    run = ctx["run"]
    run.status = "image_approved"
    run.current_stage = "image_review"
    segment = ctx["segment"]
    queued = _job(db, plan_id=ctx["plan"].id, segment_id=segment.id, status="queued", key="queued")
    retry_wait = _job(db, plan_id=ctx["plan"].id, segment_id=segment.id, status="retry_wait", key="retry")
    failed_terminal = _job(db, plan_id=ctx["plan"].id, segment_id=segment.id, status="failed", key="failed")
    db.commit()
    client = TestClient(app)

    pause_resp = client.post(f"/api/video-production/runs/{run.id}/pause")

    assert pause_resp.status_code == 200
    db.refresh(run)
    assert run.status == "paused"
    db.refresh(queued)
    db.refresh(retry_wait)
    db.refresh(failed_terminal)
    assert queued.status == "blocked"
    assert queued.resume_status == "queued"
    assert queued.blocked_reason == "PAUSED_BY_OPERATOR"
    assert retry_wait.status == "blocked"
    assert retry_wait.resume_status == "retry_wait"
    assert failed_terminal.status == "failed"

    resume_resp = client.post(f"/api/video-production/runs/{run.id}/resume")

    assert resume_resp.status_code == 200
    db.refresh(run)
    assert run.status == "image_approved"
    assert run.current_stage == "image_review"
    db.refresh(queued)
    db.refresh(retry_wait)
    db.refresh(failed_terminal)
    assert queued.status == "queued"
    assert queued.resume_status is None
    assert retry_wait.status == "retry_wait"
    assert retry_wait.resume_status is None
    assert failed_terminal.status == "failed"


def test_recompute_from_segment_updates_parent_status(db):
    from app.domains.video_production.production_status_aggregation import recompute_from_segment

    ctx = linked_segment_context(db, segment_status="completed")
    segment = ctx["segment"]

    recompute_from_segment(db, segment.id)

    assert db.query(ProductionShot).filter_by(id=ctx["shot"].id).one().status == "completed"
    assert db.query(ProductionScene).filter_by(id=ctx["scene"].id).one().status == "completed"
    assert db.query(ProductionEpisode).filter_by(id=ctx["production_episode"].id).one().status == "completed"
    assert db.query(ProductionPlan).filter_by(id=ctx["plan"].id).one().status == "completed"

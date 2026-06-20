from app.db.models import (
    ProductionAuditEvent,
    ProductionEpisode,
    ProductionJob,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
)
from app.domains.video_production.production_status import JOB_COMPLETED, JOB_QUEUED
from app.domains.video_production.production_worker_service import run_real_worker_step
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


def test_real_worker_repair_job_enqueues_downstream_image_generation(db):
    _, plan, run = _series_plan_run(db)
    production_episode = ProductionEpisode(plan_id=plan.id, episode_id=run.episode_id, order_index=1, status="ready")
    db.add(production_episode)
    db.flush()
    run.production_episode_id = production_episode.id
    run.status = "image_human_review_required"
    run.current_stage = "image_review"
    scene = ProductionScene(episode_plan_id=production_episode.id, scene_id="scene-1", order_index=1, status="ready")
    db.add(scene)
    db.flush()
    shot = ProductionShot(scene_plan_id=scene.id, shot_id="shot-1", order_index=1, status="ready")
    db.add(shot)
    db.flush()
    segment = ProductionSegment(
        shot_plan_id=shot.id,
        segment_id="seg-1",
        order_index=1,
        status="image_review_pending",
        image_prompt="原始图像提示",
        video_prompt="原始视频提示",
    )
    db.add(segment)
    db.flush()
    repair_job = ProductionJob(
        plan_id=plan.id,
        target_type="production_segment",
        target_id=segment.id,
        stage="agency_auto_repair:image_generation_failed",
        status=JOB_QUEUED,
        idempotency_key="repair:worker:segment-dispatch",
    )
    db.add(repair_job)
    db.commit()

    result = run_real_worker_step(db, run.id, lease_id="agency-repair-worker", batch_size=1)

    db.refresh(repair_job)
    db.refresh(run)
    db.refresh(segment)
    downstream_job = db.query(ProductionJob).filter_by(
        plan_id=plan.id,
        target_type="production_segment",
        target_id=segment.id,
        stage="image_generation",
        status=JOB_QUEUED,
    ).one()
    assert result["processed"] == 1
    assert result["remaining"] == 1
    assert repair_job.status == JOB_COMPLETED
    assert downstream_job.idempotency_key == f"{run.id}:{segment.id}:agency_repair:{repair_job.id}:image_generation"
    assert run.status == "image_batch_running"
    assert run.current_stage == "image_generation"
    assert "自动返修提示" in segment.image_prompt

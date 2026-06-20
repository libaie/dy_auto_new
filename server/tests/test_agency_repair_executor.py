import pytest
from datetime import timedelta

from app.db_models import (
    Character,
    Episode,
    ProductionAuditEvent,
    ProductionEpisode,
    ProductionJob,
    ProductionPlan,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    Series,
    VideoProductionRun,
)
from app.config import bj_now
from app.services.agency_repair_executor import execute_repair_job
from app.services.production_status import JOB_QUEUED, SEGMENT_IMAGE_QUEUED


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
async def test_image_repair_micro_tunes_production_segment_prompt(db):
    series = Series(title="老李控糖", logline="控糖系列", genre="health")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1)
    db.add(episode)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready", budget_limit=5.0, current_cost=0.0)
    db.add(plan)
    db.flush()
    prod_episode = ProductionEpisode(plan_id=plan.id, episode_id=episode.id)
    db.add(prod_episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        production_plan_id=plan.id,
        production_episode_id=prod_episode.id,
        production_link_status="linked",
        status="image_human_review_required",
        current_stage="image_review",
    )
    db.add(run)
    db.flush()
    scene = ProductionScene(episode_plan_id=prod_episode.id, scene_id="scene-1", order_index=1)
    db.add(scene)
    db.flush()
    shot = ProductionShot(scene_plan_id=scene.id, shot_id="shot-1", order_index=1)
    db.add(shot)
    db.flush()
    segment = ProductionSegment(
        shot_plan_id=shot.id,
        segment_id="seg-1",
        image_prompt="原始画面提示",
        video_prompt="原始视频提示",
        status="image_review_pending",
    )
    db.add(segment)
    db.flush()
    job = ProductionJob(
        plan_id=plan.id,
        target_type="production_segment",
        target_id=segment.id,
        stage="agency_auto_repair:image_generation_failed",
        status=JOB_QUEUED,
        idempotency_key="repair:executor:image-prompt-tune",
    )
    db.add(job)
    db.flush()

    result = await execute_repair_job(db, job)

    db.refresh(segment)
    db.refresh(run)
    assert result.status == "success"
    assert segment.status == SEGMENT_IMAGE_QUEUED
    assert segment.retry_count == 1
    assert "自动返修提示" in segment.image_prompt
    queued_job = db.query(ProductionJob).filter_by(
        plan_id=plan.id,
        target_type="production_segment",
        target_id=segment.id,
        stage="image_generation",
        status=JOB_QUEUED,
    ).one()
    assert queued_job.idempotency_key == f"{run.id}:{segment.id}:agency_repair:{job.id}:image_generation"
    assert run.status == "image_batch_running"
    assert run.current_stage == "image_generation"
    assert db.query(ProductionAuditEvent).filter_by(event_type="agency_repair_prompt_tuned").count() == 1
    recheck_event = db.query(ProductionAuditEvent).filter_by(event_type="agency_repair_recheck_required").one()
    assert recheck_event.payload_json["job_id"] == job.id
    assert recheck_event.payload_json["result"]["next_gate"] == "图像审查"

    second = await execute_repair_job(db, job)

    db.refresh(segment)
    assert second.status == "success"
    assert second.data["prompt_tuned"] is False
    assert segment.retry_count == 1
    assert db.query(ProductionJob).filter_by(
        plan_id=plan.id,
        target_type="production_segment",
        target_id=segment.id,
        stage="image_generation",
        status=JOB_QUEUED,
    ).count() == 1
    assert db.query(ProductionAuditEvent).filter_by(event_type="agency_repair_prompt_tuned").count() == 1
    assert db.query(ProductionAuditEvent).filter_by(event_type="agency_repair_recheck_required").count() == 1


@pytest.mark.asyncio
async def test_storyboard_segment_repair_blocks_when_reference_payload_is_missing(db):
    series = Series(title="老李控糖", logline="控糖系列", genre="health")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1)
    db.add(episode)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready", budget_limit=5.0, current_cost=0.0)
    db.add(plan)
    db.flush()
    prod_episode = ProductionEpisode(plan_id=plan.id, episode_id=episode.id)
    db.add(prod_episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        production_plan_id=plan.id,
        production_episode_id=prod_episode.id,
        production_link_status="linked",
        status="image_human_review_required",
        current_stage="image_review",
    )
    db.add(run)
    db.flush()
    scene = ProductionScene(episode_plan_id=prod_episode.id, scene_id="scene-1", order_index=1)
    db.add(scene)
    db.flush()
    shot = ProductionShot(scene_plan_id=scene.id, shot_id="shot-1", order_index=1)
    db.add(shot)
    db.flush()
    segment = ProductionSegment(
        shot_plan_id=shot.id,
        segment_id="seg-1",
        image_prompt="原始画面提示",
        video_prompt="原始视频提示",
        status="image_review_pending",
        reference_roles_json=[],
    )
    db.add(segment)
    db.flush()
    job = ProductionJob(
        plan_id=plan.id,
        target_type="production_segment",
        target_id=segment.id,
        stage="agency_auto_repair:storyboard_missing_references",
        status=JOB_QUEUED,
        idempotency_key="repair:executor:missing-reference-payload",
    )
    db.add(job)
    db.flush()

    result = await execute_repair_job(db, job)

    assert result.status == "blocked"
    assert result.repair_route == f"/video-production/{run.id}"
    assert result.affected_ids == [segment.id]
    assert db.query(ProductionJob).filter_by(
        plan_id=plan.id,
        target_type="production_segment",
        target_id=segment.id,
        stage="image_generation",
    ).count() == 0
    assert db.query(ProductionAuditEvent).filter_by(event_type="agency_repair_manual_required").count() == 1


@pytest.mark.asyncio
async def test_storyboard_segment_repair_blocks_when_reference_urls_are_empty(db):
    series = Series(title="老李控糖", logline="控糖系列", genre="health")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1)
    db.add(episode)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready", budget_limit=5.0, current_cost=0.0)
    db.add(plan)
    db.flush()
    prod_episode = ProductionEpisode(plan_id=plan.id, episode_id=episode.id)
    db.add(prod_episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        production_plan_id=plan.id,
        production_episode_id=prod_episode.id,
        production_link_status="linked",
        status="image_human_review_required",
        current_stage="image_review",
    )
    db.add(run)
    db.flush()
    scene = ProductionScene(episode_plan_id=prod_episode.id, scene_id="scene-1", order_index=1)
    db.add(scene)
    db.flush()
    shot = ProductionShot(scene_plan_id=scene.id, shot_id="shot-1", order_index=1)
    db.add(shot)
    db.flush()
    segment = ProductionSegment(
        shot_plan_id=shot.id,
        segment_id="seg-1",
        image_prompt="原始画面提示",
        video_prompt="原始视频提示",
        status="image_review_pending",
        reference_roles_json=[{"role": "character_anchor", "url": ""}],
    )
    db.add(segment)
    db.flush()
    job = ProductionJob(
        plan_id=plan.id,
        target_type="production_segment",
        target_id=segment.id,
        stage="agency_auto_repair:storyboard_missing_references",
        status=JOB_QUEUED,
        idempotency_key="repair:executor:empty-reference-url",
    )
    db.add(job)
    db.flush()

    result = await execute_repair_job(db, job)

    assert result.status == "blocked"
    assert db.query(ProductionJob).filter_by(stage="image_generation").count() == 0


@pytest.mark.asyncio
async def test_repair_job_uses_audit_event_run_instead_of_latest_run_for_plan(db):
    series = Series(title="老李控糖", logline="控糖系列", genre="health")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1)
    db.add(episode)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready", budget_limit=5.0, current_cost=0.0)
    db.add(plan)
    db.flush()
    prod_episode = ProductionEpisode(plan_id=plan.id, episode_id=episode.id)
    db.add(prod_episode)
    db.flush()
    old_run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        production_plan_id=plan.id,
        production_episode_id=prod_episode.id,
        production_link_status="linked",
        status="image_human_review_required",
        current_stage="image_review",
        created_at=bj_now() - timedelta(minutes=5),
    )
    latest_run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        production_plan_id=plan.id,
        production_episode_id=prod_episode.id,
        production_link_status="linked",
        status="video_review_pending",
        current_stage="video_review",
        created_at=bj_now(),
    )
    db.add_all([old_run, latest_run])
    db.flush()
    scene = ProductionScene(episode_plan_id=prod_episode.id, scene_id="scene-1", order_index=1)
    db.add(scene)
    db.flush()
    shot = ProductionShot(scene_plan_id=scene.id, shot_id="shot-1", order_index=1)
    db.add(shot)
    db.flush()
    segment = ProductionSegment(
        shot_plan_id=shot.id,
        segment_id="seg-1",
        image_prompt="原始画面提示",
        video_prompt="原始视频提示",
        status="image_review_pending",
        reference_roles_json=[{"role": "character_anchor", "url": "https://cdn.test/ref.png"}],
    )
    db.add(segment)
    db.flush()
    job = ProductionJob(
        plan_id=plan.id,
        target_type="production_segment",
        target_id=segment.id,
        stage="agency_auto_repair:image_generation_failed",
        status=JOB_QUEUED,
        idempotency_key="repair:executor:old-run-binding",
    )
    db.add(job)
    db.flush()
    db.add(ProductionAuditEvent(
        event_type="agency_backtrack_triggered",
        run_id=old_run.id,
        production_plan_id=plan.id,
        production_segment_id=segment.id,
        payload_json={"job_id": job.id},
    ))
    db.flush()

    result = await execute_repair_job(db, job)

    db.refresh(old_run)
    db.refresh(latest_run)
    downstream = db.query(ProductionJob).filter_by(stage="image_generation").one()
    assert result.status == "success"
    assert old_run.status == "image_batch_running"
    assert old_run.current_stage == "image_generation"
    assert latest_run.status == "video_review_pending"
    assert downstream.idempotency_key.startswith(f"{old_run.id}:{segment.id}:")


@pytest.mark.asyncio
async def test_repair_job_uses_debate_event_job_ids_to_bind_run(db):
    series = Series(title="老李控糖", logline="控糖系列", genre="health")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1)
    db.add(episode)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready", budget_limit=5.0, current_cost=0.0)
    db.add(plan)
    db.flush()
    prod_episode = ProductionEpisode(plan_id=plan.id, episode_id=episode.id)
    db.add(prod_episode)
    db.flush()
    old_run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        production_plan_id=plan.id,
        production_episode_id=prod_episode.id,
        production_link_status="linked",
        status="image_human_review_required",
        current_stage="image_review",
        created_at=bj_now() - timedelta(minutes=5),
    )
    latest_run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        production_plan_id=plan.id,
        production_episode_id=prod_episode.id,
        production_link_status="linked",
        status="video_review_pending",
        current_stage="video_review",
        created_at=bj_now(),
    )
    db.add_all([old_run, latest_run])
    db.flush()
    scene = ProductionScene(episode_plan_id=prod_episode.id, scene_id="scene-1", order_index=1)
    db.add(scene)
    db.flush()
    shot = ProductionShot(scene_plan_id=scene.id, shot_id="shot-1", order_index=1)
    db.add(shot)
    db.flush()
    segment = ProductionSegment(
        shot_plan_id=shot.id,
        segment_id="seg-1",
        image_prompt="原始画面提示",
        video_prompt="原始视频提示",
        status="image_review_pending",
        reference_roles_json=[{"role": "character_anchor", "url": "https://cdn.test/ref.png"}],
    )
    db.add(segment)
    db.flush()
    job = ProductionJob(
        plan_id=plan.id,
        target_type="production_segment",
        target_id=segment.id,
        stage="agency_auto_repair:video_segment_failed",
        status=JOB_QUEUED,
        idempotency_key="repair:executor:debate-job-ids",
    )
    db.add(job)
    db.flush()
    db.add(ProductionAuditEvent(
        event_type="agency_debate_repair_intent",
        run_id=old_run.id,
        production_plan_id=plan.id,
        production_segment_id=segment.id,
        payload_json={"job_ids": [job.id]},
    ))
    db.flush()

    result = await execute_repair_job(db, job)

    db.refresh(old_run)
    db.refresh(latest_run)
    downstream = db.query(ProductionJob).filter_by(stage="image_generation").one()
    assert result.status == "success"
    assert old_run.status == "image_batch_running"
    assert latest_run.status == "video_review_pending"
    assert downstream.idempotency_key.startswith(f"{old_run.id}:{segment.id}:")


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

import pytest

from app.config import bj_now
from app.db_models import (
    AgencyCreativePatch,
    Episode,
    ProductionEpisode,
    ProductionJob,
    ProductionPlan,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    Series,
    VideoProductionRun,
)
from app.services.production_errors import ProductionErrorCode
from app.services.video_production_run_types import REAL_SHORT_E2E
from app.services.video_production_service import VideoProductionError, start_image_stage


def _storyboard_run(db, *, patch_status="proposed"):
    series = Series(title="Creative Gate", logline="Test", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        storyboard_json={"frames": [{"frame_id": "shot-001", "image_prompt": "Prompt", "duration": 5}]},
    )
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="storyboard_ready",
        current_stage="storyboard_ready",
        storyboard_json=episode.storyboard_json,
    )
    db.add(run)
    db.flush()
    patch = AgencyCreativePatch(
        series_id=series.id,
        episode_id=episode.id,
        run_id=run.id,
        stage="image_stage",
        expert_id="prompt_engineer",
        patch_type="storyboard_patch",
        target_type="storyboard_frame",
        target_id="shot-001",
        title="Improve image prompt",
        reason="The hook needs approval before image generation.",
        before_json={"image_prompt": "Prompt"},
        after_json={"image_prompt": "Improved prompt"},
        status=patch_status,
        priority="high",
    )
    db.add(patch)
    db.commit()
    return run


@pytest.mark.asyncio
async def test_start_image_stage_blocks_pending_creative_patch(db):
    run = _storyboard_run(db)

    with pytest.raises(VideoProductionError, match="Creative patches"):
        await start_image_stage(db, run.id)

    db.refresh(run)
    assert run.status == "creative_review_required"
    assert run.current_stage == "creative_review"
    assert run.pixelle_stage_task_id is None


@pytest.mark.asyncio
async def test_applied_creative_patch_does_not_block_image_stage(db, monkeypatch):
    run = _storyboard_run(db, patch_status="applied")

    async def agency_pass(*args, **kwargs):
        return {"stage_status": "passed", "invocation_ids": [], "invocations": []}

    monkeypatch.setattr("app.services.video_production_service._guard_provider_stage", agency_pass)

    with pytest.raises(VideoProductionError, match="image_generation"):
        await start_image_stage(db, run.id)

    db.refresh(run)
    assert run.current_stage == "image_review"


def _linked_run_with_worker_job(db):
    series = Series(title="Worker Creative Gate", logline="Test", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready", active_version=1, budget_limit=5.0)
    db.add(plan)
    db.flush()
    production_episode = ProductionEpisode(plan_id=plan.id, episode_id=episode.id, order_index=1, status="ready")
    db.add(production_episode)
    db.flush()
    scene = ProductionScene(episode_plan_id=production_episode.id, scene_id="scene-1", order_index=1, status="ready")
    db.add(scene)
    db.flush()
    shot = ProductionShot(scene_plan_id=scene.id, shot_id="shot-1", order_index=1, status="ready", duration_seconds=6)
    db.add(shot)
    db.flush()
    segment = ProductionSegment(
        shot_plan_id=shot.id,
        segment_id="shot-1-seg-01",
        order_index=1,
        status="planned",
        duration_seconds=6,
        image_prompt="neon courier",
        video_prompt="slow push",
        reference_roles_json=[{"role": "character_anchor", "url": "https://cdn.test/character.png", "priority": 1}],
    )
    db.add(segment)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        run_type=REAL_SHORT_E2E,
        production_plan_id=plan.id,
        production_episode_id=production_episode.id,
        production_link_status="linked",
        status="image_batch_running",
        current_stage="image_generation",
    )
    db.add(run)
    db.flush()
    db.add(ProductionJob(
        plan_id=plan.id,
        target_type="production_segment",
        target_id=segment.id,
        stage="image_generation",
        status="queued",
        idempotency_key=f"{run.id}:{segment.id}:image_generation:v1",
        scheduled_at=bj_now(),
    ))
    patch = AgencyCreativePatch(
        series_id=series.id,
        episode_id=episode.id,
        run_id=run.id,
        production_plan_id=plan.id,
        production_episode_id=production_episode.id,
        production_segment_id=segment.id,
        stage="image_stage",
        expert_id="prompt_engineer",
        patch_type="image_prompt_patch",
        target_type="production_segment",
        target_id=segment.id,
        title="Improve segment prompt",
        reason="Needs approval before paid provider submission.",
        before_json={"image_prompt": "neon courier"},
        after_json={"image_prompt": "neon courier with visible conflict"},
        status="proposed",
        priority="high",
    )
    db.add(patch)
    db.commit()
    return run, segment, patch


def test_real_worker_step_blocks_pending_creative_patch_before_provider(db, monkeypatch):
    from app.services.production_worker_service import run_real_worker_step

    run, _segment, patch = _linked_run_with_worker_job(db)

    def fake_config(db, scene_key):
        return {
            "provider": "pixelle",
            "model": scene_key,
            "config": {
                "real_paid_allowed": True,
                "supports_external_task_id": True,
                "supports_task_query": True,
                "returns_asset_url": True,
                "returns_usage": True,
                "estimated_cost": 0.01,
                "max_concurrent_tasks": 1,
            },
        }

    async def fail_submit_image_batch(*args, **kwargs):
        raise AssertionError("worker submitted a provider task while creative patches are pending")

    monkeypatch.setattr("app.services.production_worker_service.resolve_runtime_model_config", fake_config)
    monkeypatch.setattr("app.services.video_production_service.submit_image_batch", fail_submit_image_batch)

    result = run_real_worker_step(db, run.id, lease_id="creative-gate-worker", batch_size=1)

    assert result["processed"] == 1
    assert result["items"][0]["ok"] is False
    assert result["items"][0]["error_code"] == ProductionErrorCode.REVIEW_GATE_BLOCKED.value
    assert patch.id in result["items"][0]["repair"]["affected_ids"]
    assert result["items"][0]["repair"]["repair_route"].endswith("?tab=workbench")

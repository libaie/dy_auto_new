import pytest

from app.db_models import (
    Episode,
    GeneratedVideo,
    ProductionAuditEvent,
    ProductionEpisode,
    ProductionPlan,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    Series,
    VideoProductionAsset,
    VideoProductionRun,
)
from app.services.production_errors import ProductionErrorCode, ProductionRepairableError
from app.services.video_production_service import approve_asset
from app.services.video_production_service import start_compose_stage, start_video_stage


def _linked_run_with_segments(db, statuses, *, asset_type="image"):
    series = Series(title="Gate", logline="Gate", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="running", budget_limit=10, target_total_duration_seconds=60)
    db.add(plan)
    db.flush()
    production_episode = ProductionEpisode(
        plan_id=plan.id,
        episode_id=episode.id,
        order_index=1,
        status="ready",
        target_duration_seconds=60,
    )
    db.add(production_episode)
    db.flush()
    scene = ProductionScene(episode_plan_id=production_episode.id, scene_id="scene-1", order_index=1, status="ready")
    db.add(scene)
    db.flush()
    shot = ProductionShot(scene_plan_id=scene.id, shot_id="shot-1", order_index=1, status="ready", action="walk", duration_seconds=15)
    db.add(shot)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="image_review_pending",
        current_stage="image_review",
        run_type="real_short_e2e",
        production_plan_id=plan.id,
        production_episode_id=production_episode.id,
        production_link_status="linked",
    )
    db.add(run)
    db.flush()
    segments = []
    for index, status in enumerate(statuses, start=1):
        segment = ProductionSegment(
            shot_plan_id=shot.id,
            segment_id=f"seg-{index}",
            order_index=index,
            status="image_review_pending",
            duration_seconds=5,
        )
        db.add(segment)
        db.flush()
        db.add(
            VideoProductionAsset(
                run_id=run.id,
                episode_id=episode.id,
                frame_id=segment.id,
                asset_type=asset_type,
                stage=f"{asset_type}_generation",
                status=status,
                is_latest=True,
                copy_status="persisted",
                checksum=f"checksum-{index}",
                storage_path=f"output/{segment.id}",
                production_segment_id=segment.id,
                target_type="production_segment",
                target_id=segment.id,
            )
        )
        segments.append(segment)
    db.commit()
    return run, episode, segments


def _storyboard_run(db):
    series = Series(title="Storyboard Gate", logline="Gate", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={"frames": [{"frame_id": "frame-001", "duration": 5}]},
    )
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="final_review_pending",
        current_stage="final_review",
        storyboard_json=episode.storyboard_json,
    )
    db.add(run)
    db.commit()
    return run, episode


def _storyboard_run_with_asset(db, *, asset_type, asset_status="approved", copy_status="registered"):
    series = Series(title="Stage Gate", logline="Gate", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={
            "frames": [{
                "frame_id": "frame-001",
                "image_prompt": "Image prompt",
                "video_prompt": "Video prompt",
                "narration": "Narration",
                "duration": 5,
            }]
        },
    )
    db.add(episode)
    db.flush()
    if asset_type == "image":
        status = "image_approved"
        current_stage = "image_review"
        stage = "image_generation"
        url = "https://cdn.test/image.png"
        storage_path = "output/image.png"
    else:
        status = "video_segments_approved"
        current_stage = "video_review"
        stage = "video_rendering"
        url = "https://cdn.test/segment.mp4"
        storage_path = "output/segment.mp4"
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status=status,
        current_stage=current_stage,
        storyboard_json=episode.storyboard_json,
    )
    db.add(run)
    db.flush()
    db.add(
        VideoProductionAsset(
            run_id=run.id,
            episode_id=episode.id,
            frame_id="frame-001",
            asset_type=asset_type,
            stage=stage,
            url=url,
            duration_seconds=5,
            version=1,
            status=asset_status,
            is_latest=True,
            copy_status=copy_status,
            checksum="checksum" if copy_status == "persisted" else None,
            storage_path=storage_path if copy_status == "persisted" else None,
        )
    )
    db.commit()
    return run, episode


def _final_asset(db, run, episode, *, status="review_pending", copy_status="persisted", checksum="sum", storage_path="output/final.mp4", is_latest=True):
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="final",
        asset_type="final_video",
        stage="composition",
        url="https://cdn.test/final.mp4",
        local_path="output/final.mp4",
        duration_seconds=5,
        version=1,
        status=status,
        is_latest=is_latest,
        copy_status=copy_status,
        checksum=checksum,
        storage_path=storage_path,
    )
    db.add(asset)
    db.commit()
    return asset


def test_gate_blocks_partial_image_approval(db):
    from app.services.production_gate_evaluator import evaluate_stage_gate

    run, _episode, segments = _linked_run_with_segments(db, ["approved", "storage_failed"])

    result = evaluate_stage_gate(db, run.id, stage="image_generation")

    assert result["ready"] is False
    assert result["status"] == "blocked"
    assert result["stage"] == "image_generation"
    assert result["asset_type"] == "image"
    assert result["required_count"] == 2
    assert result["approved_count"] == 1
    assert result["blocked_segment_ids"] == [segments[1].id]
    assert result["blocked_details"][0]["required_id"] == segments[1].id
    assert db.query(ProductionAuditEvent).filter_by(run_id=run.id, event_type="gate.evaluated").count() == 1


def test_gate_allows_next_stage_only_when_all_required_assets_approved(db):
    from app.services.production_gate_evaluator import evaluate_stage_gate

    run, _episode, _segments = _linked_run_with_segments(db, ["approved", "approved"])

    result = evaluate_stage_gate(db, run.id, stage="image_generation")

    assert result["ready"] is True
    assert result["status"] == "ready"
    assert result["required_count"] == 2
    assert result["approved_count"] == 2
    assert result["blocked_segment_ids"] == []
    assert result["blocked_details"] == []


def test_video_gate_requires_persisted_approved_latest_assets(db):
    from app.services.production_gate_evaluator import evaluate_stage_gate

    run, episode, segments = _linked_run_with_segments(db, ["approved"], asset_type="video_segment")
    latest = (
        db.query(VideoProductionAsset)
        .filter_by(run_id=run.id, production_segment_id=segments[0].id, asset_type="video_segment")
        .one()
    )
    latest.copy_status = "registered"
    db.add(
        VideoProductionAsset(
            run_id=run.id,
            episode_id=episode.id,
            frame_id=segments[0].id,
            asset_type="video_segment",
            stage="video_generation",
            status="approved",
            version=0,
            is_latest=False,
            copy_status="persisted",
            checksum="old-sum",
            storage_path="output/old.mp4",
            production_segment_id=segments[0].id,
            target_type="production_segment",
            target_id=segments[0].id,
        )
    )
    db.commit()

    result = evaluate_stage_gate(db, run.id, stage="video_generation")

    assert result["ready"] is False
    assert result["asset_type"] == "video_segment"
    assert result["approved_count"] == 0
    assert result["blocked_segment_ids"] == [segments[0].id]
    assert result["blocked_details"][0]["reason"] == "asset_not_persisted"


def test_final_writeback_blocked_until_final_asset_is_approved_persisted_and_latest(db):
    run, episode = _storyboard_run(db)
    asset = _final_asset(db, run, episode, copy_status="registered", checksum=None, storage_path=None)

    with pytest.raises(ProductionRepairableError) as exc_info:
        approve_asset(db, asset.id, reviewer_user_id="reviewer-1", comment="approve")

    assert exc_info.value.code == ProductionErrorCode.ASSET_STORAGE_FAILED
    db.refresh(run)
    db.refresh(episode)
    db.refresh(asset)
    assert run.status == "final_review_pending"
    assert episode.video_url is None
    assert asset.status == "review_pending"
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run.id).count() == 0


def test_final_gate_ready_after_human_approval(db):
    from app.services.production_gate_evaluator import evaluate_stage_gate

    run, episode = _storyboard_run(db)
    asset = _final_asset(db, run, episode)

    approve_asset(db, asset.id, reviewer_user_id="reviewer-1", comment="approve")

    result = evaluate_stage_gate(db, run.id, stage="episode_compose")

    assert result["ready"] is True
    assert result["asset_type"] == "final_video"
    assert result["required_count"] == 1
    assert result["approved_count"] == 1


def test_approval_does_not_leave_run_advanced_when_sibling_latest_asset_is_not_persisted(db):
    from app.services.production_gate_evaluator import evaluate_stage_gate

    run, _episode, segments = _linked_run_with_segments(db, ["review_pending", "approved"])
    non_persisted = (
        db.query(VideoProductionAsset)
        .filter_by(run_id=run.id, production_segment_id=segments[1].id, asset_type="image")
        .one()
    )
    non_persisted.copy_status = "registered"
    non_persisted.checksum = None
    non_persisted.storage_path = None
    db.commit()
    review_asset = (
        db.query(VideoProductionAsset)
        .filter_by(run_id=run.id, production_segment_id=segments[0].id, asset_type="image")
        .one()
    )

    approve_asset(db, review_asset.id, reviewer_user_id="reviewer-1", comment="ok")

    db.refresh(run)
    result = evaluate_stage_gate(db, run.id, stage="image_generation")
    assert result["ready"] is False
    assert result["blocked_segment_ids"] == [segments[1].id]
    assert run.status != "image_approved"
    assert run.status == "image_review_pending"
    assert run.current_stage == "image_review"


@pytest.mark.asyncio
async def test_start_video_stage_blocks_non_persisted_approved_image_without_submit(db, monkeypatch):
    run, _episode = _storyboard_run_with_asset(db, asset_type="image", copy_status="registered")
    calls = []

    async def agency_pass(*args, **kwargs):
        return {"stage_status": "passed"}

    async def fake_submit_video_batch(*args, **kwargs):
        calls.append(kwargs)
        raise AssertionError("video provider submit should not be called")

    monkeypatch.setattr("app.services.video_production_service._guard_provider_stage", agency_pass)
    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", lambda db, scene: {"provider": "mock", "scene_key": scene})
    monkeypatch.setattr("app.services.video_production_service.submit_video_batch", fake_submit_video_batch)

    with pytest.raises(ProductionRepairableError) as exc_info:
        await start_video_stage(db, run.id)

    assert exc_info.value.code == ProductionErrorCode.REVIEW_GATE_BLOCKED
    assert calls == []


@pytest.mark.asyncio
async def test_start_compose_stage_blocks_non_persisted_approved_video_without_submit(db, monkeypatch):
    run, _episode = _storyboard_run_with_asset(db, asset_type="video_segment", copy_status="registered")
    calls = []

    async def agency_pass(*args, **kwargs):
        return {"stage_status": "passed"}

    async def fake_submit_compose(*args, **kwargs):
        calls.append(kwargs)
        raise AssertionError("compose provider submit should not be called")

    monkeypatch.setattr("app.services.video_production_service._guard_provider_stage", agency_pass)
    monkeypatch.setattr("app.services.video_production_service.compose_model_config", lambda db: {"provider": "mock", "scene_key": "video_composition"})
    monkeypatch.setattr("app.services.video_production_service.submit_compose", fake_submit_compose)

    with pytest.raises(ProductionRepairableError) as exc_info:
        await start_compose_stage(db, run.id)

    assert exc_info.value.code == ProductionErrorCode.REVIEW_GATE_BLOCKED
    assert calls == []

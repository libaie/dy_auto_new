import pytest
from app.db_models import (
    Episode,
    ProductionAuditEvent,
    ProductionEpisode,
    ProductionPlan,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    Series,
    VideoProductionAsset,
    VideoProductionRun,
    VideoReviewRecord,
)
from app.services.video_production_service import VideoProductionError, start_asset_regeneration, sync_regenerated_asset
from app.services.video_production_run_types import REAL_SHORT_E2E


def _asset_run(db, asset_type="image", frame_id="frame-001"):
    series = Series(title="Regen", logline="Test", genre="drama", target_duration=60)
    db.add(series); db.flush()
    episode = Episode(series_id=series.id, episode_number=1, storyboard_json={"frames": [
        {"frame_id": "frame-001", "image_prompt": "new image 1", "video_prompt": "new video 1", "duration": 5},
        {"frame_id": "frame-002", "image_prompt": "new image 2", "video_prompt": "new video 2", "duration": 6},
    ]})
    db.add(episode); db.flush()
    run_status = "image_human_review_required" if asset_type == "image" else "video_human_review_required"
    run_stage = "image_review" if asset_type == "image" else "video_review"
    run = VideoProductionRun(series_id=series.id, episode_id=episode.id, status=run_status, current_stage=run_stage, storyboard_json=episode.storyboard_json)
    db.add(run); db.flush()
    asset = VideoProductionAsset(run_id=run.id, episode_id=episode.id, frame_id=frame_id, asset_type=asset_type, stage="image_generation" if asset_type == "image" else "video_rendering", url="https://cdn.test/old.png", version=1, status="rejected")
    db.add(asset)
    if asset_type == "video_segment":
        for image_frame_id in ("frame-001", "frame-002"):
            db.add(VideoProductionAsset(
                run_id=run.id,
                episode_id=episode.id,
                frame_id=image_frame_id,
                asset_type="image",
                stage="image_generation",
                url=f"https://cdn.test/{image_frame_id}.png",
                version=1,
                status="approved",
                copy_status="persisted",
                checksum=f"sha256-{image_frame_id}",
                storage_path=f"output/{image_frame_id}.png",
            ))
    db.commit()
    return run, asset


def _linked_asset_run(db, asset_type="image"):
    series = Series(title="Linked Regen", logline="Test", genre="drama", target_duration=60)
    db.add(series); db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode); db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready", active_version=1)
    db.add(plan); db.flush()
    production_episode = ProductionEpisode(plan_id=plan.id, episode_id=episode.id, order_index=1, status="ready")
    db.add(production_episode); db.flush()
    scene = ProductionScene(episode_plan_id=production_episode.id, scene_id="scene-1", order_index=1, status="ready")
    db.add(scene); db.flush()
    shot = ProductionShot(scene_plan_id=scene.id, shot_id="shot-1", order_index=1, status="ready", duration_seconds=7)
    db.add(shot); db.flush()
    segment = ProductionSegment(
        shot_plan_id=shot.id,
        segment_id="shot-1-seg-01",
        order_index=1,
        status="planned",
        duration_seconds=7,
        continuity_mode="narrative_cut",
        version=3,
        expected_end_state="same pose",
        image_prompt="linked image prompt",
        video_prompt="linked video prompt",
        reference_roles_json=[{"role": "character_anchor", "url": "https://cdn.test/ref.png"}],
    )
    db.add(segment); db.flush()
    run_status = "image_human_review_required" if asset_type == "image" else "video_human_review_required"
    run_stage = "image_review" if asset_type == "image" else "video_review"
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        production_plan_id=plan.id,
        production_episode_id=production_episode.id,
        production_link_status="linked",
        status=run_status,
        current_stage=run_stage,
    )
    db.add(run); db.flush()
    if asset_type == "video_segment":
        db.add(VideoProductionAsset(
            run_id=run.id,
            episode_id=episode.id,
            frame_id=segment.id,
            asset_type="image",
            stage="image_generation",
            url="https://cdn.test/approved-image.png",
            version=1,
            status="approved",
            production_segment_id=segment.id,
            target_type="production_segment",
            target_id=segment.id,
            source_version=segment.version,
            is_latest=True,
            copy_status="persisted",
            checksum="sha256-approved-image",
            storage_path="output/approved-image.png",
        ))
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id=segment.id,
        asset_type=asset_type,
        stage="image_generation" if asset_type == "image" else "video_rendering",
        url="https://cdn.test/old.png",
        version=1,
        status="rejected",
        pixelle_task_id="old-task",
        provider_task_id="old-provider-task",
        production_segment_id=segment.id,
        target_type="production_segment",
        target_id=segment.id,
        source_version=segment.version,
        is_latest=True,
    )
    db.add(asset)
    db.commit()
    return run, segment, asset


@pytest.mark.asyncio
async def test_start_video_segment_regeneration_uses_selected_frame(db, monkeypatch):
    _run, asset = _asset_run(db, "video_segment", frame_id="frame-002")
    calls = []

    async def fake_submit_video_batch(db, run_id, frames, model_config, template_config=None):
        calls.append(frames)
        return {"ok": True, "stage_task_id": "regen-video-task"}

    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", lambda db, scene: {"provider": "mock", "scene_key": scene})
    monkeypatch.setattr("app.services.video_production_service.submit_video_batch", fake_submit_video_batch)

    updated = await start_asset_regeneration(db, asset.id)
    assert updated.status == "regenerating"
    assert updated.pixelle_task_id == "regen-video-task"
    assert calls[0][0]["frame_id"] == "frame-002"
    assert calls[0][0]["duration"] == 6


@pytest.mark.asyncio
async def test_start_image_regeneration_marks_old_asset_regenerating(db, monkeypatch):
    _run, asset = _asset_run(db, "image")

    async def fake_submit_image_batch(db, run_id, episode_id, frames, model_config, template_config=None):
        return {"ok": True, "stage_task_id": "regen-image-task"}

    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", lambda db, scene: {"provider": "mock", "scene_key": scene})
    monkeypatch.setattr("app.services.video_production_service.submit_image_batch", fake_submit_image_batch)

    updated = await start_asset_regeneration(db, asset.id)
    assert updated.status == "regenerating"
    assert updated.pixelle_task_id == "regen-image-task"


@pytest.mark.asyncio
async def test_real_short_regeneration_blocks_direct_provider_submit(db, monkeypatch):
    run, asset = _asset_run(db, "image")
    run.run_type = REAL_SHORT_E2E
    run.production_plan_id = "plan-real-short"
    db.commit()

    async def fail_submit_image_batch(*args, **kwargs):
        raise AssertionError("real_short_e2e regeneration must not direct-submit provider work")

    monkeypatch.setattr("app.services.video_production_service.submit_image_batch", fail_submit_image_batch)

    with pytest.raises(VideoProductionError, match="worker/executor"):
        await start_asset_regeneration(db, asset.id)


@pytest.mark.asyncio
async def test_linked_image_regeneration_uses_segment_frame_and_preserves_target_version(db, monkeypatch):
    _run, segment, asset = _linked_asset_run(db, "image")
    calls = []

    async def fake_submit_image_batch(db, run_id, episode_id, frames, model_config, template_config=None):
        calls.append(frames)
        return {"ok": True, "stage_task_id": "regen-linked-image-task"}

    async def fake_get_stage_task(db, stage_task_id):
        return {"ok": True, "status": "completed", "assets": [{
            "frame_id": segment.id,
            "asset_type": "image",
            "url": "https://cdn.test/new-linked-image.png",
            "storage_path": "output/new-linked-image.png",
            "checksum": "sha256-new-linked-image",
            "copy_status": "persisted",
            "provider_task_id": "new-provider-image-task",
            "metadata": {},
        }]}

    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", lambda db, scene: {"provider": "mock", "scene_key": scene})
    monkeypatch.setattr("app.services.video_production_service.submit_image_batch", fake_submit_image_batch)
    monkeypatch.setattr("app.services.video_production_service.get_stage_task", fake_get_stage_task)

    updated = await start_asset_regeneration(db, asset.id)
    assert updated.pixelle_task_id == "regen-linked-image-task"
    assert calls[0][0]["frame_id"] == segment.id
    assert calls[0][0]["production_segment_id"] == segment.id
    assert calls[0][0]["image_prompt"] == "linked image prompt"

    new_asset = await sync_regenerated_asset(db, asset.id)
    db.refresh(asset)
    assert asset.is_latest is False
    assert new_asset.version == 2
    assert new_asset.is_latest is True
    assert new_asset.production_segment_id == segment.id
    assert new_asset.target_type == "production_segment"
    assert new_asset.target_id == segment.id
    assert new_asset.source_version == segment.version
    assert new_asset.provider_task_id == "new-provider-image-task"
    assert new_asset.pixelle_task_id == "regen-linked-image-task"


@pytest.mark.asyncio
async def test_linked_video_regeneration_uses_segment_frame_and_preserves_target_version(db, monkeypatch):
    _run, segment, asset = _linked_asset_run(db, "video_segment")
    calls = []

    async def fake_submit_video_batch(db, run_id, frames, model_config, template_config=None):
        calls.append(frames)
        return {"ok": True, "stage_task_id": "regen-linked-video-task"}

    async def fake_get_stage_task(db, stage_task_id):
        return {"ok": True, "status": "completed", "assets": [{
            "frame_id": segment.id,
            "asset_type": "video_segment",
            "url": "https://cdn.test/new-linked-video.mp4",
            "storage_path": "output/new-linked-video.mp4",
            "checksum": "sha256-new-linked-video",
            "copy_status": "persisted",
            "provider_task_id": "new-provider-video-task",
            "metadata": {"duration": 7},
        }]}

    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", lambda db, scene: {"provider": "mock", "scene_key": scene})
    monkeypatch.setattr("app.services.video_production_service.submit_video_batch", fake_submit_video_batch)
    monkeypatch.setattr("app.services.video_production_service.get_stage_task", fake_get_stage_task)

    updated = await start_asset_regeneration(db, asset.id)
    assert updated.pixelle_task_id == "regen-linked-video-task"
    assert calls[0][0]["frame_id"] == segment.id
    assert calls[0][0]["production_segment_id"] == segment.id
    assert calls[0][0]["video_prompt"] == "linked video prompt"
    assert calls[0][0]["approved_image_url"] == "https://cdn.test/approved-image.png"

    new_asset = await sync_regenerated_asset(db, asset.id)
    db.refresh(asset)
    assert asset.is_latest is False
    assert new_asset.version == 2
    assert new_asset.is_latest is True
    assert new_asset.production_segment_id == segment.id
    assert new_asset.target_type == "production_segment"
    assert new_asset.target_id == segment.id
    assert new_asset.source_version == segment.version
    assert new_asset.provider_task_id == "new-provider-video-task"
    assert new_asset.pixelle_task_id == "regen-linked-video-task"


@pytest.mark.asyncio
async def test_start_image_regeneration_blocks_when_provider_model_config_missing(db, monkeypatch):
    run, asset = _asset_run(db, "image")
    asset.status = "review_pending"
    db.commit()

    async def fail_submit_image_batch(*args, **kwargs):
        raise AssertionError("image provider should not submit without runtime config")

    monkeypatch.setattr("app.services.video_production_service.submit_image_batch", fail_submit_image_batch)

    with pytest.raises(VideoProductionError, match="image_generation"):
        await start_asset_regeneration(db, asset.id)

    db.refresh(run)
    db.refresh(asset)
    assert run.status == "image_human_review_required"
    assert run.current_stage == "image_review"
    assert asset.status == "rejected"
    assert asset.pixelle_task_id is None
    assert asset.metadata_json["regeneration_error"]["error_code"] == "PROVIDER_MODEL_CONFIG_MISSING"
    error = run.model_trace_json["provider_model_config_errors"][f"regeneration:{asset.id}"]
    assert error["scene_key"] == "image_generation"
    assert error["error_code"] == "PROVIDER_MODEL_CONFIG_MISSING"
    saved_event = db.query(ProductionAuditEvent).filter_by(
        run_id=run.id,
        event_type="provider_config.image_stage.blocked",
    ).one()
    assert saved_event.payload_json["asset_id"] == asset.id
    assert saved_event.payload_json["scene_key"] == "image_generation"
    assert saved_event.payload_json["error_code"] == "PROVIDER_MODEL_CONFIG_MISSING"


@pytest.mark.asyncio
async def test_start_video_regeneration_blocks_when_provider_model_config_missing(db, monkeypatch):
    run, asset = _asset_run(db, "video_segment", frame_id="frame-002")
    asset.status = "review_pending"
    db.commit()

    async def fail_submit_video_batch(*args, **kwargs):
        raise AssertionError("video provider should not submit without runtime config")

    monkeypatch.setattr("app.services.video_production_service.submit_video_batch", fail_submit_video_batch)

    with pytest.raises(VideoProductionError, match="video_rendering"):
        await start_asset_regeneration(db, asset.id)

    db.refresh(run)
    db.refresh(asset)
    assert run.status == "video_human_review_required"
    assert run.current_stage == "video_review"
    assert asset.status == "rejected"
    assert asset.pixelle_task_id is None
    assert asset.metadata_json["regeneration_error"]["error_code"] == "PROVIDER_MODEL_CONFIG_MISSING"
    error = run.model_trace_json["provider_model_config_errors"][f"regeneration:{asset.id}"]
    assert error["scene_key"] == "video_rendering"
    assert error["error_code"] == "PROVIDER_MODEL_CONFIG_MISSING"
    saved_event = db.query(ProductionAuditEvent).filter_by(
        run_id=run.id,
        event_type="provider_config.video_stage.blocked",
    ).one()
    assert saved_event.payload_json["asset_id"] == asset.id
    assert saved_event.payload_json["scene_key"] == "video_rendering"
    assert saved_event.payload_json["error_code"] == "PROVIDER_MODEL_CONFIG_MISSING"


@pytest.mark.asyncio
async def test_sync_regenerated_asset_creates_next_version(db, monkeypatch):
    _run, asset = _asset_run(db, "image")
    asset.status = "regenerating"; asset.pixelle_task_id = "regen-image-task"; db.commit()

    async def fake_get_stage_task(db, stage_task_id):
        return {"ok": True, "status": "completed", "assets": [{
            "frame_id": "frame-001",
            "asset_type": "image",
            "url": "https://cdn.test/new.png",
            "storage_path": "output/new.png",
            "checksum": "sha256-new",
            "copy_status": "persisted",
            "metadata": {},
        }]}

    monkeypatch.setattr("app.services.video_production_service.get_stage_task", fake_get_stage_task)
    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", lambda db, scene: {})

    new_asset = await sync_regenerated_asset(db, asset.id)
    assert new_asset.version == 2
    assert new_asset.status == "review_pending"
    assert new_asset.url == "https://cdn.test/new.png"
    assert db.query(VideoReviewRecord).filter_by(asset_id=new_asset.id, review_type="ai").count() == 1


@pytest.mark.asyncio
async def test_sync_regenerated_video_segment_creates_ai_review(db, monkeypatch):
    _run, asset = _asset_run(db, "video_segment", frame_id="frame-002")
    asset.status = "regenerating"; asset.pixelle_task_id = "regen-video-task"; db.commit()

    async def fake_get_stage_task(db, stage_task_id):
        return {"ok": True, "status": "completed", "assets": [{
            "frame_id": "frame-002",
            "asset_type": "video_segment",
            "url": "https://cdn.test/new.mp4",
            "storage_path": "output/new.mp4",
            "checksum": "sha256-new-video",
            "copy_status": "persisted",
            "metadata": {"duration": 6},
        }]}

    monkeypatch.setattr("app.services.video_production_service.get_stage_task", fake_get_stage_task)
    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", lambda db, scene: {})

    new_asset = await sync_regenerated_asset(db, asset.id)
    assert new_asset.asset_type == "video_segment"
    assert new_asset.version == 2
    assert db.query(VideoReviewRecord).filter_by(asset_id=new_asset.id, review_type="ai").count() == 1

import pytest
from app.db_models import Episode, Series, VideoProductionAsset, VideoProductionRun, VideoReviewRecord
from app.services.video_production_service import start_asset_regeneration, sync_regenerated_asset


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
            db.add(VideoProductionAsset(run_id=run.id, episode_id=episode.id, frame_id=image_frame_id, asset_type="image", stage="image_generation", url=f"https://cdn.test/{image_frame_id}.png", version=1, status="approved"))
    db.commit()
    return run, asset


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
async def test_sync_regenerated_asset_creates_next_version(db, monkeypatch):
    _run, asset = _asset_run(db, "image")
    asset.status = "regenerating"; asset.pixelle_task_id = "regen-image-task"; db.commit()

    async def fake_get_stage_task(db, stage_task_id):
        return {"ok": True, "status": "completed", "assets": [{"frame_id": "frame-001", "asset_type": "image", "url": "https://cdn.test/new.png", "metadata": {}}]}

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
        return {"ok": True, "status": "completed", "assets": [{"frame_id": "frame-002", "asset_type": "video_segment", "url": "https://cdn.test/new.mp4", "metadata": {"duration": 6}}]}

    monkeypatch.setattr("app.services.video_production_service.get_stage_task", fake_get_stage_task)
    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", lambda db, scene: {})

    new_asset = await sync_regenerated_asset(db, asset.id)
    assert new_asset.asset_type == "video_segment"
    assert new_asset.version == 2
    assert db.query(VideoReviewRecord).filter_by(asset_id=new_asset.id, review_type="ai").count() == 1

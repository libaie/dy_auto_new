import pytest
from app.db_models import Episode, Series, VideoProductionAsset, VideoProductionRun, VideoReviewRecord
from app.services.video_production_service import start_video_stage, sync_video_stage_results


def _run_with_approved_images(db):
    series = Series(title="Video Stage", logline="Test", genre="drama", target_duration=60)
    db.add(series); db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot", storyboard_json={
        "frames": [{"frame_id": "frame-001", "image_prompt": "IP", "video_prompt": "VP", "narration": "N", "duration": 5, "audio_mode": "tts"}]
    })
    db.add(episode); db.flush()
    run = VideoProductionRun(series_id=series.id, episode_id=episode.id, status="image_approved", current_stage="image_review", storyboard_json=episode.storyboard_json)
    db.add(run); db.flush()
    db.add(VideoProductionAsset(run_id=run.id, episode_id=episode.id, frame_id="frame-001", asset_type="image", stage="image_generation", url="https://cdn.test/image.png", version=1, status="approved"))
    db.commit()
    return run


@pytest.mark.asyncio
async def test_start_video_stage_submits_approved_images(db, monkeypatch):
    run = _run_with_approved_images(db)
    calls = []

    async def fake_submit_video_batch(db, run_id, frames, model_config, template_config=None):
        calls.append({"run_id": run_id, "frames": frames, "model_config": model_config})
        return {"ok": True, "stage_task_id": "video-task-1"}

    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", lambda db, scene: {"provider": "mock", "scene_key": scene})
    monkeypatch.setattr("app.services.video_production_service.submit_video_batch", fake_submit_video_batch)

    updated = await start_video_stage(db, run.id)
    assert updated.status == "video_batch_running"
    assert updated.pixelle_stage_task_id == "video-task-1"
    assert calls[0]["frames"][0]["approved_image_url"] == "https://cdn.test/image.png"


@pytest.mark.asyncio
async def test_sync_video_stage_saves_segments_and_ai_review(db, monkeypatch):
    run = _run_with_approved_images(db)
    run.pixelle_stage_task_id = "video-task-1"; run.status = "video_batch_running"; db.commit()

    async def fake_get_stage_task(db, stage_task_id):
        return {"ok": True, "status": "completed", "assets": [{"frame_id": "frame-001", "asset_type": "video_segment", "url": "https://cdn.test/segment.mp4", "local_path": "output/segment.mp4", "metadata": {"duration": 5}}]}

    monkeypatch.setattr("app.services.video_production_service.get_stage_task", fake_get_stage_task)
    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", lambda db, scene: {"provider": "mock", "api_key": "x", "model_name": "audit"})
    monkeypatch.setattr("app.routers.audit._do_audit", lambda model, url, text: {"score": 0.95, "pass_fail": True, "issues": []})

    assets = await sync_video_stage_results(db, run.id)
    assert assets[0].asset_type == "video_segment"
    assert assets[0].status == "approved"
    assert db.query(VideoReviewRecord).filter_by(asset_id=assets[0].id, review_type="ai").count() == 1
    db.refresh(run)
    assert run.status == "video_segments_approved"

import pytest
from app.db_models import Episode, GeneratedVideo, Series, VideoProductionAsset, VideoProductionRun
from app.services.video_production_service import approve_asset, reject_asset, start_compose_stage, sync_compose_stage_results


def _run_with_segments(db):
    series = Series(title="Compose", logline="Test", genre="drama", target_duration=60)
    db.add(series); db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot", storyboard_json={"frames": [{"frame_id": "frame-001", "narration": "hello", "duration": 5}]})
    db.add(episode); db.flush()
    run = VideoProductionRun(series_id=series.id, episode_id=episode.id, status="video_segments_approved", current_stage="video_review", storyboard_json=episode.storyboard_json, edit_manifest_json={"output_spec": {"aspect_ratio": "9:16", "resolution": "1080x1920"}})
    db.add(run); db.flush()
    db.add(VideoProductionAsset(run_id=run.id, episode_id=episode.id, frame_id="frame-001", asset_type="video_segment", stage="video_rendering", url="https://cdn.test/segment.mp4", duration_seconds=5, version=1, status="approved"))
    db.commit()
    return run, episode


@pytest.mark.asyncio
async def test_start_compose_stage_submits_approved_segments(db, monkeypatch):
    run, _episode = _run_with_segments(db)
    calls = []

    async def fake_submit_compose(db, run_id, segments, edit_manifest, model_config=None):
        calls.append({"run_id": run_id, "segments": segments, "edit_manifest": edit_manifest})
        return {"ok": True, "stage_task_id": "compose-task-1"}

    monkeypatch.setattr("app.services.video_production_service.submit_compose", fake_submit_compose)
    updated = await start_compose_stage(db, run.id)
    assert updated.status == "composing"
    assert updated.pixelle_stage_task_id == "compose-task-1"
    assert calls[0]["segments"][0]["video_url"] == "https://cdn.test/segment.mp4"


@pytest.mark.asyncio
async def test_sync_compose_results_writes_episode_and_generated_video(db, monkeypatch):
    run, episode = _run_with_segments(db)
    run.pixelle_stage_task_id = "compose-task-1"; run.status = "composing"; db.commit()

    async def fake_get_stage_task(db, stage_task_id):
        return {"ok": True, "status": "completed", "assets": [{"frame_id": "final", "asset_type": "final_video", "url": "https://cdn.test/final.mp4", "local_path": "output/final.mp4", "metadata": {"duration": 5}}]}

    monkeypatch.setattr("app.services.video_production_service.get_stage_task", fake_get_stage_task)
    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", lambda db, scene: {"provider": "mock", "api_key": "x", "model_name": "audit"})
    monkeypatch.setattr("app.routers.audit._do_audit", lambda model, url, text: {"score": 0.96, "pass_fail": True, "issues": []})

    asset = await sync_compose_stage_results(db, run.id)
    assert asset.asset_type == "final_video"; assert asset.status == "approved"
    db.refresh(run); db.refresh(episode)
    assert run.status == "completed"; assert episode.status == "done"
    assert episode.video_url == "https://cdn.test/final.mp4"
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run.id).count() == 1


@pytest.mark.asyncio
async def test_sync_compose_results_enters_final_review_when_audit_fails(db, monkeypatch):
    run, episode = _run_with_segments(db)
    run.pixelle_stage_task_id = "compose-task-1"; run.status = "composing"; db.commit()

    async def fake_get_stage_task(db, stage_task_id):
        return {"ok": True, "status": "completed", "assets": [{"frame_id": "final", "asset_type": "final_video", "url": "https://cdn.test/final.mp4", "local_path": "output/final.mp4", "metadata": {"duration": 5}}]}

    monkeypatch.setattr("app.services.video_production_service.get_stage_task", fake_get_stage_task)
    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", lambda db, scene: {"provider": "mock", "api_key": "x", "model_name": "audit"})
    monkeypatch.setattr("app.routers.audit._do_audit", lambda model, url, text: {"score": 0.4, "pass_fail": False, "issues": ["bad cut"]})

    asset = await sync_compose_stage_results(db, run.id)
    assert asset.asset_type == "final_video"; assert asset.status == "review_pending"
    db.refresh(run); db.refresh(episode)
    assert run.status == "final_review_pending"
    assert episode.video_url is None
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run.id).count() == 0


def test_human_approve_final_video_completes_run_after_final_audit_failure(db):
    run, episode = _run_with_segments(db)
    final_asset = VideoProductionAsset(run_id=run.id, episode_id=episode.id, frame_id="final", asset_type="final_video", stage="composition", url="https://cdn.test/final.mp4", local_path="output/final.mp4", duration_seconds=5, version=1, status="review_pending", pixelle_task_id="compose-task-1")
    run.status = "final_review_pending"; run.current_stage = "final_review"
    db.add(final_asset); db.commit()

    approved = approve_asset(db, final_asset.id, reviewer_user_id="test-user", comment="approved")
    assert approved.status == "approved"
    db.refresh(run); db.refresh(episode)
    assert run.status == "completed"; assert episode.status == "done"
    assert episode.video_url == "https://cdn.test/final.mp4"
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run.id).count() == 1


def test_human_reject_final_video_returns_run_to_compose_ready(db):
    run, episode = _run_with_segments(db)
    final_asset = VideoProductionAsset(run_id=run.id, episode_id=episode.id, frame_id="final", asset_type="final_video", stage="composition", url="https://cdn.test/final.mp4", local_path="output/final.mp4", duration_seconds=5, version=1, status="review_pending", pixelle_task_id="compose-task-1")
    run.status = "final_review_pending"; run.current_stage = "final_review"
    db.add(final_asset); db.commit()

    rejected = reject_asset(db, final_asset.id, reviewer_user_id="test-user", comment="bad cut")
    assert rejected.status == "rejected"
    db.refresh(run); db.refresh(episode)
    assert run.status == "video_segments_approved"
    assert run.current_stage == "video_review"
    assert episode.video_url is None
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run.id).count() == 0

from fastapi.testclient import TestClient
from app.db_models import Episode, GeneratedVideo, Series
from app.main import app

client = TestClient(app)


def test_storyboard_to_final_video_mocked_e2e(db, monkeypatch):
    series = Series(title="Full E2E", logline="Test", genre="drama", target_duration=30)
    db.add(series); db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot",
        storyboard_json={"frames": [{"frame_id": "frame-001", "image_prompt": "Prompt", "video_prompt": "Move", "narration": "Hello", "duration": 5}]})
    db.add(episode); db.commit()

    stage = {"current": None}

    async def fake_submit_image_batch(db, run_id, episode_id, frames, model_config, template_config=None):
        stage["current"] = "image"; return {"ok": True, "stage_task_id": "image-task"}

    async def fake_submit_video_batch(db, run_id, frames, model_config, template_config=None):
        stage["current"] = "video"; return {"ok": True, "stage_task_id": "video-task"}

    async def fake_submit_compose(db, run_id, segments, edit_manifest, model_config=None):
        stage["current"] = "compose"; return {"ok": True, "stage_task_id": "compose-task"}

    async def fake_get_stage_task(db, stage_task_id):
        if stage_task_id == "image-task":
            return {"ok": True, "status": "completed", "assets": [{"frame_id": "frame-001", "asset_type": "image", "url": "image.png", "metadata": {"duration": 5}}]}
        if stage_task_id == "video-task":
            return {"ok": True, "status": "completed", "assets": [{"frame_id": "frame-001", "asset_type": "video_segment", "url": "segment.mp4", "metadata": {"duration": 5}}]}
        return {"ok": True, "status": "completed", "assets": [{"frame_id": "final", "asset_type": "final_video", "url": "final.mp4", "local_path": "output/final.mp4", "metadata": {"duration": 5}}]}

    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", lambda db, scene: {"provider": "mock", "api_key": "x", "scene_key": scene})
    monkeypatch.setattr("app.services.video_production_service.submit_image_batch", fake_submit_image_batch)
    monkeypatch.setattr("app.services.video_production_service.submit_video_batch", fake_submit_video_batch)
    monkeypatch.setattr("app.services.video_production_service.submit_compose", fake_submit_compose)
    monkeypatch.setattr("app.services.video_production_service.get_stage_task", fake_get_stage_task)
    monkeypatch.setattr("app.routers.audit._do_audit", lambda model, url, text: {"score": 0.99, "pass_fail": True, "issues": []})

    created = client.post("/api/video-production/runs", json={"series_id": series.id, "episode_id": episode.id}).json()
    run_id = created["run"]["id"]

    assert client.post(f"/api/video-production/runs/{run_id}/start-images").status_code == 200
    assert client.post(f"/api/video-production/runs/{run_id}/sync-image-results").status_code == 200
    assert client.post(f"/api/video-production/runs/{run_id}/start-videos").status_code == 200
    assert client.post(f"/api/video-production/runs/{run_id}/sync-video-results").status_code == 200
    assert client.post(f"/api/video-production/runs/{run_id}/compose").status_code == 200
    assert client.post(f"/api/video-production/runs/{run_id}/sync-compose-results").status_code == 200

    final = client.get(f"/api/video-production/runs/{run_id}").json()
    assert final["run"]["status"] == "completed"
    db.refresh(episode)
    assert episode.video_url == "final.mp4"
    assert episode.status == "done"
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run_id).count() == 1

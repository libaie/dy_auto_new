from fastapi.testclient import TestClient

from app.db_models import AIModel, Episode, Series
from app.main import app


client = TestClient(app)


async def _agency_pass(*args, **kwargs):
    return {"stage_status": "passed", "invocation_ids": ["agency-ok"], "invocations": []}


def test_mocked_image_stage_to_human_approval(db, monkeypatch):
    series = Series(title="Mocked E2E", logline="Test", genre="drama", target_duration=60)
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={"frames": [{"frame_id": "frame-001", "image_prompt": "Prompt", "duration": 5}]},
    )
    model = AIModel(
        name="Mock Image",
        model_type="image",
        provider="mock",
        model_name="mock-image",
        enabled=True,
        config_json={"scene_key": "image_generation"},
    )
    db.add_all([episode, model])
    db.commit()

    async def fake_submit_image_batch(db, run_id, episode_id, frames, model_config, template_config=None):
        return {"ok": True, "stage_task_id": "stage-1", "assets": []}

    async def fake_get_stage_task(db, stage_task_id):
        return {
            "ok": True,
            "stage_task_id": stage_task_id,
            "status": "completed",
            "assets": [{
                "frame_id": "frame-001",
                "asset_type": "image",
                "url": "https://cdn.test/frame-001.png",
                "local_path": "output/frame-001.png",
                "storage_path": "output/frame-001.png",
                "checksum": "checksum-frame-001",
                "copy_status": "persisted",
                "metadata": {},
            }],
        }

    monkeypatch.setattr("app.services.video_production_service.submit_image_batch", fake_submit_image_batch)
    monkeypatch.setattr("app.services.video_production_service._guard_provider_stage", _agency_pass)
    monkeypatch.setattr("app.services.video_production_service.get_stage_task", fake_get_stage_task)

    run_resp = client.post("/api/video-production/runs", json={"series_id": series.id, "episode_id": episode.id})
    run_id = run_resp.json()["run"]["id"]

    submit_resp = client.post(f"/api/video-production/runs/{run_id}/start-images")
    assert submit_resp.status_code == 200

    sync_resp = client.post(f"/api/video-production/runs/{run_id}/sync-image-results")
    assert sync_resp.status_code == 200
    items = client.get(f"/api/video-production/review-items?run_id={run_id}").json()["items"]
    assert len(items) == 1
    assert items[0]["status"] == "review_pending"

    approve_resp = client.post(f"/api/video-production/assets/{items[0]['id']}/review", json={"action": "approve"})
    assert approve_resp.status_code == 200

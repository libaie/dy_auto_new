import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db_models import Episode, PipelineRun, Series


client = TestClient(app)


def _series_with_storyboard(db):
    series = Series(
        title="Pipeline Compat",
        logline="Saved storyboard should start without director_plan.",
        genre="drama",
        target_duration=60,
        mode="fully_automatic",
    )
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={
            "frames": [{
                "frame_id": "frame-001",
                "narration": "A clean opening.",
                "image_prompt": "A cinematic opening frame.",
                "duration": 5,
                "reference_urls": ["https://cdn.test/ref.png"],
            }]
        },
    )
    db.add(episode)
    db.commit()
    return series, episode


@pytest.mark.asyncio
async def test_pipeline_start_loads_saved_storyboard_when_director_plan_missing(db, monkeypatch):
    from app.routers import pipeline

    series, episode = _series_with_storyboard(db)
    captured = {}

    async def fake_submit_and_poll(payload, request_db):
        captured["payload"] = payload
        return {
            "task_id": "pixelle-task-1",
            "video_path": "output/final.mp4",
            "duration": 5,
        }

    monkeypatch.setattr(pipeline, "_submit_and_poll", fake_submit_and_poll)

    resp = client.post("/api/pipeline/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "director_plan": None,
    })

    assert resp.status_code == 200
    assert resp.json()["run_id"]
    assert captured["payload"]["frames"][0]["frame_id"] == "frame-001"
    assert captured["payload"]["frames"][0]["reference_urls"] == ["https://cdn.test/ref.png"]


def test_pipeline_run_lookup_routes_exist(db):
    series, episode = _series_with_storyboard(db)
    run = PipelineRun(
        series_id=series.id,
        episode_id=episode.id,
        mode="fully_automatic",
        status="running",
        current_layer=0,
        layers_json={"0": {"status": "queued"}},
    )
    db.add(run)
    db.commit()

    by_series = client.get(f"/api/pipeline/runs/{series.id}")
    by_pair = client.get(f"/api/pipeline/runs/{series.id}/{run.id}")
    by_id = client.get(f"/api/pipeline/runs/by-id/{run.id}")

    assert by_series.status_code == 200
    assert by_pair.status_code == 200
    assert by_id.status_code == 200
    assert by_id.json()["run"]["id"] == run.id

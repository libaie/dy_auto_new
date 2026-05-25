from fastapi.testclient import TestClient

from app.db_models import Episode, Series
from app.main import app


client = TestClient(app)


def _episode(db):
    series = Series(title="Review API", logline="Test", genre="drama", target_duration=60)
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={"frames": [{"frame_id": "frame-001", "image_prompt": "Prompt", "duration": 5}]},
    )
    db.add(episode)
    db.commit()
    return series, episode


def test_create_video_production_run(db):
    series, episode = _episode(db)

    resp = client.post("/api/video-production/runs", json={
        "series_id": series.id,
        "episode_id": episode.id,
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["run"]["episode_id"] == episode.id
    assert body["run"]["current_stage"] == "storyboard_ready"


def test_regenerate_creates_new_version(db):
    from app.services.video_production_service import create_run_from_episode, mark_image_stage_assets

    series, episode = _episode(db)
    run = create_run_from_episode(db, series.id, episode.id)
    assets = mark_image_stage_assets(db, run, [{
        "frame_id": "frame-001",
        "asset_type": "image",
        "url": "https://cdn.test/v1.png",
        "local_path": "output/v1.png",
        "metadata": {},
    }], pixelle_task_id="stage-1")

    resp = client.post(f"/api/video-production/assets/{assets[0].id}/regenerate", json={
        "url": "https://cdn.test/v2.png",
        "local_path": "output/v2.png",
        "metadata": {},
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["asset"]["version"] == 2
    assert body["asset"]["status"] == "review_pending"

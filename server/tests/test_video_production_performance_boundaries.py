from fastapi.testclient import TestClient

from app.db_models import Episode, Series, VideoProductionAsset, VideoProductionRun
from app.main import app


client = TestClient(app)


def _run_with_assets(db, count=150):
    series = Series(title="Perf", logline="Perf", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="running",
        current_stage="image_review",
    )
    db.add(run)
    db.flush()
    for index in range(count):
        db.add(VideoProductionAsset(
            run_id=run.id,
            episode_id=episode.id,
            frame_id=f"frame-{index}",
            asset_type="image",
            stage="image_generation",
            status="review_pending",
            url=f"https://cdn.test/{index}.png",
        ))
    db.commit()
    return run


def test_get_run_does_not_return_unbounded_assets(db):
    run = _run_with_assets(db, count=150)

    response = client.get(f"/api/video-production/runs/{run.id}")

    assert response.status_code == 200
    body = response.json()
    assert "asset_summary" in body
    assert "assets" not in body
    assert "assets" not in body["run"]
    assert body["asset_summary"]["image"]["review_pending"] == 150


def test_review_items_caps_page_size_at_100(db):
    _run_with_assets(db, count=150)

    response = client.get("/api/video-production/review-items", params={"page_size": 500})

    assert response.status_code == 200
    body = response.json()
    assert body["page_size"] == 100
    assert len(body["items"]) == 100

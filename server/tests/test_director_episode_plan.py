from fastapi.testclient import TestClient

from app.db_models import Episode, ProductionEpisode, ProductionPlan, ProductionSegment, ProductionShot, Series
from app.main import app


def _locked_episode(db):
    series = Series(
        title="Episode Plan",
        logline="Test",
        genre="drama",
        story_bible_json={"style_lock": {"locked": True, "version": 1, "visual_style": {}}},
    )
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        storyboard_json={"frames": [{
            "frame_id": "shot-1",
            "scene_id": "scene-1",
            "duration": 10,
            "image_prompt": "A",
            "video_prompt": "B",
        }]},
    )
    db.add(episode)
    db.commit()
    return series, episode


def test_episode_plan_alias_creates_plan_and_segments_idempotently(db):
    series, episode = _locked_episode(db)
    client = TestClient(app)

    first = client.post("/api/director/episode-plan", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "include_segments": True,
    })
    second = client.post("/api/director/episode-plan", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "include_segments": True,
    })

    assert first.status_code == 200
    assert second.status_code == 200
    assert db.query(ProductionPlan).count() == 1
    assert db.query(ProductionEpisode).count() == 1
    assert db.query(ProductionShot).count() == 1
    assert db.query(ProductionSegment).count() == 2


def test_episode_plan_alias_can_create_plan_without_segments(db):
    series, episode = _locked_episode(db)
    client = TestClient(app)

    resp = client.post("/api/director/episode-plan", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "include_segments": False,
    })

    assert resp.status_code == 200
    assert db.query(ProductionPlan).count() == 1
    assert db.query(ProductionEpisode).count() == 1
    assert db.query(ProductionShot).count() == 1
    assert db.query(ProductionSegment).count() == 0

import pytest
from fastapi.testclient import TestClient

from app.db_models import (
    Episode,
    ProductionEpisode,
    ProductionPlan,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    Series,
)
from app.main import app
from app.services.production_status import (
    PLAN_READY,
    REFERENCE_CHARACTER_ANCHOR,
    REFERENCE_STYLE_ANCHOR,
    SEGMENT_PLANNED,
)


def _create_locked_series_with_episode(db, *, locked=True, frames=None):
    series = Series(
        title="Plan Show",
        logline="Test",
        genre="drama",
        story_bible_json={
            "style_lock": {
                "locked": locked,
                "version": 1,
                "style_anchors": ["https://cdn.test/style-a.png"],
                "visual_style": {
                    "reference_urls": ["https://cdn.test/style-b.png"],
                },
            }
        },
    )
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={"frames": frames if frames is not None else [{
            "frame_id": "frame-001",
            "scene_id": "scene-a",
            "character_ids": ["char-a"],
            "image_prompt": "Hero stands in a blue-lit street",
            "video_prompt": "Hero turns and walks forward",
            "narration": "The city is quiet.",
            "duration": 12,
            "reference_urls": ["https://cdn.test/char.png"],
            "expected_end_state": "Hero has started walking forward.",
            "continuity_mode": "continuous_action",
        }]},
    )
    db.add(episode)
    db.commit()
    return series, episode


def test_create_episode_production_plan_splits_long_frame_into_segments(db):
    from app.services.production_plan_service import create_episode_production_plan

    series, episode = _create_locked_series_with_episode(db)

    plan = create_episode_production_plan(
        db,
        series.id,
        episode.id,
        target_duration_seconds=12,
        budget_limit=20.0,
    )

    assert db.query(ProductionPlan).filter_by(id=plan.id).one().status == PLAN_READY
    assert db.query(ProductionEpisode).one().status == PLAN_READY
    assert db.query(ProductionScene).one().status == PLAN_READY
    assert db.query(ProductionShot).one().status == PLAN_READY

    segments = db.query(ProductionSegment).order_by(ProductionSegment.order_index).all()
    assert len(segments) == 2
    assert [segment.status for segment in segments] == [SEGMENT_PLANNED, SEGMENT_PLANNED]
    assert [segment.duration_seconds for segment in segments] == [6.0, 6.0]
    assert segments[0].continuity_mode == "continuous_action"
    assert segments[1].previous_segment_id == segments[0].id
    assert segments[0].image_prompt == "Hero stands in a blue-lit street"
    assert segments[0].video_prompt == "Hero turns and walks forward"
    assert segments[0].narration == "The city is quiet."
    assert segments[0].expected_end_state == "Hero has started walking forward."

    role_pairs = {(item["role"], item["url"]) for item in segments[0].reference_roles_json}
    assert (REFERENCE_CHARACTER_ANCHOR, "https://cdn.test/char.png") in role_pairs
    assert (REFERENCE_STYLE_ANCHOR, "https://cdn.test/style-a.png") in role_pairs
    assert (REFERENCE_STYLE_ANCHOR, "https://cdn.test/style-b.png") in role_pairs


def test_create_episode_production_plan_requires_locked_style(db):
    from app.services.production_plan_service import create_episode_production_plan

    series, episode = _create_locked_series_with_episode(db, locked=False)

    with pytest.raises(ValueError, match="style must be locked"):
        create_episode_production_plan(db, series.id, episode.id)


def test_create_episode_production_plan_rejects_empty_storyboard(db):
    from app.services.production_plan_service import create_episode_production_plan

    series, episode = _create_locked_series_with_episode(db, frames=[])

    with pytest.raises(ValueError, match="storyboard"):
        create_episode_production_plan(db, series.id, episode.id)


def test_create_episode_production_plan_rejects_non_object_frames(db):
    from app.services.production_plan_service import create_episode_production_plan

    series, episode = _create_locked_series_with_episode(db, frames=[None])

    with pytest.raises(ValueError, match="frames must contain objects"):
        create_episode_production_plan(db, series.id, episode.id)


def test_episode_production_plan_endpoint_creates_plan(db):
    series, episode = _create_locked_series_with_episode(db)

    with TestClient(app) as client:
        resp = client.post("/api/director/episode-production-plan", json={
            "series_id": series.id,
            "episode_id": episode.id,
            "target_duration_seconds": 12,
            "budget_limit": 20.0,
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["plan"]["series_id"] == series.id
    assert data["plan"]["status"] == PLAN_READY
    assert db.query(ProductionSegment).count() == 2


def test_episode_production_plan_endpoint_returns_400_for_validation_errors(db):
    series, episode = _create_locked_series_with_episode(db, locked=False)

    with TestClient(app) as client:
        resp = client.post("/api/director/episode-production-plan", json={
            "series_id": series.id,
            "episode_id": episode.id,
        })

    assert resp.status_code == 400
    assert "style must be locked" in resp.json()["detail"]

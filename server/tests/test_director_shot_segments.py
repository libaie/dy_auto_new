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


def test_shot_segments_route_is_idempotent(db):
    series = Series(title="Segments", logline="Test", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1)
    db.add(episode)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready", active_version=1, target_total_duration_seconds=10)
    db.add(plan)
    db.flush()
    prod_episode = ProductionEpisode(
        plan_id=plan.id,
        episode_id=episode.id,
        order_index=1,
        status="ready",
        target_duration_seconds=10,
    )
    db.add(prod_episode)
    db.flush()
    scene = ProductionScene(episode_plan_id=prod_episode.id, scene_id="scene-1", order_index=1, status="ready")
    db.add(scene)
    db.flush()
    shot = ProductionShot(
        scene_plan_id=scene.id,
        shot_id="shot-1",
        order_index=1,
        status="ready",
        duration_seconds=10,
    )
    db.add(shot)
    db.commit()

    client = TestClient(app)
    for _ in range(2):
        resp = client.post("/api/director/shot-segments", json={
            "production_episode_id": prod_episode.id,
            "preferred_segment_seconds": 8,
        })
        assert resp.status_code == 200

    assert db.query(ProductionSegment).count() == 2

from fastapi.testclient import TestClient

from app.db.models import AITextArtifact, Episode, ProductionJob, Series
from app.main import app


def test_force_story_plan_endpoint_requeues_completed_plan(db):
    client = TestClient(app)
    series = Series(
        title="Force Story API",
        logline="A family secret returns.",
        total_episodes=1,
        status="draft",
        story_bible_json={"story_planning": {"status": "completed", "version": 1, "job_id": "job-done"}},
    )
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, status="pending")
    db.add(episode)
    db.flush()
    db.add_all([
        AITextArtifact(
            series_id=series.id,
            target_type="series",
            target_id=series.id,
            artifact_type="series_story_plan",
            version=1,
            status="approved",
            source_type="ai",
            content_json={"summary": "The family secret escalates."},
        ),
        AITextArtifact(
            series_id=series.id,
            target_type="series",
            target_id=series.id,
            artifact_type="season_arc",
            version=1,
            status="approved",
            source_type="ai",
            content_json={"arc_summary": "Truth rises."},
        ),
        AITextArtifact(
            series_id=series.id,
            target_type="series",
            target_id=series.id,
            artifact_type="continuity_ledger",
            version=1,
            status="approved",
            source_type="ai",
            content_json={"mainline": "Keep it coherent."},
        ),
        AITextArtifact(
            series_id=series.id,
            episode_id=episode.id,
            target_type="episode",
            target_id=episode.id,
            artifact_type="episode_outline",
            version=1,
            status="approved",
            source_type="ai",
            content_json={"episode_number": 1, "episode_goal": "Expose the first clue."},
        ),
    ])
    db.commit()

    resp = client.post(f"/api/series/{series.id}/story-plan?force=true")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "planning"
    assert data["story_planning"]["status"] == "queued"
    assert data["story_planning"]["force"] is True
    assert data["story_planning"]["version"] == 2
    assert db.query(ProductionJob).filter_by(
        target_type="series",
        target_id=series.id,
        stage="story_planning",
        status="queued",
    ).count() == 1

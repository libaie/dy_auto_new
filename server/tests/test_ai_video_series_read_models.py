from app.db_models import Episode, Series, VideoProductionRun
from app.domains.ai_video_series.read_models import (
    active_video_runs_by_episode,
    episode_dict_with_video_run,
    series_dict,
)


def test_series_dict_preserves_public_shape(db):
    series = Series(
        title="Read Model Series",
        logline="A clear public shape.",
        genre="drama",
        total_episodes=2,
        target_duration=90,
        mode="step_by_step",
        pilot_first=True,
        status="draft",
    )
    db.add(series)
    db.commit()

    payload = series_dict(series)

    assert payload["id"] == series.id
    assert payload["title"] == "Read Model Series"
    assert payload["logline"] == "A clear public shape."
    assert payload["genre"] == "drama"
    assert payload["total_episodes"] == 2
    assert payload["target_duration"] == 90
    assert payload["mode"] == "step_by_step"
    assert payload["pilot_first"] is True
    assert payload["status"] == "draft"


def test_episode_payload_includes_active_video_run(db):
    series = Series(title="Episode Read Model", logline="Status", genre="drama")
    episode = Episode(series=series, episode_number=1, title="Pilot", status="pending")
    db.add_all([series, episode])
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="running",
        current_stage="image_batch_running",
        run_type="real_short_e2e",
    )
    db.add(run)
    db.commit()

    active_runs = active_video_runs_by_episode(db, series.id)
    payload = episode_dict_with_video_run(episode, active_runs[episode.id])

    assert payload["id"] == episode.id
    assert payload["episode_number"] == 1
    assert payload["active_video_run_id"] == run.id
    assert payload["video_run_status"] == "running"
    assert payload["video_run_stage"] == "image_batch_running"
    assert payload["video_run_route"] == f"/video-production/{run.id}"

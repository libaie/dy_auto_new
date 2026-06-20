from __future__ import annotations

from app.db_models import Episode, ImageCreationAsset, ImageCreationTask, Series, VideoProductionAsset, VideoProductionRun
from app.services.video_production_service import image_stage_frames


def _series_episode_run(db):
    series = Series(title="Storyboard Bridge", logline="Approved frame images feed video", status="active")
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Episode 1",
        storyboard_json={
            "frames": [{
                "frame_id": "shot-001",
                "time_range": "0-2秒",
                "duration": 2,
                "image_prompt": "时间段: 0-2秒\n主体/角色: 老李\n画面动作: 老李抬头。",
                "reference_urls": ["/static/image-creation/reference.png"],
            }]
        },
    )
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="storyboard_ready",
        current_stage="storyboard_ready",
        storyboard_json=episode.storyboard_json,
    )
    db.add(run)
    db.commit()
    return series, episode, run


def test_image_stage_frames_prefer_promoted_approved_storyboard_image(db):
    series, episode, run = _series_episode_run(db)
    task = ImageCreationTask(
        id="task-approved",
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="completed",
        series_id=series.id,
        episode_id=episode.id,
        prompt="prompt",
        destination_role="storyboard_frame",
        destination_context_json={"run_id": run.id, "frame_id": "shot-001"},
        count=1,
        target_count=1,
    )
    db.add(task)
    db.flush()
    image_asset = ImageCreationAsset(
        id="image-asset-approved",
        task_id=task.id,
        series_id=series.id,
        episode_id=episode.id,
        url="/static/image-creation/approved-storyboard.png",
        status="approved",
        version=1,
        destination_role="storyboard_frame",
        destination_context_json={"run_id": run.id, "frame_id": "shot-001"},
    )
    db.add(image_asset)
    db.add(VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="shot-001",
        asset_type="image",
        stage="image_review",
        url=image_asset.url,
        version=1,
        status="approved",
        metadata_json={
            "source_image_asset_id": image_asset.id,
            "destination_role": "storyboard_frame",
        },
    ))
    db.commit()

    frames = image_stage_frames(run, db)

    assert frames[0]["frame_id"] == "shot-001"
    assert frames[0]["source_image_url"] == "/static/image-creation/approved-storyboard.png"
    assert frames[0]["storyboard_image_asset_id"] == "image-asset-approved"
    assert frames[0]["reference_urls"] == ["/static/image-creation/reference.png"]


def test_image_stage_frames_ignore_unpromoted_storyboard_image_asset(db):
    series, episode, run = _series_episode_run(db)
    task = ImageCreationTask(
        id="task-pending",
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="completed",
        series_id=series.id,
        episode_id=episode.id,
        prompt="prompt",
        destination_role="storyboard_frame",
        destination_context_json={"run_id": run.id, "frame_id": "shot-001"},
        count=1,
        target_count=1,
    )
    db.add(task)
    db.flush()
    db.add(ImageCreationAsset(
        id="image-asset-pending",
        task_id=task.id,
        series_id=series.id,
        episode_id=episode.id,
        url="/static/image-creation/pending-storyboard.png",
        status="review_pending",
        version=1,
        destination_role="storyboard_frame",
        destination_context_json={"run_id": run.id, "frame_id": "shot-001"},
    ))
    db.commit()

    frames = image_stage_frames(run, db)

    assert "source_image_url" not in frames[0]
    assert "storyboard_image_asset_id" not in frames[0]

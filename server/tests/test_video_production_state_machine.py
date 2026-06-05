from app.db_models import Episode, Series, VideoProductionAsset, VideoProductionRun, VideoReviewRecord
from app.services.video_production_state import (
    assert_can_start_images,
    assert_can_start_videos,
    assert_can_compose,
    latest_assets_by_frame,
    record_stage_task,
    recompute_run_gate,
)
from app.services.video_production_service import mark_image_stage_assets, run_ai_audit_for_assets


def _run(db, frame_count=2):
    series = Series(title="State", logline="Test", genre="drama", target_duration=60)
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={
            "frames": [
                {"frame_id": f"frame-{index:03d}", "image_prompt": "Prompt", "duration": 5}
                for index in range(1, frame_count + 1)
            ]
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
    return run


def _asset(db, run, frame_id, asset_type, version, status, task_id="task-1"):
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=run.episode_id,
        frame_id=frame_id,
        asset_type=asset_type,
        stage="image_generation" if asset_type == "image" else "video_rendering",
        url=f"https://cdn.test/{frame_id}-{asset_type}-{version}",
        version=version,
        status=status,
        pixelle_task_id=task_id,
    )
    db.add(asset)
    db.commit()
    return asset


def test_latest_assets_by_frame_uses_highest_version(db):
    run = _run(db, frame_count=1)
    old = _asset(db, run, "frame-001", "image", 1, "approved")
    new = _asset(db, run, "frame-001", "image", 2, "review_pending")

    latest = latest_assets_by_frame(db, run.id, "image")

    assert latest["frame-001"].id == new.id
    assert latest["frame-001"].id != old.id


def test_cannot_start_videos_until_each_latest_image_is_approved(db):
    run = _run(db, frame_count=2)
    run.status = "image_approved"
    _asset(db, run, "frame-001", "image", 1, "approved")
    _asset(db, run, "frame-002", "image", 1, "review_pending")
    db.commit()

    try:
        assert_can_start_videos(db, run)
    except ValueError as exc:
        assert "Images not approved: frame-002" in str(exc)
    else:
        raise AssertionError("Expected gate failure")


def test_start_video_stage_rejects_duplicate_inflight_run(db):
    run = _run(db, frame_count=1)
    run.status = "video_batch_running"
    run.current_stage = "video_rendering"
    record_stage_task(run, "video_rendering", "video-task-1")
    _asset(db, run, "frame-001", "image", 1, "approved")
    db.commit()

    try:
        assert_can_start_videos(db, run)
    except ValueError as exc:
        assert "Video stage already started" in str(exc)
    else:
        raise AssertionError("Expected duplicate video stage gate failure")


def test_can_retry_video_stage_after_pre_video_gate_block_without_video_assets(db):
    run = _run(db, frame_count=1)
    run.status = "video_human_review_required"
    run.current_stage = "video_review"
    _asset(db, run, "frame-001", "image", 1, "approved")
    db.commit()

    assert_can_start_videos(db, run)


def test_cannot_retry_video_stage_when_video_assets_exist_for_review(db):
    run = _run(db, frame_count=1)
    run.status = "video_human_review_required"
    run.current_stage = "video_review"
    _asset(db, run, "frame-001", "image", 1, "approved")
    _asset(db, run, "frame-001", "video_segment", 1, "rejected")
    db.commit()

    try:
        assert_can_start_videos(db, run)
    except ValueError as exc:
        assert "Video stage can start only after images are approved" in str(exc)
    else:
        raise AssertionError("Expected video review retry gate failure")


def test_start_compose_stage_rejects_duplicate_inflight_run(db):
    run = _run(db, frame_count=1)
    run.status = "composing"
    run.current_stage = "composition"
    record_stage_task(run, "composition", "compose-task-1")
    _asset(db, run, "frame-001", "video_segment", 1, "approved")
    db.commit()

    try:
        assert_can_compose(db, run)
    except ValueError as exc:
        assert "Compose stage already started" in str(exc)
    else:
        raise AssertionError("Expected duplicate compose stage gate failure")


def test_sync_image_stage_results_is_idempotent_for_same_pixelle_task(db):
    run = _run(db, frame_count=1)
    assets = [{"frame_id": "frame-001", "url": "https://cdn.test/image.png", "metadata": {}}]

    first = mark_image_stage_assets(db, run, assets, pixelle_task_id="image-task-1")
    first[0].status = "approved"
    db.commit()
    second = mark_image_stage_assets(db, run, assets, pixelle_task_id="image-task-1")

    assert second[0].id == first[0].id
    assert db.query(VideoProductionAsset).filter_by(run_id=run.id, asset_type="image").count() == 1


def test_ai_audit_is_idempotent_for_existing_asset_review(db):
    run = _run(db, frame_count=1)
    asset = _asset(db, run, "frame-001", "image", 1, "review_pending")
    db.add(VideoReviewRecord(asset_id=asset.id, run_id=run.id, review_type="ai", status="approved", score=1.0))
    db.commit()

    run_ai_audit_for_assets(db, run, [asset])

    assert db.query(VideoReviewRecord).filter_by(asset_id=asset.id, review_type="ai").count() == 1


def test_recompute_image_gate_sets_image_approved_when_all_latest_images_pass(db):
    run = _run(db, frame_count=2)
    _asset(db, run, "frame-001", "image", 1, "approved")
    _asset(db, run, "frame-002", "image", 1, "approved")

    recompute_run_gate(db, run.id, "image")
    db.refresh(run)

    assert run.status == "image_approved"
    assert run.current_stage == "image_review"


def test_recompute_video_gate_sets_video_segments_approved_when_all_latest_segments_pass(db):
    run = _run(db, frame_count=2)
    _asset(db, run, "frame-001", "video_segment", 1, "approved")
    _asset(db, run, "frame-002", "video_segment", 1, "approved")

    recompute_run_gate(db, run.id, "video_segment")
    db.refresh(run)

    assert run.status == "video_segments_approved"
    assert run.current_stage == "video_review"


def test_recompute_video_gate_treats_failed_segment_as_human_blocked(db):
    run = _run(db, frame_count=1)
    _asset(db, run, "frame-001", "video_segment", 1, "failed")

    recompute_run_gate(db, run.id, "video_segment")
    db.refresh(run)

    assert run.status == "video_human_review_required"
    assert run.current_stage == "video_review"


def test_cannot_compose_until_latest_video_segments_are_approved(db):
    run = _run(db, frame_count=1)
    run.status = "video_segments_approved"
    _asset(db, run, "frame-001", "video_segment", 1, "approved")
    _asset(db, run, "frame-001", "video_segment", 2, "review_pending")
    db.commit()

    try:
        assert_can_compose(db, run)
    except ValueError as exc:
        assert "Video segments not approved: frame-001" in str(exc)
    else:
        raise AssertionError("Expected compose gate failure")


def test_start_images_is_allowed_only_from_storyboard_ready(db):
    run = _run(db)
    assert_can_start_images(run)
    run.status = "image_batch_running"

    try:
        assert_can_start_images(run)
    except ValueError as exc:
        assert "Image stage already started" in str(exc)
    else:
        raise AssertionError("Expected start image gate failure")

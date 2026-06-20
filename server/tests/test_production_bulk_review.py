import pytest

from app.db.models import (
    Episode,
    ProductionEpisode,
    ProductionPlan,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    Series,
    VideoProductionAsset,
    VideoProductionRun,
    VideoReviewRecord,
)
from app.domains.video_production.production_review_service import apply_bulk_review_action
from app.domains.video_production.production_segment_service import retry_segment
from app.domains.video_production.production_status import SEGMENT_RETRY_QUEUED, SEGMENT_SUPERSEDED
from app.domains.video_production.video_production_run_types import MOCK_SERIES_SCALE, REAL_SHORT_E2E


def _production_context(db, frame_ids=("seg-1",), run_type=MOCK_SERIES_SCALE):
    series = Series(title="Review Show", logline="Review", genre="drama")
    db.add(series)
    db.flush()

    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={
            "frames": [
                {"frame_id": frame_id, "image_prompt": "Prompt", "duration": 5}
                for frame_id in frame_ids
            ]
        },
    )
    db.add(episode)
    db.flush()

    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="image_review_pending",
        current_stage="image_review",
        run_type=run_type,
        storyboard_json=episode.storyboard_json,
    )
    db.add(run)

    plan = ProductionPlan(series_id=series.id, status="ready", target_total_duration_seconds=60)
    db.add(plan)
    db.flush()

    production_episode = ProductionEpisode(
        plan_id=plan.id,
        episode_id=episode.id,
        order_index=1,
        status="ready",
        target_duration_seconds=60,
    )
    db.add(production_episode)
    db.flush()

    scene = ProductionScene(
        episode_plan_id=production_episode.id,
        scene_id="scene-a",
        order_index=1,
        status="ready",
        location_summary="Night street",
    )
    db.add(scene)
    db.flush()

    shot = ProductionShot(
        scene_plan_id=scene.id,
        shot_id="shot-a",
        order_index=1,
        status="ready",
        character_ids=[],
        action="move",
        duration_seconds=5,
    )
    db.add(shot)
    db.commit()
    return series, episode, run, shot


def _asset(db, run, frame_id, asset_type, version, status, copy_status="persisted"):
    storage_path = f"output/video-production/{frame_id}-{asset_type}-{version}" if copy_status == "persisted" else None
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=run.episode_id,
        frame_id=frame_id,
        asset_type=asset_type,
        stage="image_generation" if asset_type == "image" else "video_rendering",
        url=f"https://cdn.test/{frame_id}-{asset_type}-{version}",
        source_url=f"https://cdn.test/{frame_id}-{asset_type}-{version}",
        storage_path=storage_path,
        checksum=f"sha256-{frame_id}-{asset_type}-{version}" if copy_status == "persisted" else None,
        copy_status=copy_status,
        version=version,
        status=status,
    )
    db.add(asset)
    db.commit()
    return asset


def test_bulk_review_approves_latest_only(db):
    _, _, run, _ = _production_context(db)
    old = _asset(db, run, "seg-1", "image", 1, "review_pending")
    new = _asset(db, run, "seg-1", "image", 2, "review_pending")

    result = apply_bulk_review_action(
        db,
        [old.id, new.id],
        action="approve",
        reviewer_user_id="user-a",
        comment="bulk approve",
    )

    db.refresh(old)
    db.refresh(new)
    db.refresh(run)
    assert result == {"approved": 1, "rejected": 0, "skipped_stale": 1}
    assert old.status == "review_pending"
    assert new.status == "approved"
    assert run.status == "image_approved"


def test_bulk_reject_creates_review_record(db):
    _, _, run, _ = _production_context(db)
    asset = _asset(db, run, "seg-1", "video_segment", 1, "review_pending")

    result = apply_bulk_review_action(
        db,
        [asset.id],
        action="reject",
        reviewer_user_id="user-b",
        comment="motion break",
    )

    db.refresh(asset)
    db.refresh(run)
    review = db.query(VideoReviewRecord).filter_by(asset_id=asset.id, review_type="human").one()
    assert result == {"approved": 0, "rejected": 1, "skipped_stale": 0}
    assert asset.status == "rejected"
    assert review.status == "rejected"
    assert review.score == 0.0
    assert review.issues_json == ["motion break"]
    assert review.reviewer_user_id == "user-b"
    assert review.comment == "motion break"
    assert review.asset_version == asset.version
    assert review.is_latest_asset_review is True
    assert run.status == "video_human_review_required"


def test_bulk_review_rejects_unsupported_action(db):
    _, _, run, _ = _production_context(db)
    asset = _asset(db, run, "seg-1", "image", 1, "review_pending")

    with pytest.raises(ValueError, match="Unsupported review action"):
        apply_bulk_review_action(db, [asset.id], action="hold")


def test_bulk_review_rejects_real_short_assets_without_mutating(db):
    _, _, run, _ = _production_context(db, run_type=REAL_SHORT_E2E)
    asset = _asset(db, run, "seg-1", "image", 1, "review_pending")

    with pytest.raises(ValueError, match="only available for mock_series_scale"):
        apply_bulk_review_action(db, [asset.id], action="approve")

    assert db.query(VideoReviewRecord).filter_by(review_type="human").count() == 0
    db.refresh(asset)
    assert asset.status == "review_pending"


def test_bulk_approve_rejects_unpersisted_assets_without_mutating(db):
    _, _, run, _ = _production_context(db)
    asset = _asset(db, run, "seg-1", "image", 1, "review_pending", copy_status="registered")

    with pytest.raises(ValueError, match="persisted assets"):
        apply_bulk_review_action(db, [asset.id], action="approve")

    assert db.query(VideoReviewRecord).filter_by(review_type="human").count() == 0
    db.refresh(asset)
    assert asset.status == "review_pending"


def test_bulk_approve_rejects_non_review_pending_assets_without_mutating(db):
    _, _, run, _ = _production_context(db)
    asset = _asset(db, run, "seg-1", "image", 1, "failed")

    with pytest.raises(ValueError, match="review_pending assets"):
        apply_bulk_review_action(db, [asset.id], action="approve")

    assert db.query(VideoReviewRecord).filter_by(review_type="human").count() == 0
    db.refresh(asset)
    assert asset.status == "failed"


def test_bulk_review_rejects_final_video_assets(db):
    _, _, run, _ = _production_context(db)
    asset = _asset(db, run, "final", "final_video", 1, "review_pending")

    with pytest.raises(ValueError, match="manual final review"):
        apply_bulk_review_action(db, [asset.id], action="approve")


def test_bulk_review_rejects_mock_final_video_but_allows_mock_image_and_video(db):
    _, _, run, _ = _production_context(db, frame_ids=("seg-1", "seg-2", "final"))
    run.run_type = MOCK_SERIES_SCALE
    image = _asset(db, run, "seg-1", "image", 1, "review_pending")
    video = _asset(db, run, "seg-2", "video_segment", 1, "review_pending")
    final = _asset(db, run, "final", "final_video", 1, "review_pending")

    assert apply_bulk_review_action(db, [image.id], action="approve")["approved"] == 1
    assert apply_bulk_review_action(db, [video.id], action="approve")["approved"] == 1
    with pytest.raises(ValueError, match="manual final review"):
        apply_bulk_review_action(db, [final.id], action="approve")


def test_bulk_review_final_video_error_leaves_prior_asset_unchanged(db):
    _, _, run, _ = _production_context(db, frame_ids=("seg-1", "final"))
    image = _asset(db, run, "seg-1", "image", 1, "review_pending")
    final = _asset(db, run, "final", "final_video", 1, "review_pending")

    with pytest.raises(ValueError, match="manual final review"):
        apply_bulk_review_action(db, [image.id, final.id], action="approve")

    assert len(db.dirty) == 0
    assert len(db.new) == 0
    assert db.query(VideoReviewRecord).filter_by(review_type="human").count() == 0
    db.refresh(image)
    db.refresh(final)
    assert image.status == "review_pending"
    assert final.status == "review_pending"


def test_bulk_review_rejects_stale_final_video_without_mutating_prior_asset(db):
    _, _, run, _ = _production_context(db, frame_ids=("seg-1", "final"))
    image = _asset(db, run, "seg-1", "image", 1, "review_pending")
    stale_final = _asset(db, run, "final", "final_video", 1, "review_pending")
    latest_final = _asset(db, run, "final", "final_video", 2, "review_pending")

    with pytest.raises(ValueError, match="manual final review"):
        apply_bulk_review_action(db, [image.id, stale_final.id], action="approve")

    assert len(db.dirty) == 0
    assert len(db.new) == 0
    assert db.query(VideoReviewRecord).filter_by(review_type="human").count() == 0
    db.refresh(image)
    db.refresh(stale_final)
    db.refresh(latest_final)
    assert image.status == "review_pending"
    assert stale_final.status == "review_pending"
    assert latest_final.status == "review_pending"


def test_bulk_review_rejects_mixed_asset_types_for_same_run(db):
    _, _, run, _ = _production_context(db, frame_ids=("seg-1", "seg-2"))
    image = _asset(db, run, "seg-1", "image", 1, "review_pending")
    video = _asset(db, run, "seg-2", "video_segment", 1, "review_pending")

    with pytest.raises(ValueError, match="cannot mix asset types"):
        apply_bulk_review_action(db, [image.id, video.id], action="approve")


def test_bulk_review_mixed_type_error_leaves_prior_asset_unchanged(db):
    _, _, run, _ = _production_context(db, frame_ids=("seg-1", "seg-2"))
    image = _asset(db, run, "seg-1", "image", 1, "review_pending")
    video = _asset(db, run, "seg-2", "video_segment", 1, "review_pending")

    with pytest.raises(ValueError, match="cannot mix asset types"):
        apply_bulk_review_action(db, [image.id, video.id], action="approve")

    assert len(db.dirty) == 0
    assert len(db.new) == 0
    assert db.query(VideoReviewRecord).filter_by(review_type="human").count() == 0
    db.refresh(image)
    db.refresh(video)
    assert image.status == "review_pending"
    assert video.status == "review_pending"


def test_bulk_review_rejects_mixed_type_even_when_first_asset_is_stale(db):
    _, _, run, _ = _production_context(db, frame_ids=("seg-1", "seg-2"))
    stale_image = _asset(db, run, "seg-1", "image", 1, "review_pending")
    latest_image = _asset(db, run, "seg-1", "image", 2, "review_pending")
    video = _asset(db, run, "seg-2", "video_segment", 1, "review_pending")

    with pytest.raises(ValueError, match="cannot mix asset types"):
        apply_bulk_review_action(db, [stale_image.id, video.id], action="approve")

    assert len(db.dirty) == 0
    assert len(db.new) == 0
    assert db.query(VideoReviewRecord).filter_by(review_type="human").count() == 0
    db.refresh(stale_image)
    db.refresh(latest_image)
    db.refresh(video)
    assert stale_image.status == "review_pending"
    assert latest_image.status == "review_pending"
    assert video.status == "review_pending"


def test_bulk_review_skips_missing_assets(db):
    _, _, run, _ = _production_context(db)
    asset = _asset(db, run, "seg-1", "image", 1, "review_pending")

    result = apply_bulk_review_action(db, ["missing-asset", asset.id], action="approve")

    db.refresh(asset)
    assert result == {"approved": 1, "rejected": 0, "skipped_stale": 0}
    assert asset.status == "approved"


def test_bulk_review_ignores_duplicate_asset_ids(db):
    _, _, run, _ = _production_context(db)
    asset = _asset(db, run, "seg-1", "image", 1, "review_pending")

    result = apply_bulk_review_action(db, [asset.id, asset.id], action="approve")

    assert result == {"approved": 1, "rejected": 0, "skipped_stale": 0}
    assert db.query(VideoReviewRecord).filter_by(asset_id=asset.id, review_type="human").count() == 1


def test_retry_segment_creates_new_version_and_marks_old_superseded(db):
    _, _, _, shot = _production_context(db)
    previous = ProductionSegment(
        shot_plan_id=shot.id,
        segment_id="seg-prev",
        order_index=1,
        status="completed",
        duration_seconds=5,
        continuity_mode="continuous_action",
        version=1,
    )
    db.add(previous)
    db.flush()
    segment = ProductionSegment(
        shot_plan_id=shot.id,
        previous_segment_id=previous.id,
        segment_id="seg-a",
        order_index=2,
        status="failed",
        duration_seconds=6.5,
        continuity_mode="continuous_action",
        version=2,
        previous_end_frame_url="https://cdn.test/end.png",
        expected_end_state="Hero has crossed the room.",
        retry_count=1,
        image_prompt="Hero in the room",
        video_prompt="Hero walks forward",
        narration="The room is quiet.",
        reference_roles_json=[{"role": "character_anchor", "url": "https://cdn.test/char.png"}],
    )
    db.add(segment)
    db.commit()

    new_segment = retry_segment(db, segment.id)

    db.refresh(segment)
    assert segment.status == SEGMENT_SUPERSEDED
    assert new_segment.id != segment.id
    assert new_segment.shot_plan_id == segment.shot_plan_id
    assert new_segment.segment_id == segment.segment_id
    assert new_segment.order_index == segment.order_index
    assert new_segment.status == SEGMENT_RETRY_QUEUED
    assert new_segment.duration_seconds == segment.duration_seconds
    assert new_segment.continuity_mode == segment.continuity_mode
    assert new_segment.previous_segment_id == segment.previous_segment_id
    assert new_segment.previous_end_frame_url == segment.previous_end_frame_url
    assert new_segment.expected_end_state == segment.expected_end_state
    assert new_segment.version == segment.version + 1
    assert new_segment.retry_count == segment.retry_count + 1
    assert new_segment.image_prompt == segment.image_prompt
    assert new_segment.video_prompt == segment.video_prompt
    assert new_segment.narration == segment.narration
    assert new_segment.reference_roles_json == segment.reference_roles_json


def test_retry_segment_rejects_repeated_retry_of_superseded_segment(db):
    _, _, _, shot = _production_context(db)
    segment = ProductionSegment(
        shot_plan_id=shot.id,
        segment_id="seg-a",
        order_index=1,
        status="failed",
        duration_seconds=5,
        continuity_mode="continuous_action",
        version=1,
    )
    db.add(segment)
    db.commit()

    retry_segment(db, segment.id)

    with pytest.raises(ValueError, match="not retryable"):
        retry_segment(db, segment.id)


def test_retry_segment_raises_for_missing_segment(db):
    with pytest.raises(ValueError, match="Production segment not found"):
        retry_segment(db, "missing-segment")

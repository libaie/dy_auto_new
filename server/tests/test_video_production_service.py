import pytest

from app.db.models import Episode, Series, VideoProductionAsset, VideoProductionRun, VideoReviewRecord
from app.domains.video_production.video_production_service import (
    approve_asset,
    create_regenerated_image_asset,
    create_run_from_episode,
    latest_approved_assets_by_frame,
    mark_image_stage_assets,
)
from tests.video_production_control_plane_helpers import linked_segment_context


def _episode_with_storyboard(db):
    series = Series(title="Image Wedge", logline="Test", genre="drama", target_duration=60)
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={
            "frames": [{
                "frame_id": "frame-001",
                "image_prompt": "Prompt",
                "reference_urls": ["https://cdn.test/ref.png"],
                "duration": 5,
            }]
        },
    )
    db.add(episode)
    db.commit()
    return series, episode


def test_create_run_from_episode_copies_storyboard(db):
    series, episode = _episode_with_storyboard(db)

    run = create_run_from_episode(db, series.id, episode.id)

    assert run.status == "draft"
    assert run.current_stage == "storyboard_ready"
    assert run.storyboard_json["frames"][0]["frame_id"] == "frame-001"


def test_mark_image_stage_assets_creates_review_pending_assets(db):
    series, episode = _episode_with_storyboard(db)
    run = create_run_from_episode(db, series.id, episode.id)

    assets = mark_image_stage_assets(db, run, [{
        "frame_id": "frame-001",
        "asset_type": "image",
        "url": "https://cdn.test/image.png",
        "local_path": "output/image.png",
        "metadata": {},
    }], pixelle_task_id="stage-1")

    assert assets[0].status == "review_pending"
    assert assets[0].version == 1
    assert db.query(VideoProductionRun).filter_by(id=run.id).one().status == "image_review_pending"


def test_latest_approved_assets_uses_latest_version(db):
    series, episode = _episode_with_storyboard(db)
    run = create_run_from_episode(db, series.id, episode.id)
    old_asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="frame-001",
        asset_type="image",
        stage="image_generation",
        version=1,
        status="approved",
        url="old.png",
    )
    new_asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="frame-001",
        asset_type="image",
        stage="image_generation",
        version=2,
        status="review_pending",
        url="new.png",
    )
    db.add_all([old_asset, new_asset])
    db.commit()

    approved = latest_approved_assets_by_frame(db, run.id)

    assert approved == {}


def test_approve_asset_records_human_review(db):
    series, episode = _episode_with_storyboard(db)
    run = create_run_from_episode(db, series.id, episode.id)
    asset = mark_image_stage_assets(db, run, [{
        "frame_id": "frame-001",
        "asset_type": "image",
        "url": "https://cdn.test/image.png",
        "local_path": "output/image.png",
        "metadata": {},
    }], pixelle_task_id="stage-1")[0]
    asset.copy_status = "persisted"
    asset.checksum = "image-checksum"
    asset.storage_path = "output/image.png"
    db.commit()

    approve_asset(db, asset.id, reviewer_user_id="user-1", comment="looks good")

    db.refresh(asset)
    assert asset.status == "approved"
    assert latest_approved_assets_by_frame(db, run.id)["frame-001"].id == asset.id


def test_approve_asset_is_idempotent_for_already_approved_latest_asset(db):
    series, episode = _episode_with_storyboard(db)
    run = create_run_from_episode(db, series.id, episode.id)
    asset = mark_image_stage_assets(db, run, [{
        "frame_id": "frame-001",
        "asset_type": "image",
        "url": "https://cdn.test/image.png",
        "local_path": "output/image.png",
        "metadata": {},
    }], pixelle_task_id="stage-1")[0]
    asset.copy_status = "persisted"
    asset.checksum = "image-checksum"
    asset.storage_path = "output/image.png"
    db.commit()

    first = approve_asset(db, asset.id, reviewer_user_id="user-1", comment="auto approved")
    second = approve_asset(db, asset.id, reviewer_user_id="user-1", comment="clicked stale approve")

    assert first.id == second.id == asset.id
    assert second.status == "approved"
    assert db.query(VideoReviewRecord).filter_by(
        asset_id=asset.id,
        review_type="human",
        status="approved",
    ).count() == 1


def test_approve_linked_image_asset_promotes_segment_status(db):
    ctx = linked_segment_context(db, segment_status="image_review_pending")
    asset = ctx["asset"]
    segment = ctx["segment"]
    asset.status = "review_pending"
    asset.copy_status = "persisted"
    asset.checksum = "image-checksum"
    asset.storage_path = "output/image.png"
    db.commit()

    approve_asset(db, asset.id, reviewer_user_id="user-1", comment="image ok")

    db.refresh(segment)
    assert segment.status == "image_approved"


def test_approve_linked_video_asset_promotes_segment_status(db):
    ctx = linked_segment_context(db, segment_status="video_review_pending")
    asset = ctx["asset"]
    segment = ctx["segment"]
    asset.asset_type = "video_segment"
    asset.stage = "video_generation"
    asset.status = "review_pending"
    asset.copy_status = "persisted"
    asset.checksum = "video-checksum"
    asset.storage_path = "output/video.mp4"
    db.commit()

    approve_asset(db, asset.id, reviewer_user_id="user-1", comment="video ok")

    db.refresh(segment)
    assert segment.status == "video_approved"


def test_regeneration_marks_old_asset_and_creates_next_version(db):
    series, episode = _episode_with_storyboard(db)
    run = create_run_from_episode(db, series.id, episode.id)
    asset = mark_image_stage_assets(db, run, [{
        "frame_id": "frame-001",
        "asset_type": "image",
        "url": "https://cdn.test/v1.png",
        "local_path": "output/v1.png",
        "metadata": {},
    }], pixelle_task_id="stage-1")[0]

    new_asset = create_regenerated_image_asset(db, asset.id, {
        "url": "https://cdn.test/v2.png",
        "local_path": "output/v2.png",
        "storage_path": "output/v2.png",
        "checksum": "sha256-v2",
        "copy_status": "persisted",
        "metadata": {},
    })

    db.refresh(asset)
    assert asset.status == "regenerating"
    assert new_asset.version == 2
    assert new_asset.status == "review_pending"

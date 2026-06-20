from fastapi.testclient import TestClient

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
from app.main import app

client = TestClient(app)


def _linked_asset(
    db,
    *,
    run_id=None,
    production_segment_id=None,
    version=1,
    is_latest=True,
    asset_type="image",
):
    if run_id and production_segment_id:
        run = db.query(VideoProductionRun).filter_by(id=run_id).one()
        segment = db.query(ProductionSegment).filter_by(id=production_segment_id).one()
        episode = db.query(Episode).filter_by(id=run.episode_id).one()
    else:
        series = Series(title="Review Latest", logline="Review", genre="drama")
        db.add(series)
        db.flush()
        episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
        db.add(episode)
        db.flush()
        plan = ProductionPlan(series_id=series.id, status="ready", active_version=1)
        db.add(plan)
        db.flush()
        production_episode = ProductionEpisode(plan_id=plan.id, episode_id=episode.id, order_index=1, status="ready")
        db.add(production_episode)
        db.flush()
        scene = ProductionScene(episode_plan_id=production_episode.id, scene_id="scene-1", order_index=1, status="ready")
        db.add(scene)
        db.flush()
        shot = ProductionShot(scene_plan_id=scene.id, shot_id="shot-1", order_index=1, status="ready")
        db.add(shot)
        db.flush()
        segment = ProductionSegment(
            shot_plan_id=shot.id,
            segment_id="shot-1-seg-01",
            order_index=1,
            status="planned",
            image_prompt="image",
            video_prompt="video",
        )
        db.add(segment)
        db.flush()
        run = VideoProductionRun(
            series_id=series.id,
            episode_id=episode.id,
            production_plan_id=plan.id,
            production_episode_id=production_episode.id,
            production_link_status="linked",
            status="image_review_pending",
            current_stage="image_review",
        )
        db.add(run)
        db.flush()

    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id=segment.id,
        asset_type=asset_type,
        stage="image_generation" if asset_type == "image" else "video_rendering",
        url=f"https://cdn.test/{segment.id}-{asset_type}-{version}.png",
        version=version,
        status="review_pending",
        production_segment_id=segment.id,
        target_type="production_segment",
        target_id=segment.id,
        source_version=segment.version,
        is_latest=is_latest,
        copy_status="persisted",
        checksum=f"checksum-{asset_type}-{version}",
        storage_path=f"output/{segment.id}-{asset_type}-{version}.png",
    )
    db.add(asset)
    db.commit()
    return asset


def test_human_review_snapshots_asset_target_fields(db):
    from app.domains.video_production.video_production_service import approve_asset

    asset = _linked_asset(db, version=2, is_latest=True)

    approve_asset(db, asset.id, reviewer_user_id="reviewer-1", comment="ok")

    review = db.query(VideoReviewRecord).filter_by(asset_id=asset.id, review_type="human").one()
    assert review.target_type == asset.target_type
    assert review.target_id == asset.target_id
    assert review.production_segment_id == asset.production_segment_id
    assert review.asset_version == asset.version
    assert review.is_latest_asset_review is True


def test_stale_asset_approval_returns_named_conflict(db):
    old_asset = _linked_asset(db, version=1, is_latest=False)
    _linked_asset(
        db,
        run_id=old_asset.run_id,
        production_segment_id=old_asset.production_segment_id,
        version=2,
        is_latest=True,
    )

    resp = client.post(f"/api/video-production/assets/{old_asset.id}/review", json={"action": "approve"})

    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "STALE_ASSET_VERSION"


def test_review_rejects_asset_that_is_not_persisted(db):
    asset = _linked_asset(db, version=1, is_latest=True)
    asset.copy_status = "registered"
    asset.checksum = None
    asset.storage_path = None
    db.commit()

    response = client.post(f"/api/video-production/assets/{asset.id}/review", json={"action": "approve"})

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "ASSET_STORAGE_FAILED"
    db.refresh(asset)
    assert asset.status == "review_pending"


def test_review_rejects_persisted_asset_missing_storage_path(db):
    asset = _linked_asset(db, version=1, is_latest=True)
    asset.copy_status = "persisted"
    asset.checksum = "checksum-without-storage-path"
    asset.storage_path = None
    asset.local_path = "output/local-only.png"
    db.commit()

    response = client.post(f"/api/video-production/assets/{asset.id}/review", json={"action": "approve"})

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "ASSET_STORAGE_FAILED"
    db.refresh(asset)
    assert asset.status == "review_pending"


def test_review_rejects_asset_that_is_not_review_pending(db):
    asset = _linked_asset(db, version=1, is_latest=True)
    asset.status = "generated"
    db.commit()

    response = client.post(f"/api/video-production/assets/{asset.id}/review", json={"action": "approve"})

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "REVIEW_GATE_BLOCKED"
    db.refresh(asset)
    assert asset.status == "generated"


def test_final_video_review_rejects_asset_that_is_not_persisted(db):
    asset = _linked_asset(db, version=1, is_latest=True, asset_type="final_video")
    run = db.query(VideoProductionRun).filter_by(id=asset.run_id).one()
    run.status = "final_review_pending"
    run.current_stage = "final_review"
    asset.copy_status = "registered"
    asset.checksum = None
    asset.storage_path = None
    db.commit()

    response = client.post(f"/api/video-production/assets/{asset.id}/review", json={"action": "approve"})

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "ASSET_STORAGE_FAILED"
    db.refresh(asset)
    assert asset.status == "review_pending"


def test_final_video_review_rejects_persisted_asset_missing_storage_path(db):
    asset = _linked_asset(db, version=1, is_latest=True, asset_type="final_video")
    run = db.query(VideoProductionRun).filter_by(id=asset.run_id).one()
    run.status = "final_review_pending"
    run.current_stage = "final_review"
    asset.copy_status = "persisted"
    asset.checksum = "checksum-without-storage-path"
    asset.storage_path = None
    asset.local_path = "output/local-only-final.mp4"
    db.commit()

    response = client.post(f"/api/video-production/assets/{asset.id}/review", json={"action": "approve"})

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "ASSET_STORAGE_FAILED"
    db.refresh(asset)
    assert asset.status == "review_pending"

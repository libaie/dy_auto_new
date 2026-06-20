from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import (
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    VideoProductionAsset,
    VideoProductionRun,
)
from app.domains.video_production.production_queue_service import enqueue_job


def get_retry_impact(db: Session, segment_id: str) -> dict:
    segment = db.query(ProductionSegment).filter(ProductionSegment.id == segment_id).first()
    if not segment:
        raise ValueError("Production segment not found")
    downstream = db.query(ProductionSegment).filter(ProductionSegment.previous_segment_id == segment.id).all()
    old_latest = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.production_segment_id == segment.id,
        VideoProductionAsset.is_latest.is_(True),
    ).all()
    allowed = segment.status in {"failed", "failed_retryable", "retry_queued"}
    return {
        "current_segment_version": segment.version,
        "target_new_version": segment.version + 1,
        "affected_downstream_segments": [
            {"id": item.id, "segment_id": item.segment_id, "continuity_mode": item.continuity_mode}
            for item in downstream
        ],
        "old_latest_assets": [
            {"id": item.id, "asset_type": item.asset_type, "version": item.version}
            for item in old_latest
        ],
        "estimated_extra_cost": 0.0,
        "estimate_status": "unknown",
        "unknown_estimate_reasons": ["pricing metadata unavailable"],
        "allowed": allowed,
    }


def retry_segment_with_impact(db: Session, segment_id: str) -> ProductionSegment:
    impact = get_retry_impact(db, segment_id)
    if not impact["allowed"]:
        raise ValueError("Production segment is not retryable")

    old = db.query(ProductionSegment).filter(ProductionSegment.id == segment_id).with_for_update().first()
    if not old:
        raise ValueError("Production segment not found")

    db.query(VideoProductionAsset).filter(
        VideoProductionAsset.production_segment_id == old.id,
        VideoProductionAsset.is_latest.is_(True),
    ).update({"is_latest": False}, synchronize_session=False)
    old.status = "superseded"
    new_segment = ProductionSegment(
        shot_plan_id=old.shot_plan_id,
        previous_segment_id=old.previous_segment_id,
        segment_id=old.segment_id,
        order_index=old.order_index,
        status="retry_queued",
        duration_seconds=old.duration_seconds,
        continuity_mode=old.continuity_mode,
        version=old.version + 1,
        previous_end_frame_url=old.previous_end_frame_url,
        expected_end_state=old.expected_end_state,
        retry_count=old.retry_count + 1,
        image_prompt=old.image_prompt,
        video_prompt=old.video_prompt,
        narration=old.narration,
        reference_roles_json=old.reference_roles_json or [],
    )
    db.add(new_segment)
    db.commit()
    db.refresh(new_segment)
    _enqueue_retry_stage_job(db, new_segment)
    db.refresh(new_segment)
    return new_segment


def _enqueue_retry_stage_job(db: Session, segment: ProductionSegment) -> None:
    run = _run_for_segment(db, segment)
    if not run:
        return
    stage = _retry_stage_for_segment(db, run, segment)
    enqueue_job(
        db,
        run.production_plan_id,
        "production_segment",
        segment.id,
        stage,
        f"{run.id}:{segment.id}:{stage}:v{segment.version}",
        priority=25,
    )
    if stage == "video_generation":
        run.status = "video_batch_running"
        run.current_stage = "video_rendering"
    else:
        run.status = "image_batch_running"
        run.current_stage = "image_generation"
    run.updated_at = bj_now()
    db.commit()


def _run_for_segment(db: Session, segment: ProductionSegment) -> VideoProductionRun | None:
    row = (
        db.query(VideoProductionRun)
        .join(ProductionScene, VideoProductionRun.production_episode_id == ProductionScene.episode_plan_id)
        .join(ProductionShot, ProductionShot.scene_plan_id == ProductionScene.id)
        .filter(ProductionShot.id == segment.shot_plan_id)
        .first()
    )
    return row


def _retry_stage_for_segment(db: Session, run: VideoProductionRun, segment: ProductionSegment) -> str:
    del db, run, segment
    return "image_generation"

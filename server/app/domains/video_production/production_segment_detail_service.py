from sqlalchemy.orm import Session

from app.db.models.video_production import (
    ProductionEpisode,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    VideoProductionAsset,
    VideoReviewRecord,
)


def _asset_payload(asset: VideoProductionAsset | None) -> dict | None:
    if not asset:
        return None
    return {
        "id": asset.id,
        "asset_type": asset.asset_type,
        "version": asset.version,
        "is_latest": asset.is_latest,
        "status": asset.status,
        "url": asset.url,
        "provider_task_id": asset.provider_task_id or asset.pixelle_task_id,
        "prompt_hash": asset.prompt_hash,
        "source_version": asset.source_version,
    }


def get_segment_detail(db: Session, segment_id: str, history_limit: int = 10) -> dict:
    segment = db.query(ProductionSegment).filter(ProductionSegment.id == segment_id).first()
    if not segment:
        raise ValueError("Production segment not found")
    shot = db.query(ProductionShot).filter(ProductionShot.id == segment.shot_plan_id).one()
    scene = db.query(ProductionScene).filter(ProductionScene.id == shot.scene_plan_id).one()
    episode = db.query(ProductionEpisode).filter(ProductionEpisode.id == scene.episode_plan_id).one()
    assets = (
        db.query(VideoProductionAsset)
        .filter(VideoProductionAsset.production_segment_id == segment.id)
        .order_by(VideoProductionAsset.asset_type.asc(), VideoProductionAsset.version.desc())
        .limit(max(1, int(history_limit or 10)) * 2)
        .all()
    )
    latest = {}
    history = {"image": [], "video_segment": []}
    for asset in assets:
        if asset.asset_type in history:
            history[asset.asset_type].append(_asset_payload(asset))
        if asset.is_latest and asset.asset_type not in latest:
            latest[asset.asset_type] = _asset_payload(asset)

    reviews = (
        db.query(VideoReviewRecord)
        .filter(VideoReviewRecord.production_segment_id == segment.id)
        .order_by(VideoReviewRecord.created_at.desc())
        .limit(max(1, int(history_limit or 10)))
        .all()
    )
    return {
        "segment": {
            "id": segment.id,
            "segment_id": segment.segment_id,
            "status": segment.status,
            "version": segment.version,
            "duration_seconds": segment.duration_seconds,
            "continuity_mode": segment.continuity_mode,
            "image_prompt": segment.image_prompt,
            "video_prompt": segment.video_prompt,
            "narration": segment.narration,
            "reference_roles": segment.reference_roles_json or [],
        },
        "path": {
            "plan_id": episode.plan_id,
            "episode_plan_id": episode.id,
            "scene_id": scene.id,
            "shot_id": shot.id,
        },
        "latest_assets": {"image": latest.get("image"), "video_segment": latest.get("video_segment")},
        "asset_history": history,
        "reviews": [
            {
                "id": row.id,
                "status": row.status,
                "review_type": row.review_type,
                "asset_version": row.asset_version,
            }
            for row in reviews
        ],
        "allowed_actions": ["retry"] if segment.status in {"failed", "failed_retryable", "retry_queued"} else [],
        "repair": None,
    }

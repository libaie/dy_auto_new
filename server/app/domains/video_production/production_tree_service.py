from collections import defaultdict

from sqlalchemy.orm import Session

from app.db.models.video_production import ProductionEpisode, ProductionPlan, ProductionScene, ProductionShot
from app.db_models import (
    ProductionJob,
    ProductionSegment,
    VideoProductionAsset,
)
from app.domains.video_production.production_status import (
    JOB_LEASED,
    JOB_QUEUED,
    JOB_RETRY_WAIT,
    JOB_RUNNING,
    JOB_BLOCKED,
    SEGMENT_BLOCKED_BY_REVIEW,
    SEGMENT_IMAGE_QUEUED,
    SEGMENT_IMAGE_REVIEW_PENDING,
    SEGMENT_IMAGE_RUNNING,
    SEGMENT_VIDEO_QUEUED,
    SEGMENT_VIDEO_REVIEW_PENDING,
    SEGMENT_VIDEO_RUNNING,
)


def _normalize_page(page: int, page_size: int) -> tuple[int, int]:
    return max(1, int(page or 1)), min(max(1, int(page_size or 50)), 100)


def _plan_payload(plan: ProductionPlan) -> dict:
    return {
        "id": plan.id,
        "series_id": plan.series_id,
        "status": plan.status,
        "current_cost": plan.current_cost,
        "budget_limit": plan.budget_limit,
    }


def _episode_payload(episode: ProductionEpisode, scenes: list[dict]) -> dict:
    return {
        "id": episode.id,
        "episode_id": episode.episode_id,
        "order_index": episode.order_index,
        "status": episode.status,
        "target_duration_seconds": episode.target_duration_seconds,
        "scenes": scenes,
    }


def _scene_payload(scene: ProductionScene, shots: list[dict]) -> dict:
    return {
        "id": scene.id,
        "scene_id": scene.scene_id,
        "order_index": scene.order_index,
        "status": scene.status,
        "location_summary": scene.location_summary,
        "shots": shots,
    }


def _shot_payload(shot: ProductionShot, segments: list[dict]) -> dict:
    return {
        "id": shot.id,
        "shot_id": shot.shot_id,
        "order_index": shot.order_index,
        "status": shot.status,
        "duration_seconds": shot.duration_seconds,
        "segments": segments,
    }


def _asset_payload(asset: VideoProductionAsset) -> dict:
    return {
        "id": asset.id,
        "asset_type": asset.asset_type,
        "stage": asset.stage,
        "status": asset.status,
        "url": asset.url,
        "thumbnail_url": asset.thumbnail_url,
        "version": asset.version,
        "copy_status": asset.copy_status,
        "storage_path": asset.storage_path,
        "checksum": asset.checksum,
    }


def _job_payload(job: ProductionJob) -> dict:
    return {
        "id": job.id,
        "stage": job.stage,
        "status": job.status,
        "provider_task_id": job.provider_task_id,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "retryable": job.retryable,
        "attempt_count": job.attempt_count,
    }


def _segment_payload(
    segment: ProductionSegment,
    jobs_by_segment: dict[str, list[ProductionJob]] | None = None,
    latest_assets_by_segment: dict[str, dict[str, VideoProductionAsset]] | None = None,
) -> dict:
    jobs = {
        job.stage: _job_payload(job)
        for job in (jobs_by_segment or {}).get(segment.id, [])
    }
    latest_assets = {
        asset_type: _asset_payload(asset)
        for asset_type, asset in (latest_assets_by_segment or {}).get(segment.id, {}).items()
    }
    status = _effective_segment_status(segment, list(jobs.values()), latest_assets)
    return {
        "id": segment.id,
        "segment_id": segment.segment_id,
        "status": status,
        "stored_status": segment.status,
        "duration_seconds": segment.duration_seconds,
        "continuity_mode": segment.continuity_mode,
        "version": segment.version,
        "jobs": jobs,
        "latest_assets": latest_assets,
    }


def _effective_segment_status(
    segment: ProductionSegment,
    jobs: list[dict],
    latest_assets: dict[str, dict],
) -> str:
    by_stage = {job["stage"]: job["status"] for job in jobs}
    if JOB_BLOCKED in set(by_stage.values()):
        return SEGMENT_BLOCKED_BY_REVIEW
    if segment.status != "planned":
        return segment.status
    if latest_assets.get("video_segment"):
        return SEGMENT_VIDEO_REVIEW_PENDING
    if latest_assets.get("image"):
        return SEGMENT_IMAGE_REVIEW_PENDING
    if by_stage.get("video_generation") in {JOB_LEASED, JOB_RUNNING}:
        return SEGMENT_VIDEO_RUNNING
    if by_stage.get("video_generation") in {JOB_QUEUED, JOB_RETRY_WAIT}:
        return SEGMENT_VIDEO_QUEUED
    if by_stage.get("image_generation") in {JOB_LEASED, JOB_RUNNING}:
        return SEGMENT_IMAGE_RUNNING
    if by_stage.get("image_generation") in {JOB_QUEUED, JOB_RETRY_WAIT}:
        return SEGMENT_IMAGE_QUEUED
    return segment.status


def get_run_tree(
    db: Session,
    plan_id: str,
    page: int = 1,
    page_size: int = 50,
    status: str | None = None,
    run_id: str | None = None,
) -> dict:
    plan = db.query(ProductionPlan).filter(ProductionPlan.id == plan_id).first()
    if not plan:
        raise ValueError("Production plan not found")

    page, page_size = _normalize_page(page, page_size)
    status_filter = status.strip() if status else None

    segment_query = db.query(ProductionSegment).join(
        ProductionShot,
        ProductionSegment.shot_plan_id == ProductionShot.id,
    ).join(
        ProductionScene,
        ProductionShot.scene_plan_id == ProductionScene.id,
    ).join(
        ProductionEpisode,
        ProductionScene.episode_plan_id == ProductionEpisode.id,
    ).filter(ProductionEpisode.plan_id == plan.id)
    if status_filter:
        segment_query = segment_query.filter(ProductionSegment.status == status_filter)

    total_segments = segment_query.count()
    paged_segments = segment_query.order_by(
        ProductionEpisode.order_index.asc(),
        ProductionScene.order_index.asc(),
        ProductionShot.order_index.asc(),
        ProductionSegment.order_index.asc(),
        ProductionSegment.id.asc(),
    ).offset((page - 1) * page_size).limit(page_size).all()
    segment_ids = [segment.id for segment in paged_segments]
    jobs_by_segment = _jobs_by_segment(db, plan.id, segment_ids)
    latest_assets_by_segment = _latest_assets_by_segment(db, segment_ids, run_id=run_id)

    shot_ids = list({segment.shot_plan_id for segment in paged_segments})
    shots = db.query(ProductionShot).filter(
        ProductionShot.id.in_(shot_ids),
    ).order_by(ProductionShot.order_index.asc(), ProductionShot.id.asc()).all() if shot_ids else []

    scene_ids = list({shot.scene_plan_id for shot in shots})
    scenes = db.query(ProductionScene).filter(
        ProductionScene.id.in_(scene_ids),
    ).order_by(ProductionScene.order_index.asc(), ProductionScene.id.asc()).all() if scene_ids else []

    episode_ids = list({scene.episode_plan_id for scene in scenes})
    episodes = db.query(ProductionEpisode).filter(
        ProductionEpisode.id.in_(episode_ids),
    ).order_by(ProductionEpisode.order_index.asc(), ProductionEpisode.id.asc()).all() if episode_ids else []

    scenes_by_episode: dict[str, list[ProductionScene]] = defaultdict(list)
    for scene in scenes:
        scenes_by_episode[scene.episode_plan_id].append(scene)

    shots_by_scene: dict[str, list[ProductionShot]] = defaultdict(list)
    for shot in shots:
        shots_by_scene[shot.scene_plan_id].append(shot)

    segments_by_shot: dict[str, list[ProductionSegment]] = defaultdict(list)
    for segment in paged_segments:
        segments_by_shot[segment.shot_plan_id].append(segment)

    episode_payloads = []
    for episode in episodes:
        scene_payloads = []
        for scene in scenes_by_episode.get(episode.id, []):
            shot_payloads = [
                _shot_payload(
                    shot,
                    [
                        _segment_payload(segment, jobs_by_segment, latest_assets_by_segment)
                        for segment in segments_by_shot.get(shot.id, [])
                    ],
                )
                for shot in shots_by_scene.get(scene.id, [])
            ]
            scene_payloads.append(_scene_payload(scene, shot_payloads))
        episode_payloads.append(_episode_payload(episode, scene_payloads))

    repair_nodes = _repair_nodes(db, plan.id)
    return {
        "plan": _plan_payload(plan),
        "episodes": episode_payloads,
        "nodes": repair_nodes,
        "total_segments": total_segments,
        "page": page,
        "page_size": page_size,
    }


def _jobs_by_segment(db: Session, plan_id: str, segment_ids: list[str]) -> dict[str, list[ProductionJob]]:
    if not segment_ids:
        return {}
    rows = (
        db.query(ProductionJob)
        .filter(ProductionJob.plan_id == plan_id)
        .filter(ProductionJob.target_type.in_(("production_segment", "segment")))
        .filter(ProductionJob.target_id.in_(segment_ids))
        .order_by(ProductionJob.created_at.asc(), ProductionJob.id.asc())
        .all()
    )
    grouped: dict[str, list[ProductionJob]] = defaultdict(list)
    for row in rows:
        grouped[row.target_id].append(row)
    return grouped


def _latest_assets_by_segment(
    db: Session,
    segment_ids: list[str],
    *,
    run_id: str | None = None,
) -> dict[str, dict[str, VideoProductionAsset]]:
    if not segment_ids:
        return {}
    query = (
        db.query(VideoProductionAsset)
        .filter(VideoProductionAsset.production_segment_id.in_(segment_ids))
        .filter(VideoProductionAsset.is_latest.is_(True))
        .order_by(VideoProductionAsset.created_at.asc(), VideoProductionAsset.id.asc())
    )
    if run_id:
        query = query.filter(VideoProductionAsset.run_id == run_id)
    grouped: dict[str, dict[str, VideoProductionAsset]] = defaultdict(dict)
    for asset in query.all():
        grouped[asset.production_segment_id][asset.asset_type] = asset
    return grouped


def _repair_nodes(db: Session, plan_id: str) -> list[dict]:
    jobs = (
        db.query(ProductionJob)
        .filter(ProductionJob.plan_id == plan_id)
        .filter(ProductionJob.stage.like("agency_auto_repair%"))
        .all()
    )
    if not jobs:
        return []
    summary = {"total": len(jobs), "queued": 0, "running": 0, "completed": 0, "failed": 0, "manual_required": 0, "recheck_required": 0}
    for job in jobs:
        if job.status in summary:
            summary[job.status] += 1
        if job.status in {"leased", "running", "retry_wait"}:
            summary["running"] += 1
        if job.status in {"failed", "blocked"}:
            summary["manual_required"] += 1
    status = "failed" if summary["failed"] else ("running" if summary["running"] or summary["queued"] else "completed")
    return [{
        "id": f"repair:{plan_id}",
        "type": "agency_auto_repair",
        "label": "自动返修",
        "status": status,
        "summary": summary,
    }]

from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import VideoProductionAsset, VideoProductionRun


IMAGE_READY_STATUS = "image_approved"
VIDEO_READY_STATUS = "video_segments_approved"


def storyboard_frame_ids(run: VideoProductionRun) -> list[str]:
    frames = (run.storyboard_json or {}).get("frames") or []
    return [str(frame.get("frame_id") or frame.get("id") or f"frame-{index + 1:03d}") for index, frame in enumerate(frames)]


def latest_assets_by_frame(db: Session, run_id: str, asset_type: str) -> dict[str, VideoProductionAsset]:
    rows = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == run_id,
        VideoProductionAsset.asset_type == asset_type,
    ).order_by(VideoProductionAsset.frame_id.asc(), VideoProductionAsset.version.desc()).all()
    latest: dict[str, VideoProductionAsset] = {}
    for row in rows:
        latest.setdefault(row.frame_id, row)
    return latest


def missing_or_unapproved_frames(db: Session, run: VideoProductionRun, asset_type: str) -> list[str]:
    latest = latest_assets_by_frame(db, run.id, asset_type)
    missing: list[str] = []
    for frame_id in storyboard_frame_ids(run):
        asset = latest.get(frame_id)
        if not asset or asset.status != "approved":
            missing.append(frame_id)
    return missing


def assert_can_start_images(run: VideoProductionRun) -> None:
    if run.status not in {"draft", "storyboard_ready"}:
        raise ValueError("Image stage already started")
    if run.pixelle_stage_task_id:
        raise ValueError("Image stage already has a Pixelle task")


def assert_can_start_videos(db: Session, run: VideoProductionRun) -> None:
    if run.status == "video_batch_running":
        raise ValueError("Video stage already started")
    if run.status != IMAGE_READY_STATUS:
        raise ValueError("Video stage can start only after images are approved")
    missing = missing_or_unapproved_frames(db, run, "image")
    if missing:
        raise ValueError(f"Images not approved: {', '.join(missing)}")


def assert_can_compose(db: Session, run: VideoProductionRun) -> None:
    if run.status == "composing":
        raise ValueError("Compose stage already started")
    if run.status != VIDEO_READY_STATUS:
        raise ValueError("Compose can start only after video segments are approved")
    missing = missing_or_unapproved_frames(db, run, "video_segment")
    if missing:
        raise ValueError(f"Video segments not approved: {', '.join(missing)}")


def record_stage_task(run: VideoProductionRun, stage: str, task_id: str, status: str = "submitted") -> None:
    trace = dict(run.model_trace_json or {})
    stage_tasks = dict(trace.get("stage_tasks") or {})
    stage_tasks[stage] = {
        "task_id": task_id,
        "status": status,
        "updated_at": bj_now().isoformat(),
    }
    trace["stage_tasks"] = stage_tasks
    run.model_trace_json = trace


def recompute_run_gate(db: Session, run_id: str, asset_type: str) -> VideoProductionRun:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise ValueError("Run not found")
    missing = missing_or_unapproved_frames(db, run, asset_type)
    latest = latest_assets_by_frame(db, run.id, asset_type)
    latest_statuses = [latest[frame_id].status for frame_id in latest if latest.get(frame_id)]

    if asset_type == "image":
        run.current_stage = "image_review"
        if not missing:
            run.status = "image_approved"
        elif any(status == "rejected" for status in latest_statuses):
            run.status = "image_human_review_required"
        else:
            run.status = "image_review_pending"
    elif asset_type == "video_segment":
        run.current_stage = "video_review"
        if not missing:
            run.status = "video_segments_approved"
        elif any(status == "rejected" for status in latest_statuses):
            run.status = "video_human_review_required"
        else:
            run.status = "video_review_pending"
    else:
        raise ValueError(f"Unsupported gate asset type: {asset_type}")

    run.updated_at = bj_now()
    db.commit()
    db.refresh(run)
    return run

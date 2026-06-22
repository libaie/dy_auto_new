"""视频生产业务域模块。

视频生产业务域，负责生产计划、作业队列、provider 执行、审核门禁和资产状态流转。本文件负责 video_production_state 相关业务规则、状态转换和外部系统边界。
"""

from sqlalchemy.orm import Session

from app.config import bj_now
from app.db.models.video_production import VideoProductionAsset, VideoProductionRun


IMAGE_READY_STATUS = "image_approved"
VIDEO_READY_STATUS = "video_segments_approved"
HUMAN_BLOCKING_ASSET_STATUSES = {"failed", "rejected"}


def storyboard_frame_ids(run: VideoProductionRun) -> list[str]:
    """业务函数：处理 storyboard_frame_ids 对应的业务流程、校验或数据转换。

    入参：run 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    frames = (run.storyboard_json or {}).get("frames") or []
    return [str(frame.get("frame_id") or frame.get("id") or f"frame-{index + 1:03d}") for index, frame in enumerate(frames)]


def _is_linked_run(run: VideoProductionRun) -> bool:
    """业务函数：处理 _is_linked_run 对应的业务流程、校验或数据转换。

    入参：run 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return bool(
        run.production_plan_id
        and run.production_episode_id
        and run.production_link_status == "linked"
    )


def production_segment_frame_ids(db: Session, run: VideoProductionRun) -> list[str]:
    """业务函数：处理 production_segment_frame_ids 对应的业务流程、校验或数据转换。

    入参：db、run 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    from app.db.models.video_production import ProductionScene, ProductionSegment, ProductionShot

    if not _is_linked_run(run):
        return storyboard_frame_ids(run)
    rows = (
        db.query(ProductionSegment)
        .join(ProductionShot, ProductionSegment.shot_plan_id == ProductionShot.id)
        .join(ProductionScene, ProductionShot.scene_plan_id == ProductionScene.id)
        .filter(ProductionScene.episode_plan_id == run.production_episode_id)
        .filter(ProductionSegment.status != "superseded")
        .order_by(
            ProductionScene.order_index.asc(),
            ProductionShot.order_index.asc(),
            ProductionSegment.order_index.asc(),
        )
        .all()
    )
    return [segment.id for segment in rows]


def latest_assets_by_frame(db: Session, run_id: str, asset_type: str) -> dict[str, VideoProductionAsset]:
    """业务函数：处理 latest_assets_by_frame 对应的业务流程、校验或数据转换。

    入参：db、run_id、asset_type 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    rows = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == run_id,
        VideoProductionAsset.asset_type == asset_type,
    ).order_by(VideoProductionAsset.frame_id.asc(), VideoProductionAsset.version.desc()).all()
    latest: dict[str, VideoProductionAsset] = {}
    for row in rows:
        latest.setdefault(row.frame_id, row)
    return latest


def missing_or_unapproved_frames(db: Session, run: VideoProductionRun, asset_type: str) -> list[str]:
    """业务函数：处理 missing_or_unapproved_frames 对应的业务流程、校验或数据转换。

    入参：db、run、asset_type 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    latest = latest_assets_by_frame(db, run.id, asset_type)
    missing: list[str] = []
    for frame_id in production_segment_frame_ids(db, run):
        asset = latest.get(frame_id)
        if not asset or asset.status != "approved":
            missing.append(frame_id)
    return missing


def assert_can_start_images(run: VideoProductionRun) -> None:
    """业务函数：处理 assert_can_start_images 对应的业务流程、校验或数据转换。

    入参：run 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if run.status not in {"draft", "storyboard_ready"}:
        raise ValueError("Image stage already started")
    if run.pixelle_stage_task_id:
        raise ValueError("Image stage already has a Pixelle task")


def assert_can_start_videos(db: Session, run: VideoProductionRun) -> None:
    """业务函数：处理 assert_can_start_videos 对应的业务流程、校验或数据转换。

    入参：db、run 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if run.status == "video_batch_running":
        raise ValueError("Video stage already started")
    video_gate_retry = (
        run.status == "video_human_review_required"
        and not db.query(VideoProductionAsset).filter(
            VideoProductionAsset.run_id == run.id,
            VideoProductionAsset.asset_type == "video_segment",
        ).first()
    )
    if run.status != IMAGE_READY_STATUS and not video_gate_retry:
        raise ValueError("Video stage can start only after images are approved")
    missing = missing_or_unapproved_frames(db, run, "image")
    if missing:
        raise ValueError(f"Images not approved: {', '.join(missing)}")


def assert_can_compose(db: Session, run: VideoProductionRun) -> None:
    """业务函数：处理 assert_can_compose 对应的业务流程、校验或数据转换。

    入参：db、run 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if run.status == "composing":
        raise ValueError("Compose stage already started")
    if run.status != VIDEO_READY_STATUS:
        raise ValueError("Compose can start only after video segments are approved")
    missing = missing_or_unapproved_frames(db, run, "video_segment")
    if missing:
        raise ValueError(f"Video segments not approved: {', '.join(missing)}")


def record_stage_task(run: VideoProductionRun, stage: str, task_id: str, status: str = "submitted") -> None:
    """业务函数：处理 record_stage_task 对应的业务流程、校验或数据转换。

    入参：run、stage、task_id、status 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
    """业务函数：处理 recompute_run_gate 对应的业务流程、校验或数据转换。

    入参：db、run_id、asset_type 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
        elif any(status in HUMAN_BLOCKING_ASSET_STATUSES for status in latest_statuses):
            run.status = "image_human_review_required"
        else:
            run.status = "image_review_pending"
    elif asset_type == "video_segment":
        run.current_stage = "video_review"
        if not missing:
            run.status = "video_segments_approved"
        elif any(status in HUMAN_BLOCKING_ASSET_STATUSES for status in latest_statuses):
            run.status = "video_human_review_required"
        else:
            run.status = "video_review_pending"
    else:
        raise ValueError(f"Unsupported gate asset type: {asset_type}")

    run.updated_at = bj_now()
    db.commit()
    db.refresh(run)
    return run

"""AI 视频系列业务域模块。

AI 视频系列业务域，负责系列策划、风格锁定、剧集资产范围和 LangChain 工具编排。本文件负责 status_read_model 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models.ai_video_series import (
    AITextArtifact,
    Episode,
    ProductionAuditEvent,
    ProductionJob,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    VideoProductionRun,
)
from app.domains.video_production.video_production_state import IMAGE_READY_STATUS, VIDEO_READY_STATUS


ACTIVE_JOB_STATUSES = {"queued", "leased", "running", "retry_wait"}
ACTIVE_RUN_STATUSES = {
    "running",
    "reference_generation_running",
    "image_batch_running",
    "video_batch_running",
    "composing",
    "final_review_pending",
}
COMPLETED_RUN_STATUSES = {"completed", "done"}
FAILED_RUN_STATUSES = {"failed", "cancelled", "canceled"}
REVIEW_RUN_STATUSES = {
    "image_review_pending",
    "video_review_pending",
    "final_review_pending",
    "image_human_review_required",
    "video_human_review_required",
}
READY_RUN_STATUS_TO_PRODUCTION_STATUS = {
    IMAGE_READY_STATUS: "ready_for_video",
    VIDEO_READY_STATUS: "ready_for_compose",
}


def build_episode_status_matrix(db: Session, series_id: str) -> dict[str, dict]:
    """业务函数：处理 build_episode_status_matrix 对应的业务流程、校验或数据转换。

    入参：db、series_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    episodes = (
        db.query(Episode)
        .filter(Episode.series_id == series_id)
        .order_by(Episode.episode_number.asc())
        .all()
    )
    episode_ids = [episode.id for episode in episodes]
    runs_by_episode = _latest_runs_by_episode(db, episode_ids)
    production_scope = _production_scope_by_run(db, list(runs_by_episode.values()))
    active_jobs_by_run = _active_jobs_by_run(db, list(runs_by_episode.values()), production_scope)
    audit_events_by_run = _audit_events_by_run(db, list(runs_by_episode.values()), production_scope)
    artifact_types_by_episode = _artifact_types_by_episode(db, episode_ids)

    matrix = {}
    for episode in episodes:
        run = runs_by_episode.get(episode.id)
        artifact_types = artifact_types_by_episode.get(episode.id, set())
        active_jobs = active_jobs_by_run.get(run.id, []) if run else []
        audit_events = audit_events_by_run.get(run.id, []) if run else []
        matrix[episode.id] = _episode_status_payload(
            episode,
            run,
            active_jobs,
            audit_events,
            artifact_types,
        )
    return matrix


def _latest_runs_by_episode(db: Session, episode_ids: list[str]) -> dict[str, VideoProductionRun]:
    """业务函数：处理 _latest_runs_by_episode 对应的业务流程、校验或数据转换。

    入参：db、episode_ids 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if not episode_ids:
        return {}
    runs = (
        db.query(VideoProductionRun)
        .filter(VideoProductionRun.episode_id.in_(episode_ids))
        .order_by(VideoProductionRun.created_at.desc())
        .all()
    )
    latest = {}
    for run in runs:
        latest.setdefault(run.episode_id, run)
    return latest


def _active_jobs_by_run(
    db: Session,
    runs: list[VideoProductionRun],
    production_scope: dict[str, dict[str, set[str]]],
) -> dict[str, list[ProductionJob]]:
    """业务函数：处理 _active_jobs_by_run 对应的业务流程、校验或数据转换。

    入参：db、runs、production_scope 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if not runs:
        return {}
    grouped = defaultdict(list)
    seen_job_ids = set()
    if hasattr(ProductionJob, "run_id"):
        run_ids = [run.id for run in runs]
        rows = (
            db.query(ProductionJob)
            .filter(ProductionJob.run_id.in_(run_ids))
            .filter(ProductionJob.status.in_(ACTIVE_JOB_STATUSES))
            .all()
        )
        for row in rows:
            seen_job_ids.add(row.id)
            grouped[row.run_id].append(row)

    plan_ids = [run.production_plan_id for run in runs if run.production_plan_id]
    if not plan_ids:
        return dict(grouped)
    rows = (
        db.query(ProductionJob)
        .filter(ProductionJob.plan_id.in_(plan_ids))
        .filter(ProductionJob.status.in_(ACTIVE_JOB_STATUSES))
        .all()
    )
    target_to_run = _target_to_run_id(runs, production_scope)
    for row in rows:
        if row.id in seen_job_ids:
            continue
        run_id = target_to_run.get((row.target_type, row.target_id))
        if run_id:
            grouped[run_id].append(row)
    return dict(grouped)


def _audit_events_by_run(
    db: Session,
    runs: list[VideoProductionRun],
    production_scope: dict[str, dict[str, set[str]]],
) -> dict[str, list[ProductionAuditEvent]]:
    """业务函数：处理 _audit_events_by_run 对应的业务流程、校验或数据转换。

    入参：db、runs、production_scope 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if not runs:
        return {}
    run_ids = [run.id for run in runs]
    runs_by_production_episode_id = {
        run.production_episode_id: run
        for run in runs
        if run.production_episode_id
    }
    filters = [ProductionAuditEvent.run_id.in_(run_ids)]
    if runs_by_production_episode_id:
        filters.append(ProductionAuditEvent.production_episode_id.in_(runs_by_production_episode_id))
    segment_ids = set().union(*[
        scope.get("production_segment", set())
        for scope in production_scope.values()
    ]) if production_scope else set()
    if segment_ids:
        filters.append(ProductionAuditEvent.production_segment_id.in_(segment_ids))
    rows = (
        db.query(ProductionAuditEvent)
        .filter(or_(*filters))
        .order_by(ProductionAuditEvent.created_at.desc())
        .all()
    )
    grouped = defaultdict(list)
    segment_to_run = {
        segment_id: run_id
        for run_id, scope in production_scope.items()
        for segment_id in scope.get("production_segment", set())
    }
    for row in rows:
        if row.run_id:
            grouped[row.run_id].append(row)
            continue
        run = runs_by_production_episode_id.get(row.production_episode_id)
        if run:
            grouped[run.id].append(row)
            continue
        run_id = segment_to_run.get(row.production_segment_id)
        if run_id:
            grouped[run_id].append(row)
    return dict(grouped)


def _production_scope_by_run(db: Session, runs: list[VideoProductionRun]) -> dict[str, dict[str, set[str]]]:
    """业务函数：处理 _production_scope_by_run 对应的业务流程、校验或数据转换。

    入参：db、runs 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    scope = {
        run.id: {
            "episode": {run.episode_id} if run.episode_id else set(),
            "production_episode": {run.production_episode_id} if run.production_episode_id else set(),
            "production_scene": set(),
            "production_shot": set(),
            "production_segment": set(),
        }
        for run in runs
    }
    production_episode_to_run = {
        run.production_episode_id: run.id
        for run in runs
        if run.production_episode_id
    }
    if not production_episode_to_run:
        return scope

    scenes = (
        db.query(ProductionScene)
        .filter(ProductionScene.episode_plan_id.in_(production_episode_to_run))
        .all()
    )
    scene_to_run = {}
    for scene in scenes:
        run_id = production_episode_to_run.get(scene.episode_plan_id)
        if run_id:
            scope[run_id]["production_scene"].add(scene.id)
            scene_to_run[scene.id] = run_id

    shots = (
        db.query(ProductionShot)
        .filter(ProductionShot.scene_plan_id.in_(scene_to_run))
        .all()
        if scene_to_run
        else []
    )
    shot_to_run = {}
    for shot in shots:
        run_id = scene_to_run.get(shot.scene_plan_id)
        if run_id:
            scope[run_id]["production_shot"].add(shot.id)
            shot_to_run[shot.id] = run_id

    segments = (
        db.query(ProductionSegment)
        .filter(ProductionSegment.shot_plan_id.in_(shot_to_run))
        .all()
        if shot_to_run
        else []
    )
    for segment in segments:
        run_id = shot_to_run.get(segment.shot_plan_id)
        if run_id:
            scope[run_id]["production_segment"].add(segment.id)

    return scope


def _target_to_run_id(
    runs: list[VideoProductionRun],
    production_scope: dict[str, dict[str, set[str]]],
) -> dict[tuple[str, str], str]:
    """业务函数：处理 _target_to_run_id 对应的业务流程、校验或数据转换。

    入参：runs、production_scope 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    target_to_run = {}
    for run in runs:
        for target_type, target_ids in production_scope.get(run.id, {}).items():
            for target_id in target_ids:
                target_to_run[(target_type, target_id)] = run.id
    return target_to_run


def _artifact_types_by_episode(db: Session, episode_ids: list[str]) -> dict[str, set[str]]:
    """业务函数：处理 _artifact_types_by_episode 对应的业务流程、校验或数据转换。

    入参：db、episode_ids 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if not episode_ids:
        return {}
    rows = (
        db.query(AITextArtifact.episode_id, AITextArtifact.artifact_type)
        .filter(AITextArtifact.episode_id.in_(episode_ids))
        .filter(AITextArtifact.status == "approved")
        .filter(AITextArtifact.artifact_type.in_(("episode_script", "storyboard")))
        .all()
    )
    grouped = defaultdict(set)
    for episode_id, artifact_type in rows:
        grouped[episode_id].add(artifact_type)
    return dict(grouped)


def _episode_status_payload(
    episode: Episode,
    run: VideoProductionRun | None,
    active_jobs: list[ProductionJob],
    audit_events: list[ProductionAuditEvent],
    artifact_types: set[str],
) -> dict:
    """业务函数：处理 _episode_status_payload 对应的业务流程、校验或数据转换。

    入参：episode、run、active_jobs、audit_events、artifact_types 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    has_script = "episode_script" in artifact_types or bool(episode.script_json)
    has_storyboard = "storyboard" in artifact_types or bool(episode.storyboard_json)
    payload = {
        "episode_id": episode.id,
        "episode_number": episode.episode_number,
        "has_episode_script": has_script,
        "has_storyboard": has_storyboard,
        "active_run_id": run.id if run else None,
        "active_job_count": len(active_jobs),
        "audit_event_count": len(audit_events),
        "latest_audit_event_type": audit_events[0].event_type if audit_events else None,
        "blocking_code": None,
    }
    if run:
        payload["latest_run_status"] = run.status
        payload["latest_run_stage"] = run.current_stage
    else:
        payload["latest_run_status"] = None
        payload["latest_run_stage"] = None

    if run and run.status in COMPLETED_RUN_STATUSES:
        payload["production_status"] = "completed"
    elif run and run.status in READY_RUN_STATUS_TO_PRODUCTION_STATUS:
        payload["production_status"] = READY_RUN_STATUS_TO_PRODUCTION_STATUS[run.status]
    elif run and run.status in REVIEW_RUN_STATUSES:
        payload["production_status"] = "blocked"
        payload["blocking_code"] = "RUN_REQUIRES_REVIEW"
    elif run and run.status in ACTIVE_RUN_STATUSES and active_jobs:
        payload["production_status"] = "producing"
    elif run and run.status in ACTIVE_RUN_STATUSES and not active_jobs:
        payload["production_status"] = "blocked"
        payload["blocking_code"] = "RUNNING_WITHOUT_ACTIVE_JOB"
    elif run and run.status in FAILED_RUN_STATUSES:
        payload["production_status"] = "blocked"
        payload["blocking_code"] = "RUN_FAILED"
    elif run:
        payload["production_status"] = "blocked"
        payload["blocking_code"] = "RUN_STATE_UNCLASSIFIED"
    elif has_script and has_storyboard:
        payload["production_status"] = "ready_for_production"
    else:
        payload["production_status"] = "not_started"
        payload["blocking_code"] = "NO_ACTIVE_RUN"
    return payload

"""视频生产业务域模块。

视频生产业务域，负责生产计划、作业队列、provider 执行、审核门禁和资产状态流转。本文件负责 mock_scale_scheduler_service 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

from math import ceil
from typing import Any

from sqlalchemy.orm import Session

from app.config import bj_now
from app.db.models.video_production import (
    ProductionEpisode,
    ProductionJob,
    ProductionPlan,
    ProductionPlanVersion,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    VideoProductionAsset,
    VideoProductionRun,
)
from app.db.models import (
    Episode,
    Series,
)
from app.domains.video_production.production_status import (
    JOB_COMPLETED,
    JOB_LEASED,
    JOB_QUEUED,
    PLAN_COMPLETED,
    PLAN_READY,
    PLAN_RUNNING,
    SEGMENT_COMPLETED,
    SEGMENT_PLANNED,
)
from app.domains.video_production.production_queue_service import claim_next_job, mark_job_completed
from app.domains.production_observability.production_observability_service import record_production_event
from app.domains.video_production.video_production_run_types import MOCK_SERIES_SCALE


DEFAULT_TARGET_DURATION_SECONDS = 240 * 60
MAX_ACCEPTED_TARGET_DURATION_SECONDS = 480 * 60
MOCK_SEGMENT_SECONDS = 60
MOCK_SCENE_SEGMENTS = 20
MOCK_JOB_STAGE = "mock_segment_render"
MOCK_PROVIDER_TASK_ID = "mock:provider-free"
MOCK_ASSET_URL_PREFIX = "mock://provider-free"


def _clean_prompt(prompt: str) -> str:
    """业务函数：处理 _clean_prompt 对应的业务流程、校验或数据转换。

    入参：prompt 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return " ".join((prompt or "").strip().split())


def _title_from_prompt(prompt: str, title: str | None) -> str:
    """业务函数：处理 _title_from_prompt 对应的业务流程、校验或数据转换。

    入参：prompt、title 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if title and title.strip():
        return title.strip()[:200]
    clean = _clean_prompt(prompt)
    return (clean[:80] or "Mock Scale Run")


def _target_duration(value: int | None) -> int:
    """业务函数：处理 _target_duration 对应的业务流程、校验或数据转换。

    入参：value 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    duration = int(value or DEFAULT_TARGET_DURATION_SECONDS)
    if duration <= 0:
        raise ValueError("target_duration_seconds must be positive")
    if duration > MAX_ACCEPTED_TARGET_DURATION_SECONDS:
        raise ValueError("mock_series_scale target_duration_seconds must be <= 28800 seconds")
    return duration


def _segment_durations(total_seconds: int) -> list[int]:
    """业务函数：处理 _segment_durations 对应的业务流程、校验或数据转换。

    入参：total_seconds 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    count = max(1, ceil(total_seconds / MOCK_SEGMENT_SECONDS))
    base = total_seconds // count
    remainder = total_seconds % count
    return [base + (1 if index < remainder else 0) for index in range(count)]


def _storyboard_frames(prompt: str, durations: list[int]) -> list[dict[str, Any]]:
    """业务函数：处理 _storyboard_frames 对应的业务流程、校验或数据转换。

    入参：prompt、durations 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    frames = []
    for index, duration in enumerate(durations, start=1):
        frames.append({
            "frame_id": f"mock-shot-{index:04d}",
            "scene_id": f"mock-scene-{ceil(index / MOCK_SCENE_SEGMENTS):03d}",
            "duration": duration,
            "image_prompt": f"Mock provider-free image beat {index}: {prompt}",
            "video_prompt": f"Mock provider-free video beat {index}: {prompt}",
            "narration": f"Mock narration beat {index}.",
            "action": f"Mock story beat {index}",
            "emotion": "neutral",
            "shot_type": "medium",
            "character_ids": [],
        })
    return frames


def _create_series_episode(db: Session, prompt: str, title: str, target_duration_seconds: int) -> tuple[Series, Episode, list[int]]:
    """业务函数：处理 _create_series_episode 对应的业务流程、校验或数据转换。

    入参：db、prompt、title、target_duration_seconds 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    durations = _segment_durations(target_duration_seconds)
    frames = _storyboard_frames(prompt, durations)
    series = Series(
        title=title,
        logline=prompt,
        genre="mock",
        total_episodes=1,
        target_duration=target_duration_seconds,
        mode="mock_scale",
        pilot_first=True,
        status="rendering",
        story_bible_json={
            "style_lock": {
                "locked": True,
                "version": 1,
                "source": MOCK_SERIES_SCALE,
                "provider_free": True,
            }
        },
    )
    db.add(series)
    db.flush()

    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Episode 1",
        status="storyboard_ready",
        duration_seconds=target_duration_seconds,
        storyboard_json={
            "source": MOCK_SERIES_SCALE,
            "provider_free": True,
            "frame_count": len(frames),
            "total_duration": target_duration_seconds,
            "frames": frames,
        },
    )
    db.add(episode)
    db.flush()
    return series, episode, durations


def _create_plan_tree(
    db: Session,
    *,
    series: Series,
    episode: Episode,
    prompt: str,
    durations: list[int],
    target_duration_seconds: int,
    budget_limit: float | None,
) -> tuple[ProductionPlan, ProductionEpisode, int]:
    """业务函数：处理 _create_plan_tree 对应的业务流程、校验或数据转换。

    入参：db、series、episode、prompt、durations、target_duration_seconds、budget_limit 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    plan = ProductionPlan(
        series_id=series.id,
        status=PLAN_READY,
        active_version=1,
        target_total_duration_seconds=target_duration_seconds,
        budget_limit=budget_limit,
        current_cost=0.0,
    )
    db.add(plan)
    db.flush()
    db.add(ProductionPlanVersion(
        plan_id=plan.id,
        version=1,
        style_lock_json=series.story_bible_json.get("style_lock", {}),
        model_config_snapshot_json={"provider_free": True},
        prompt_policy_json={
            "source": MOCK_SERIES_SCALE,
            "segment_seconds": MOCK_SEGMENT_SECONDS,
        },
    ))

    production_episode = ProductionEpisode(
        plan_id=plan.id,
        episode_id=episode.id,
        order_index=1,
        status=PLAN_READY,
        target_duration_seconds=target_duration_seconds,
    )
    db.add(production_episode)
    db.flush()

    scene: ProductionScene | None = None
    previous_segment: ProductionSegment | None = None
    for index, duration in enumerate(durations, start=1):
        if scene is None or (index - 1) % MOCK_SCENE_SEGMENTS == 0:
            scene_number = ceil(index / MOCK_SCENE_SEGMENTS)
            scene = ProductionScene(
                episode_plan_id=production_episode.id,
                scene_id=f"mock-scene-{scene_number:03d}",
                order_index=scene_number,
                status=PLAN_READY,
                location_summary=f"Mock scale scene {scene_number}",
            )
            db.add(scene)
            db.flush()

        shot_id = f"mock-shot-{index:04d}"
        shot = ProductionShot(
            scene_plan_id=scene.id,
            shot_id=shot_id,
            order_index=index,
            status=PLAN_READY,
            character_ids=[],
            action=f"Provider-free mock beat {index}: {prompt}",
            emotion="neutral",
            shot_type="medium",
            duration_seconds=duration,
        )
        db.add(shot)
        db.flush()

        segment = ProductionSegment(
            shot_plan_id=shot.id,
            previous_segment_id=previous_segment.id if previous_segment else None,
            segment_id=f"{shot_id}-seg-01",
            order_index=1,
            status=SEGMENT_PLANNED,
            duration_seconds=duration,
            continuity_mode="narrative_cut",
            version=1,
            image_prompt=f"Mock provider-free image prompt {index}: {prompt}",
            video_prompt=f"Mock provider-free video prompt {index}: {prompt}",
            narration=f"Mock narration beat {index}.",
            reference_roles_json=[],
        )
        db.add(segment)
        db.flush()
        previous_segment = segment

        db.add(ProductionJob(
            plan_id=plan.id,
            target_type="segment",
            target_id=segment.id,
            stage=MOCK_JOB_STAGE,
            status=JOB_QUEUED,
            provider_task_id=MOCK_PROVIDER_TASK_ID,
            attempt_count=0,
            max_attempts=1,
            priority=100,
            idempotency_key=f"{plan.id}:{segment.id}:{MOCK_JOB_STAGE}:v1",
            retryable=False,
        ))
    return plan, production_episode, len(durations)


def create_mock_scale_run(
    db: Session,
    *,
    prompt: str,
    title: str | None = None,
    target_duration_seconds: int | None = None,
    budget_limit: float | None = None,
) -> dict[str, Any]:
    """业务函数：处理 create_mock_scale_run 对应的业务流程、校验或数据转换。

    入参：db、prompt、title、target_duration_seconds、budget_limit 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    clean_prompt = _clean_prompt(prompt)
    duration = _target_duration(target_duration_seconds)
    series, episode, durations = _create_series_episode(
        db,
        clean_prompt,
        _title_from_prompt(clean_prompt, title),
        duration,
    )
    plan, production_episode, segment_count = _create_plan_tree(
        db,
        series=series,
        episode=episode,
        prompt=clean_prompt,
        durations=durations,
        target_duration_seconds=duration,
        budget_limit=budget_limit,
    )

    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="mock_scheduler_pending",
        current_stage="mock_scheduler",
        run_type=MOCK_SERIES_SCALE,
        production_plan_id=plan.id,
        production_episode_id=production_episode.id,
        production_link_status="linked",
        storyboard_json=episode.storyboard_json,
        model_trace_json={
            "source": MOCK_SERIES_SCALE,
            "provider_free": True,
            "provider_calls": 0,
            "target_duration_seconds": duration,
            "segment_count": segment_count,
            "job_count": segment_count,
        },
    )
    db.add(run)
    db.flush()
    record_production_event(
        db,
        event_type="run_type.assigned",
        run_id=run.id,
        production_plan_id=plan.id,
        production_episode_id=production_episode.id,
        payload={
            "run_type": MOCK_SERIES_SCALE,
            "source": MOCK_SERIES_SCALE,
            "mode": "mock_scale",
            "provider_calls": 0,
        },
    )
    db.commit()
    db.refresh(series)
    db.refresh(episode)
    db.refresh(plan)
    db.refresh(production_episode)
    db.refresh(run)
    return {
        "series": series,
        "episode": episode,
        "run": run,
        "plan": plan,
        "production_episode": production_episode,
        "segment_count": segment_count,
        "job_count": segment_count,
    }


def _next_mock_asset_version(db: Session, run_id: str, segment_id: str) -> int:
    """业务函数：处理 _next_mock_asset_version 对应的业务流程、校验或数据转换。

    入参：db、run_id、segment_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    latest = (
        db.query(VideoProductionAsset.version)
        .filter(
            VideoProductionAsset.run_id == run_id,
            VideoProductionAsset.production_segment_id == segment_id,
            VideoProductionAsset.asset_type == "video_segment",
        )
        .order_by(VideoProductionAsset.version.desc())
        .first()
    )
    return int(latest[0]) + 1 if latest else 1


def _register_mock_segment_asset(
    db: Session,
    *,
    run: VideoProductionRun,
    segment: ProductionSegment,
    job: ProductionJob,
    now,
) -> VideoProductionAsset:
    """业务函数：处理 _register_mock_segment_asset 对应的业务流程、校验或数据转换。

    入参：db、run、segment、job、now 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    existing = (
        db.query(VideoProductionAsset)
        .filter(
            VideoProductionAsset.run_id == run.id,
            VideoProductionAsset.production_segment_id == segment.id,
            VideoProductionAsset.asset_type == "video_segment",
            VideoProductionAsset.is_latest.is_(True),
        )
        .first()
    )
    if existing:
        return existing

    asset_url = f"{MOCK_ASSET_URL_PREFIX}/{run.id}/{segment.segment_id}.mp4"
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=run.episode_id,
        frame_id=segment.segment_id,
        asset_type="video_segment",
        stage=MOCK_JOB_STAGE,
        url=asset_url,
        duration_seconds=segment.duration_seconds,
        version=_next_mock_asset_version(db, run.id, segment.id),
        metadata_json={
            "source": MOCK_SERIES_SCALE,
            "provider_free": True,
            "job_id": job.id,
            "production_segment_id": segment.id,
            "note": "Provider-free mock asset for production-tree and scheduler verification.",
        },
        status="approved",
        pixelle_task_id=job.provider_task_id or MOCK_PROVIDER_TASK_ID,
        production_segment_id=segment.id,
        target_type="production_segment",
        target_id=segment.id,
        provider_task_id=job.provider_task_id or MOCK_PROVIDER_TASK_ID,
        storage_path=asset_url,
        source_url=asset_url,
        is_latest=True,
        copy_status="persisted",
        checksum=f"mock:{run.id}:{segment.id}:v1",
        size_bytes=0,
        created_at=now,
        updated_at=now,
    )
    db.add(asset)
    return asset


def advance_mock_scheduler(db: Session, run_id: str, limit: int = 25, lease_id: str = "mock-worker") -> dict[str, Any]:
    """业务函数：处理 advance_mock_scheduler 对应的业务流程、校验或数据转换。

    入参：db、run_id、limit、lease_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise ValueError("Video production run not found")
    if run.run_type != MOCK_SERIES_SCALE:
        raise ValueError("advance_mock_scheduler only accepts mock_series_scale runs")
    if not run.production_plan_id:
        raise ValueError("Mock scale run is not linked to a production plan")

    batch_size = max(0, int(limit or 0))
    now = bj_now()
    processed = 0
    processed_job_ids = []
    for _ in range(batch_size):
        job = claim_next_job(
            db,
            lease_id=lease_id,
            plan_id=run.production_plan_id,
            stage=MOCK_JOB_STAGE,
        )
        if not job:
            break
        if run.status != "completed":
            run.status = "mock_scheduler_running"
            run.current_stage = "mock_scheduler"
            run.started_at = run.started_at or now
            plan = db.query(ProductionPlan).filter(ProductionPlan.id == run.production_plan_id).first()
            if plan and plan.status == PLAN_READY:
                plan.status = PLAN_RUNNING
        try:
            completed_job = mark_job_completed(
                db,
                job.id,
                provider_task_id=job.provider_task_id or MOCK_PROVIDER_TASK_ID,
                allowed_statuses=(JOB_LEASED,),
                expected_lease_id=lease_id,
            )
        except ValueError:
            continue
        completed_job.attempt_count += 1
        completed_job.started_at = completed_job.started_at or now
        processed += 1
        processed_job_ids.append(completed_job.id)
        segment = db.query(ProductionSegment).filter(ProductionSegment.id == job.target_id).first()
        if segment:
            segment.status = SEGMENT_COMPLETED
            segment.updated_at = now
            _register_mock_segment_asset(db, run=run, segment=segment, job=completed_job, now=now)

    db.flush()
    remaining = (
        db.query(ProductionJob)
        .filter(
            ProductionJob.plan_id == run.production_plan_id,
            ProductionJob.stage == MOCK_JOB_STAGE,
            ProductionJob.status == JOB_QUEUED,
        )
        .count()
    )
    open_jobs = (
        db.query(ProductionJob)
        .filter(
            ProductionJob.plan_id == run.production_plan_id,
            ProductionJob.stage == MOCK_JOB_STAGE,
            ProductionJob.status != JOB_COMPLETED,
        )
        .count()
    )
    if open_jobs == 0:
        plan = db.query(ProductionPlan).filter(ProductionPlan.id == run.production_plan_id).first()
        production_episode = (
            db.query(ProductionEpisode)
            .filter(ProductionEpisode.id == run.production_episode_id)
            .first()
        )
        if run.status != "completed":
            run.status = "completed"
            run.current_stage = "completed"
            run.completed_at = now
        if plan:
            plan.status = PLAN_COMPLETED
        if production_episode:
            production_episode.status = PLAN_COMPLETED

    trace = dict(run.model_trace_json or {})
    trace["provider_calls"] = 0
    trace["last_advance"] = {
        "processed": processed,
        "remaining": remaining,
        "open_jobs": open_jobs,
        "job_ids": processed_job_ids,
    }
    run.model_trace_json = trace
    run.updated_at = now
    record_production_event(
        db,
        event_type="mock_scheduler.step_completed",
        run_id=run.id,
        production_plan_id=run.production_plan_id,
        production_episode_id=run.production_episode_id,
        payload={
            "run_type": run.run_type,
            "completed": open_jobs == 0,
            "remaining": remaining,
            "open_jobs": open_jobs,
            "job_ids": processed_job_ids,
            "provider_calls": 0,
            "provider_free": True,
        },
    )
    db.commit()
    db.refresh(run)
    return {
        "run": run,
        "processed": processed,
        "remaining": remaining,
        "open_jobs": open_jobs,
        "completed": open_jobs == 0,
    }

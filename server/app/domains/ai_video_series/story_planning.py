"""Story-planning queue and worker helpers for the AI video series domain."""

from datetime import datetime, timezone
import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.config import bj_now
from app.database import SessionLocal
from app.db.models.ai_video_series import ProductionJob, ProductionPlan, Series
from app.domains.ai_video_series.artifacts import completed_story_plan_payload
from app.domains.video_production.production_queue_service import claim_next_job, fail_job, mark_job_completed
from app.domains.video_production.production_status import (
    JOB_LEASED,
    JOB_QUEUED,
    JOB_RETRY_WAIT,
    JOB_RUNNING,
    PLAN_COMPLETED,
    PLAN_READY,
)
from app.domains.ai_video_series.series_planning_service import generate_series_story_plan


logger = logging.getLogger(__name__)

STORY_PLANNING_STAGE = "story_planning"
STORY_PLANNING_ACTIVE_JOB_STATUSES = (JOB_QUEUED, JOB_LEASED, JOB_RUNNING, JOB_RETRY_WAIT)
STORY_PLANNING_JOB_LEASE_SECONDS = 3600


class StoryPlanningDomainError(RuntimeError):
    def __init__(self, status_code: int, detail: object):
        self.status_code = status_code
        self.detail = detail
        super().__init__(str(detail))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def story_planning_in_progress_error() -> StoryPlanningDomainError:
    return StoryPlanningDomainError(409, {
        "code": "STORY_PLANNING_IN_PROGRESS",
        "message": "Story planning is already running for this series.",
    })


def active_story_plan_job(db: Session, series_id: str) -> ProductionJob | None:
    return (
        db.query(ProductionJob)
        .filter(ProductionJob.target_type == "series")
        .filter(ProductionJob.target_id == series_id)
        .filter(ProductionJob.stage == STORY_PLANNING_STAGE)
        .filter(ProductionJob.status.in_(STORY_PLANNING_ACTIVE_JOB_STATUSES))
        .order_by(ProductionJob.created_at.desc())
        .first()
    )


def set_story_planning_state(
    db: Session,
    series: Series,
    *,
    status: str,
    version: int | None = None,
    job_id: str | None = None,
    error: str | None = None,
    result: dict | None = None,
) -> dict:
    story_bible = dict(series.story_bible_json or {})
    current = dict(story_bible.get("story_planning") or {})
    if version is not None:
        current["version"] = version
    elif "version" not in current:
        current["version"] = 1
    current["status"] = status
    current["updated_at"] = _utc_now_iso()
    if job_id is not None:
        current["job_id"] = job_id
    if error is not None:
        current["error"] = error
    elif status in {"queued", "running", "completed", "fallback"}:
        current.pop("error", None)
    if result is not None:
        current["result"] = result
    if status in {"completed", "fallback", "failed"}:
        current["completed_at"] = _utc_now_iso()
    story_bible["story_planning"] = current
    series.story_bible_json = story_bible
    flag_modified(series, "story_bible_json")
    db.commit()
    db.refresh(series)
    return current


def enqueue_story_plan_job(db: Session, series: Series, version: int) -> ProductionJob:
    if active_story_plan_job(db, series.id):
        raise story_planning_in_progress_error()

    plan = ProductionPlan(
        series_id=series.id,
        status=PLAN_READY,
        active_version=1,
        target_total_duration_seconds=0,
    )
    db.add(plan)
    db.flush()
    job = ProductionJob(
        plan_id=plan.id,
        target_type="series",
        target_id=series.id,
        stage=STORY_PLANNING_STAGE,
        status=JOB_QUEUED,
        idempotency_key=f"story_planning:{series.id}:v{version}",
        priority=10,
        scheduled_at=bj_now(),
        max_attempts=3,
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(ProductionJob).filter(
            ProductionJob.idempotency_key == f"story_planning:{series.id}:v{version}"
        ).first()
        if existing and existing.status in STORY_PLANNING_ACTIVE_JOB_STATUSES:
            raise story_planning_in_progress_error()
        raise
    db.refresh(job)
    return job


def start_story_plan(db: Session, series: Series) -> dict:
    if active_story_plan_job(db, series.id):
        raise story_planning_in_progress_error()
    completed_payload = completed_story_plan_payload(db, series)
    if completed_payload:
        return completed_payload

    story_bible = dict(series.story_bible_json or {})
    current = story_bible.get("story_planning", {})
    version = int(current.get("version") or 0) + 1 if isinstance(current, dict) else 1
    job = enqueue_story_plan_job(db, series, version)
    db.refresh(series)
    story_planning_state = set_story_planning_state(
        db,
        series,
        status="queued",
        version=version,
        job_id=job.id,
    )
    return {
        "ok": True,
        "status": "planning",
        "series_id": series.id,
        "job_id": job.id,
        "story_planning": story_planning_state,
    }


async def run_story_plan_job(series_id: str, db: Session | None = None) -> dict:
    owns_session = db is None
    db = db or SessionLocal()
    try:
        series = db.query(Series).filter(Series.id == series_id).first()
        if not series:
            return {"ok": False, "status": "failed", "error": "Series not found"}

        current = (series.story_bible_json or {}).get("story_planning", {})
        version = int(current.get("version") or 1) if isinstance(current, dict) else 1
        set_story_planning_state(db, series, status="running", version=version)
        result = await generate_series_story_plan(db, series_id)
        trace = result.model_trace if hasattr(result, "model_trace") else {}
        terminal_status = "fallback" if isinstance(trace, dict) and trace.get("stage_status") == "fallback" else "completed"
        result_payload = result.__dict__ if hasattr(result, "__dict__") else result
        db.refresh(series)
        story_planning = set_story_planning_state(
            db,
            series,
            status=terminal_status,
            version=version,
            result=result_payload if isinstance(result_payload, dict) else {"ok": True},
        )
        return {
            "ok": True,
            "status": terminal_status,
            "series_id": series_id,
            "story_planning": story_planning,
            "result": result_payload,
        }
    except Exception as exc:
        db.rollback()
        series = db.query(Series).filter(Series.id == series_id).first()
        if series:
            set_story_planning_state(db, series, status="failed", error=str(exc))
        raise
    finally:
        if owns_session:
            db.close()


async def run_story_plan_worker_step(db: Session, *, lease_id: str, batch_size: int = 1) -> dict:
    limit = max(1, min(int(batch_size or 1), 20))
    items: list[dict] = []
    for _ in range(limit):
        job = claim_next_job(
            db,
            lease_id=lease_id,
            lease_seconds=STORY_PLANNING_JOB_LEASE_SECONDS,
            stage=STORY_PLANNING_STAGE,
        )
        if not job:
            break
        try:
            job.status = JOB_RUNNING
            job.started_at = job.started_at or bj_now()
            db.commit()
            result = await run_story_plan_job(job.target_id, db=db)
            completed_job = mark_job_completed(
                db,
                job.id,
                expected_lease_id=lease_id,
                allowed_statuses=(JOB_LEASED, JOB_RUNNING),
            )
            plan = db.query(ProductionPlan).filter(ProductionPlan.id == completed_job.plan_id).first()
            if plan:
                plan.status = PLAN_COMPLETED
                db.commit()
            items.append({
                "ok": True,
                "job_id": completed_job.id,
                "series_id": completed_job.target_id,
                "status": completed_job.status,
                "result": result,
            })
        except Exception as exc:
            logger.exception("Story planning worker failed job %s", job.id)
            failed_job = fail_job(db, job.id, "STORY_PLANNING_JOB_FAILED", str(exc), retryable=True)
            items.append({
                "ok": False,
                "job_id": failed_job.id,
                "series_id": failed_job.target_id,
                "status": failed_job.status,
                "error": str(exc),
            })

    remaining = (
        db.query(ProductionJob)
        .filter(ProductionJob.target_type == "series")
        .filter(ProductionJob.stage == STORY_PLANNING_STAGE)
        .filter(ProductionJob.status.in_([JOB_QUEUED, JOB_RETRY_WAIT]))
        .count()
    )
    return {
        "ok": True,
        "lease_id": lease_id,
        "processed": len(items),
        "remaining": remaining,
        "items": items,
    }

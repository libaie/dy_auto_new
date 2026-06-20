from __future__ import annotations

from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import AgencyExpertInvocation, VideoProductionRun
from app.domains.production_observability.production_observability_service import record_production_event
from app.services.video_production_run_types import get_run_type
from app.services.agency_creative_patch_service import create_patches_for_invocation
from app.domains.agency_operations.agency_repair_classifier import classify_repair_tasks
from app.domains.agency_operations.agency_repair_orchestrator import enqueue_repair_tasks_for_invocation

RETRYABLE_INVOCATION_ERROR_CODES = {
    "EXPERT_MODEL_TIMEOUT",
    "EXPERT_MODEL_RATE_LIMITED",
    "EXPERT_MODEL_HTTP_ERROR",
}


def create_or_resume_invocation(
    db: Session,
    *,
    idempotency_key: str,
    series_id: str,
    stage: str,
    expert_id: str,
    role: str,
    source: dict[str, str],
    input_summary: dict[str, Any],
    episode_id: str | None = None,
    run_id: str | None = None,
    production_plan_id: str | None = None,
    production_episode_id: str | None = None,
    production_segment_id: str | None = None,
    pipeline_run_id: str | None = None,
) -> AgencyExpertInvocation:
    existing = (
        db.query(AgencyExpertInvocation)
        .filter(AgencyExpertInvocation.idempotency_key == idempotency_key)
        .first()
    )
    if existing:
        if (
            existing.execution_status == "failed"
            and existing.error_code in RETRYABLE_INVOCATION_ERROR_CODES
        ):
            existing.attempt = int(existing.attempt or 1) + 1
            existing.execution_status = "running"
            existing.result_status = "pending"
            existing.output_summary_json = {}
            existing.evidence_json = []
            existing.token_usage_json = {}
            existing.model_config_snapshot_json = {}
            existing.duration_ms = 0
            existing.error_code = None
            existing.error_message = None
            existing.repair_action = None
            existing.repair_route = None
            existing.repair_target_type = None
            existing.repair_target_ids_json = []
            existing.retry_scope = None
            existing.started_at = bj_now()
            existing.finished_at = None
            db.commit()
            db.refresh(existing)
        return existing

    invocation = AgencyExpertInvocation(
        idempotency_key=idempotency_key,
        series_id=series_id,
        episode_id=episode_id,
        run_id=run_id,
        production_plan_id=production_plan_id,
        production_episode_id=production_episode_id,
        production_segment_id=production_segment_id,
        pipeline_run_id=pipeline_run_id,
        stage=stage,
        expert_id=expert_id,
        role=role,
        execution_status="running",
        result_status="pending",
        input_summary_json=input_summary,
        source_repo=source["repo"],
        source_commit=source["commit"],
        source_path=source["path"],
        source_sha256=source["sha256"],
        started_at=bj_now(),
    )
    db.add(invocation)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(AgencyExpertInvocation)
            .filter(AgencyExpertInvocation.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            return existing
        raise

    db.refresh(invocation)
    return invocation


def finalize_invocation_and_audit(
    db: Session,
    *,
    invocation_id: str,
    result_status: str,
    output_summary: dict[str, Any],
    evidence: list[Any],
    token_usage: dict[str, Any] | None = None,
    model_config_snapshot: dict[str, Any] | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    repair: dict[str, Any] | None = None,
    duration_ms: int = 0,
) -> AgencyExpertInvocation:
    invocation = (
        db.query(AgencyExpertInvocation)
        .filter(AgencyExpertInvocation.id == invocation_id)
        .one()
    )
    if invocation.execution_status in {"completed", "failed"}:
        return invocation

    repair = repair or {}
    token_usage = token_usage or {}
    model_config_snapshot = model_config_snapshot or {}

    invocation.execution_status = "failed" if result_status == "failed" else "completed"
    invocation.result_status = result_status
    classification = classify_repair_tasks(
        output_summary,
        stage=invocation.stage,
        series_id=invocation.series_id,
    )
    output = dict(output_summary or {})
    output["repair_tasks"] = [task.model_dump() for task in classification.repair_tasks]

    invocation.output_summary_json = output
    creative_patches = create_patches_for_invocation(db, invocation, output)
    invocation.evidence_json = evidence
    invocation.token_usage_json = token_usage
    invocation.model_config_snapshot_json = model_config_snapshot
    invocation.error_code = error_code
    invocation.error_message = error_message
    invocation.repair_action = repair.get("repair_action")
    invocation.repair_route = repair.get("repair_route")
    invocation.repair_target_type = repair.get("repair_target_type")
    invocation.repair_target_ids_json = repair.get("repair_target_ids", [])
    invocation.retry_scope = repair.get("retry_scope")
    invocation.duration_ms = duration_ms
    invocation.finished_at = bj_now()

    payload = {
        "agency_invocation_id": invocation.id,
        "stage": invocation.stage,
        "expert_id": invocation.expert_id,
        "role": invocation.role,
        "execution_status": invocation.execution_status,
        "result_status": invocation.result_status,
        "output_summary": output,
        "evidence": evidence,
        "token_usage": token_usage,
        "model_config_snapshot": model_config_snapshot,
        "creative_patch_ids": [patch.id for patch in creative_patches],
        "duration_ms": duration_ms,
        "error_code": error_code,
    }
    if invocation.run_id:
        run = db.query(VideoProductionRun).filter(VideoProductionRun.id == invocation.run_id).first()
        if run:
            try:
                payload["run_type"] = get_run_type(run)
            except ValueError:
                pass
            enqueue_repair_tasks_for_invocation(
                db,
                invocation,
                (run.model_trace_json or {}).get("auto_repair_policy") or {},
            )

    record_production_event(
        db,
        event_type="agency.invocation.completed",
        run_id=invocation.run_id,
        production_plan_id=invocation.production_plan_id,
        production_episode_id=invocation.production_episode_id,
        production_segment_id=invocation.production_segment_id,
        payload=payload,
    )
    db.commit()
    db.refresh(invocation)
    return invocation

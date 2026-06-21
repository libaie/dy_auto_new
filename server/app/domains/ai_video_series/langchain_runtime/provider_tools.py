from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.domains.agency_operations.agency_runtime_contracts import AgencyRuntimeError


PROVIDER_TOOL_NAMES = [
    "submit_image_generation",
    "query_image_task",
    "submit_video_generation",
    "query_video_task",
    "submit_compose",
    "query_compose_task",
]
COMPOSE_STAGES = {"episode_compose", "composition"}


def _load_run_and_job(db: Session, run_id: str, job_id: str):
    from app.db.models.video_production import ProductionJob, VideoProductionRun

    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise AgencyRuntimeError("AI_VIDEO_PROVIDER_CONTEXT_NOT_FOUND", "Video production run not found.")
    job = db.query(ProductionJob).filter(ProductionJob.id == job_id).first()
    if not job or job.plan_id != run.production_plan_id:
        raise AgencyRuntimeError("AI_VIDEO_PROVIDER_CONTEXT_NOT_FOUND", "Production job not found for run.")
    return run, job


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(key): _json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [_json_safe(item) for item in value]
        return str(value)


def _result_payload(result: Any) -> dict[str, Any]:
    data = result.data if isinstance(getattr(result, "data", None), dict) else {}
    provider_result = data.get("provider_result") if isinstance(data.get("provider_result"), dict) else {}
    return {
        "status": str(getattr(result, "status", "")),
        "message": str(getattr(result, "message", "")),
        "provider_stage_task_id": data.get("provider_stage_task_id") or provider_result.get("provider_stage_task_id"),
        "provider_task_id": provider_result.get("provider_task_id")
        or provider_result.get("stage_task_id")
        or provider_result.get("task_id"),
        "provider_status": provider_result.get("status"),
        "asset_count": len(provider_result.get("assets") or []),
        "raw": _json_safe(data),
    }


async def _execute_provider_job(db: Session, run: Any, job: Any) -> Any:
    from app.domains.video_production.production_worker_service import execute_provider_job_direct

    return await execute_provider_job_direct(db, run, job)


async def _run_provider_job(
    db: Session | None,
    *,
    run_id: str,
    job_id: str,
    expected_stage: str | set[str],
) -> dict[str, Any]:
    if db is None:
        raise AgencyRuntimeError("AI_VIDEO_PROVIDER_CONTEXT_NOT_FOUND", "Database session is required.")
    run, job = _load_run_and_job(db, run_id, job_id)
    expected_stages = {expected_stage} if isinstance(expected_stage, str) else expected_stage
    if job.stage not in expected_stages:
        raise ValueError(f"Provider tool expected stage {sorted(expected_stages)}, got {job.stage}.")
    return _result_payload(await _execute_provider_job(db, run, job))


def build_provider_tools(db: Session | None, allowed_tools: list[str] | None = None) -> list[Any]:
    selected = set(PROVIDER_TOOL_NAMES if allowed_tools is None else allowed_tools)

    @tool
    async def submit_image_generation(run_id: str, job_id: str) -> dict[str, Any]:
        """Submit or resume one image_generation production job through guarded provider services."""
        return await _run_provider_job(db, run_id=run_id, job_id=job_id, expected_stage="image_generation")

    @tool
    async def query_image_task(run_id: str, job_id: str) -> dict[str, Any]:
        """Query or sync one image_generation production job through guarded provider services."""
        return await _run_provider_job(db, run_id=run_id, job_id=job_id, expected_stage="image_generation")

    @tool
    async def submit_video_generation(run_id: str, job_id: str) -> dict[str, Any]:
        """Submit or resume one video_generation production job through guarded provider services."""
        return await _run_provider_job(db, run_id=run_id, job_id=job_id, expected_stage="video_generation")

    @tool
    async def query_video_task(run_id: str, job_id: str) -> dict[str, Any]:
        """Query or sync one video_generation production job through guarded provider services."""
        return await _run_provider_job(db, run_id=run_id, job_id=job_id, expected_stage="video_generation")

    @tool
    async def submit_compose(run_id: str, job_id: str) -> dict[str, Any]:
        """Submit or resume one compose production job through guarded provider services."""
        return await _run_provider_job(db, run_id=run_id, job_id=job_id, expected_stage=COMPOSE_STAGES)

    @tool
    async def query_compose_task(run_id: str, job_id: str) -> dict[str, Any]:
        """Query or sync one compose production job through guarded provider services."""
        return await _run_provider_job(db, run_id=run_id, job_id=job_id, expected_stage=COMPOSE_STAGES)

    tools_by_name = {
        "submit_image_generation": submit_image_generation,
        "query_image_task": query_image_task,
        "submit_video_generation": submit_video_generation,
        "query_video_task": query_video_task,
        "submit_compose": submit_compose,
        "query_compose_task": query_compose_task,
    }
    return [tools_by_name[name] for name in tools_by_name if name in selected]

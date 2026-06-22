"""AI 视频系列业务域模块。

AI 视频系列业务域，负责系列策划、风格锁定、剧集资产范围和 LangChain 工具编排。本文件负责 provider_tools 相关业务规则、状态转换和外部系统边界。
"""

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
    """业务函数：处理 _load_run_and_job 对应的业务流程、校验或数据转换。

    入参：db、run_id、job_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    from app.db.models.video_production import ProductionJob, VideoProductionRun

    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise AgencyRuntimeError("AI_VIDEO_PROVIDER_CONTEXT_NOT_FOUND", "Video production run not found.")
    job = db.query(ProductionJob).filter(ProductionJob.id == job_id).first()
    if not job or job.plan_id != run.production_plan_id:
        raise AgencyRuntimeError("AI_VIDEO_PROVIDER_CONTEXT_NOT_FOUND", "Production job not found for run.")
    return run, job


def _json_safe(value: Any) -> Any:
    """业务函数：处理 _json_safe 对应的业务流程、校验或数据转换。

    入参：value 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(key): _json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [_json_safe(item) for item in value]
        return str(value)


def _string_value(value: Any) -> str | None:
    """业务函数：处理 _string_value 对应的业务流程、校验或数据转换。

    入参：value 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _result_payload(result: Any) -> dict[str, Any]:
    """业务函数：处理 _result_payload 对应的业务流程、校验或数据转换。

    入参：result 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    data = result.data if isinstance(getattr(result, "data", None), dict) else {}
    provider_result = data.get("provider_result") if isinstance(data.get("provider_result"), dict) else {}
    code = _string_value(getattr(result, "code", None))
    return {
        "status": str(getattr(result, "status", "")),
        "message": str(getattr(result, "message", "")),
        "code": code,
        "error_code": code,
        "retryable": bool(getattr(result, "retryable", False)),
        "repair_action": getattr(result, "repair_action", None),
        "repair_route": getattr(result, "repair_route", None),
        "affected_ids": _json_safe(getattr(result, "affected_ids", []) or []),
        "provider_stage_task_id": data.get("provider_stage_task_id") or provider_result.get("provider_stage_task_id"),
        "provider_task_id": provider_result.get("provider_task_id")
        or provider_result.get("stage_task_id")
        or provider_result.get("task_id"),
        "provider_status": provider_result.get("status"),
        "asset_count": len(provider_result.get("assets") or []),
        "raw": _json_safe(data),
    }


async def _execute_provider_job(db: Session, run: Any, job: Any) -> Any:
    """业务函数：处理 _execute_provider_job 对应的业务流程、校验或数据转换。

    入参：db、run、job 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    from app.domains.video_production.production_worker_service import execute_provider_job_direct

    return await execute_provider_job_direct(db, run, job)


async def _run_provider_job(
    db: Session | None,
    *,
    run_id: str,
    job_id: str,
    expected_stage: str | set[str],
) -> dict[str, Any]:
    """业务函数：处理 _run_provider_job 对应的业务流程、校验或数据转换。

    入参：db、run_id、job_id、expected_stage 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if db is None:
        raise AgencyRuntimeError("AI_VIDEO_PROVIDER_CONTEXT_NOT_FOUND", "Database session is required.")
    run, job = _load_run_and_job(db, run_id, job_id)
    expected_stages = {expected_stage} if isinstance(expected_stage, str) else expected_stage
    if job.stage not in expected_stages:
        raise ValueError(f"Provider tool expected stage {sorted(expected_stages)}, got {job.stage}.")
    return _result_payload(await _execute_provider_job(db, run, job))


def build_provider_tools(db: Session | None, allowed_tools: list[str] | None = None) -> list[Any]:
    """业务函数：处理 build_provider_tools 对应的业务流程、校验或数据转换。

    入参：db、allowed_tools 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    selected = set(PROVIDER_TOOL_NAMES if allowed_tools is None else allowed_tools)

    @tool
    async def submit_image_generation(run_id: str, job_id: str) -> dict[str, Any]:
        """业务函数：处理 submit_image_generation 对应的业务流程、校验或数据转换。

        入参：run_id、job_id 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
        """Submit or resume one image_generation production job through guarded provider services."""
        return await _run_provider_job(db, run_id=run_id, job_id=job_id, expected_stage="image_generation")

    @tool
    async def query_image_task(run_id: str, job_id: str) -> dict[str, Any]:
        """业务函数：处理 query_image_task 对应的业务流程、校验或数据转换。

        入参：run_id、job_id 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
        """Query or sync one image_generation production job through guarded provider services."""
        return await _run_provider_job(db, run_id=run_id, job_id=job_id, expected_stage="image_generation")

    @tool
    async def submit_video_generation(run_id: str, job_id: str) -> dict[str, Any]:
        """业务函数：处理 submit_video_generation 对应的业务流程、校验或数据转换。

        入参：run_id、job_id 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
        """Submit or resume one video_generation production job through guarded provider services."""
        return await _run_provider_job(db, run_id=run_id, job_id=job_id, expected_stage="video_generation")

    @tool
    async def query_video_task(run_id: str, job_id: str) -> dict[str, Any]:
        """业务函数：处理 query_video_task 对应的业务流程、校验或数据转换。

        入参：run_id、job_id 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
        """Query or sync one video_generation production job through guarded provider services."""
        return await _run_provider_job(db, run_id=run_id, job_id=job_id, expected_stage="video_generation")

    @tool
    async def submit_compose(run_id: str, job_id: str) -> dict[str, Any]:
        """业务函数：处理 submit_compose 对应的业务流程、校验或数据转换。

        入参：run_id、job_id 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
        """Submit or resume one compose production job through guarded provider services."""
        return await _run_provider_job(db, run_id=run_id, job_id=job_id, expected_stage=COMPOSE_STAGES)

    @tool
    async def query_compose_task(run_id: str, job_id: str) -> dict[str, Any]:
        """业务函数：处理 query_compose_task 对应的业务流程、校验或数据转换。

        入参：run_id、job_id 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
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

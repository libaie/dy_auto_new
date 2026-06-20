import asyncio
import copy
import inspect
import os
import re
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import PIXELLE_CONFIG_PATH, bj_now
from app.db_models import ProductionJob, ProductionSegment, VideoProductionRun
from app.domains.agency_operations.agency_creative_patch_service import unresolved_patch_gate
from app.domains.agency_operations.agency_repair_executor import execute_repair_job, is_agency_repair_stage
from app.domains.model_configuration.runtime_model_config import resolve_runtime_model_config
from app.domains.video_production.production_action_result import ProductionActionResult
from app.domains.video_production.production_errors import ProductionErrorCode, ProductionRepairableError, to_http_detail
from app.domains.video_production.production_queue_service import (
    claim_next_job,
    fail_job,
    mark_job_completed,
    retry_job_without_attempt,
)
from app.domains.video_production.production_status import (
    JOB_BLOCKED,
    JOB_FAILED,
    JOB_LEASED,
    JOB_QUEUED,
    JOB_RETRY_WAIT,
    JOB_RUNNING,
    SEGMENT_BLOCKED_BY_REVIEW,
    SEGMENT_FAILED,
    SEGMENT_IMAGE_RUNNING,
    SEGMENT_VIDEO_RUNNING,
)
from app.domains.video_production.provider_capability_service import capability_from_model_config
from app.domains.video_production.provider_stage_executor import ProviderStageExecutor
from app.services.video_production_service import run_ai_audit_for_assets
from app.domains.video_production.video_production_run_types import MOCK_SERIES_SCALE, REAL_SHORT_E2E, get_run_type


MAX_WORKER_STEP_BATCH_SIZE = 100
COMPOSE_STAGES = {"composition", "episode_compose"}
DEFERRED_STAGE_GATE_TIMEOUT_SECONDS = 30
CREATIVE_PATCH_STAGE_GATES = {
    "image_generation": "image_stage",
    "video_generation": "video_stage",
    "episode_compose": "compose_preflight",
    "composition": "compose_preflight",
}


def _deferred_stage_gate_timeout_seconds() -> float:
    try:
        return float(os.getenv("DY_AUTO_DEFERRED_STAGE_GATE_TIMEOUT_SECONDS", DEFERRED_STAGE_GATE_TIMEOUT_SECONDS))
    except (TypeError, ValueError):
        return float(DEFERRED_STAGE_GATE_TIMEOUT_SECONDS)


def _pixelle_output_root() -> Path:
    return Path(PIXELLE_CONFIG_PATH).resolve().parent / "output"


async def execute_real_job(db: Session, run: VideoProductionRun, job: ProductionJob) -> ProductionActionResult:
    if is_agency_repair_stage(job.stage):
        return await execute_repair_job(db, job)
    job_spec = _job_spec(db, run, job)
    gate_result = await _run_deferred_stage_gates(db, run, job, job_spec)
    if gate_result is not None:
        return gate_result
    model_config = resolve_runtime_model_config(db, job_spec["scene_key"])
    provider = str(model_config.get("provider") or "configured")
    model_name = str(model_config.get("model_name") or model_config.get("model") or job_spec["scene_key"])
    payload = {
        **job_spec["payload"],
        "run_id": run.id,
        "job_id": job.id,
        "stage": job.stage,
        "model_config": model_config,
    }
    result = await ProviderStageExecutor(PixelleStageClientAdapter(db, run, job)).execute(
        db,
        run_id=run.id,
        plan_id=run.production_plan_id,
        job_id=job.id,
        target_type=job.target_type,
        target_id=job.target_id,
        stage=job.stage,
        provider=provider,
        model_name=model_name,
        estimated_cost=_model_estimated_cost(model_config),
        payload=payload,
        capability=_worker_capability_from_model_config(model_config),
    )
    if result.status != "success":
        return result
    if not _persist_completed_provider_result(db, run, job, result):
        return ProductionActionResult.blocked(
            ProductionErrorCode.PROVIDER_TASK_FAILED,
            "Provider completed with no assets.",
            "Inspect the provider response and retry or regenerate the stage so the worker can persist a reviewable asset.",
            repair_route=f"/video-production/{run.id}",
            affected_ids=[job.id],
            retryable=False,
        )
    return result


async def _run_deferred_stage_gates(
    db: Session,
    run: VideoProductionRun,
    job: ProductionJob,
    job_spec: dict,
) -> ProductionActionResult | None:
    from app.services import video_production_service as video_service
    from app.domains.model_configuration.runtime_model_config import RuntimeModelConfigError

    gates: list[tuple[str, str, Any]] = []
    if job.stage == "image_generation":
        gates.append(("image_stage", "frames", [job_spec["payload"]["frame"]]))
    elif job.stage == "video_generation":
        frame = job_spec["payload"]["frame"]
        gates.extend([
            ("image_review", "frames", [frame]),
            ("video_stage", "frames", [frame]),
        ])
    elif job.stage in COMPOSE_STAGES:
        payload = job_spec["payload"]
        gates.extend([
            ("video_review", "segments", payload["segments"]),
            (
                "compose_preflight",
                "segments",
                {"segments": payload["segments"], "edit_manifest": payload["edit_manifest"]},
            ),
        ])

    if gates:
        try:
            video_service.resolve_runtime_model_config(db, "llm_agency_expert_review")
        except RuntimeModelConfigError:
            return None

    for stage, payload_key, payload in gates:
        timeout_seconds = _deferred_stage_gate_timeout_seconds()
        stage_context = video_service._stage_context(db, run, payload_key, payload)
        if stage == "video_stage" and job.stage == "video_generation":
            total_frames = len(video_service.video_stage_frames(db, run))
            current_frames = payload if isinstance(payload, list) else []
            stage_context["job_scope"] = {
                "mode": "single_production_segment_job",
                "current_target_id": job.target_id,
                "current_frame_count": len(current_frames),
                "total_frame_count": total_frames,
                "review_instruction": (
                    "The frames payload contains only the current production segment job; "
                    "other segments are queued separately and must not be treated as missing "
                    "unless the full production queue lacks them."
                ),
            }
        if stage == "image_stage" and job_spec.get("scene_key") == "image_generation":
            model_config = (job_spec.get("payload") or {}).get("frame", {}).get("provider_parameters") or {}
            stage_context = _image_stage_context_for_model(stage_context, model_config)
        try:
            trace = await asyncio.wait_for(
                video_service._guard_provider_stage(
                    db,
                    run,
                    stage,
                    stage_context,
                ),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            video_service._store_agency_trace(
                run,
                stage,
                {
                    "stage": stage,
                    "stage_status": "partial",
                    "invocation_ids": [],
                    "invocations": [],
                    "error_code": "DEFERRED_STAGE_REVIEW_TIMEOUT",
                    "error_message": (
                        f"{stage} expert review exceeded "
                        f"{timeout_seconds:g} seconds before provider submission."
                    ),
                    "next_action": "Continue provider submission and keep the partial review trace visible.",
                },
            )
            db.commit()
            db.refresh(run)
            continue
        if trace is None:
            return ProductionActionResult.blocked(
                ProductionErrorCode.REVIEW_GATE_BLOCKED,
                f"{stage} expert review blocked the provider job.",
                "Review the expert trace and repair the production inputs before retrying this job.",
                repair_route=f"/video-production/{run.id}",
                affected_ids=[job.id],
                retryable=False,
                data={"stage": stage, "agency_trace": (run.model_trace_json or {}).get("agency_reviews", {}).get(stage)},
            )
    return None


def run_real_worker_step(db: Session, run_id: str, *, lease_id: str, batch_size: int = 1) -> dict:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise ValueError("Run not found")
    if get_run_type(run) == MOCK_SERIES_SCALE:
        raise ProductionRepairableError(
            code=ProductionErrorCode.INVALID_RUN_TYPE,
            message="mock_series_scale runs must use the mock worker step.",
            cause="invalid_worker_for_run_type",
            repair_action="Use /api/video-production/runs/{run_id}/mock-worker-step for mock scale runs.",
            repair_route=f"/video-production/{run.id}",
            retryable=False,
            affected_ids=[run.id],
        )
    if get_run_type(run) != REAL_SHORT_E2E:
        raise ProductionRepairableError(
            code=ProductionErrorCode.INVALID_RUN_TYPE,
            message="Real worker step only processes real_short_e2e runs.",
            cause="invalid_worker_for_run_type",
            repair_action="Use the legacy stage routes for legacy episode runs.",
            repair_route=f"/video-production/{run.id}",
            retryable=False,
            affected_ids=[run.id],
        )
    if not run.production_plan_id:
        raise ValueError("Run has no linked production plan")

    limit = max(1, min(int(batch_size or 1), MAX_WORKER_STEP_BATCH_SIZE))
    items: list[dict[str, Any]] = []
    for _ in range(limit):
        job = claim_next_job(db, lease_id=lease_id, plan_id=run.production_plan_id)
        if not job:
            break
        items.append(_process_claimed_job(db, run, job))

    return {
        "ok": True,
        "lease_id": lease_id,
        "run_id": run.id,
        "processed": len(items),
        "remaining": _remaining_claimable_jobs(db, run.production_plan_id),
        "items": items,
    }


def _worker_capability_from_model_config(model_config: dict | None) -> dict:
    if not isinstance(model_config, dict):
        return capability_from_model_config(model_config)
    normalized = dict(model_config)
    if isinstance(model_config.get("config"), dict):
        merged_config_json = {
            **(model_config.get("config_json") or {}),
            **model_config["config"],
        }
        normalized["config_json"] = merged_config_json
    return capability_from_model_config(normalized)


def _model_estimated_cost(model_config: dict | None) -> float:
    if not isinstance(model_config, dict):
        return 0.0
    candidates = [model_config.get("estimated_cost"), model_config.get("cost")]
    for key in ("config", "config_json", "provider_options", "capability"):
        value = model_config.get(key)
        if isinstance(value, dict):
            candidates.extend([value.get("estimated_cost"), value.get("cost")])
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            amount = float(candidate)
        except (TypeError, ValueError):
            continue
        if amount > 0:
            return amount
    return 0.0


def _process_claimed_job(db: Session, run: VideoProductionRun, job: ProductionJob) -> dict:
    try:
        _mark_segment_running_for_job(db, job)
        result = _run_async(execute_real_job(db, run, job))
        if _result_is_blocked(result):
            item = _record_blocked_result(db, job, result)
            _update_run_status_after_stage_job(db, run, job.stage)
            return item
        item = _success_item(result, job)
        refreshed = db.query(ProductionJob).filter(ProductionJob.id == job.id).first()
        if refreshed and refreshed.status in {"leased", "running"}:
            refreshed = mark_job_completed(
                db,
                refreshed.id,
                provider_task_id=_result_provider_task_id(result),
                expected_lease_id=job.lease_id,
            )
        if refreshed:
            item["status"] = refreshed.status
            item["provider_task_id"] = refreshed.provider_task_id
            _update_run_status_after_stage_job(db, run, refreshed.stage)
        return item
    except ProductionRepairableError as exc:
        failed = _fail_or_reload_job(db, job, exc.code.value, exc.message, exc.retryable)
        _update_run_status_after_stage_job(db, run, job.stage)
        detail = to_http_detail(exc)
        return {
            "ok": False,
            "job_id": failed.id,
            "status": failed.status,
            "error_code": detail["code"],
            "error": detail["message"],
            "retryable": failed.retryable,
            "attempt_count": failed.attempt_count,
            "retry_after": failed.retry_after.isoformat() if failed.retry_after else None,
            "repair": detail,
        }
    except ValueError as exc:
        failed = _fail_or_reload_job(
            db,
            job,
            ProductionErrorCode.PROVIDER_SUBMIT_FAILED.value,
            str(exc),
            retryable=False,
        )
        _update_run_status_after_stage_job(db, run, job.stage)
        return _failed_job_item(failed, ProductionErrorCode.PROVIDER_SUBMIT_FAILED.value, str(exc), {"message": str(exc)})
    except Exception as exc:
        failed = _fail_or_reload_job(
            db,
            job,
            ProductionErrorCode.PROVIDER_SUBMIT_FAILED.value,
            "Unexpected worker job error.",
            retryable=True,
        )
        _update_run_status_after_stage_job(db, run, job.stage)
        return _failed_job_item(
            failed,
            ProductionErrorCode.PROVIDER_SUBMIT_FAILED.value,
            "Unexpected worker job error.",
            {"message": str(exc)},
        )


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("run_real_worker_step cannot be called from a running event loop")


def _success_item(result: Any, job: ProductionJob) -> dict:
    if isinstance(result, ProductionActionResult):
        payload = result.to_http_detail()
        return {
            "ok": result.status == "success",
            "job_id": job.id,
            "status": job.status,
            "result": payload,
        }
    if isinstance(result, dict):
        return {
            "ok": result.get("ok", True),
            "job_id": result.get("job_id") or job.id,
            "status": result.get("status") or job.status,
            "result": result,
        }
    return {"ok": True, "job_id": job.id, "status": job.status, "result": result}


def _result_is_blocked(result: Any) -> bool:
    if isinstance(result, ProductionActionResult):
        return result.status != "success"
    if isinstance(result, dict):
        return result.get("ok") is False or result.get("status") in {"blocked", "failed"}
    return False


def _record_blocked_result(db: Session, job: ProductionJob, result: Any) -> dict:
    if isinstance(result, ProductionActionResult):
        detail = result.to_http_detail()
        code = detail.get("code") or ProductionErrorCode.PROVIDER_TASK_FAILED.value
        message = detail.get("message") or "Provider job did not complete."
        retryable = bool(detail.get("retryable"))
    else:
        detail = result
        code = str(result.get("code") or result.get("error_code") or ProductionErrorCode.PROVIDER_TASK_FAILED.value)
        message = str(result.get("message") or result.get("error") or "Provider job did not complete.")
        retryable = bool(result.get("retryable", True))
    if code == ProductionErrorCode.PROVIDER_STAGE_TASK_SYNC_REQUIRED.value:
        retried = retry_job_without_attempt(
            db,
            job.id,
            code,
            message,
            retry_after_seconds=60,
            expected_lease_id=job.lease_id,
        )
        return _failed_job_item(retried, code, message, detail)
    if code == ProductionErrorCode.PROVIDER_THROTTLED.value:
        retried = retry_job_without_attempt(
            db,
            job.id,
            code,
            message,
            retry_after_seconds=60,
            expected_lease_id=job.lease_id,
        )
        return _failed_job_item(retried, code, message, detail)
    if code == ProductionErrorCode.REVIEW_GATE_BLOCKED.value:
        current = db.query(ProductionJob).filter(ProductionJob.id == job.id).first() or job
        current.status = JOB_BLOCKED
        current.blocked_reason = code
        current.error_code = code
        current.error_message = message
        current.retryable = False
        current.lease_id = None
        current.leased_until = None
        current.updated_at = bj_now()
        _mark_segment_blocked_for_job(db, current)
        db.commit()
        db.refresh(current)
        return _failed_job_item(current, code, message, detail)
    failed = _fail_or_reload_job(db, job, code, message, retryable)
    return _failed_job_item(failed, code, message, detail)


def _failed_job_item(
    failed: ProductionJob,
    code: str,
    message: str,
    detail: dict,
) -> dict:
    return {
        "ok": False,
        "job_id": failed.id,
        "status": failed.status,
        "error_code": code,
        "error": message,
        "retryable": failed.retryable,
        "attempt_count": failed.attempt_count,
        "retry_after": failed.retry_after.isoformat() if failed.retry_after else None,
        "repair": detail,
    }


def _fail_or_reload_job(db: Session, job: ProductionJob, code: str, message: str, retryable: bool) -> ProductionJob:
    current = db.query(ProductionJob).filter(ProductionJob.id == job.id).first()
    if current and current.status not in {"leased", "running"}:
        return current
    if code == ProductionErrorCode.PROVIDER_THROTTLED.value:
        return retry_job_without_attempt(
            db,
            job.id,
            code,
            message,
            retry_after_seconds=60,
            expected_lease_id=job.lease_id,
        )
    failed = fail_job(db, job.id, code, message, retryable=retryable)
    if failed.status == JOB_FAILED:
        _mark_segment_failed_for_job(db, failed)
    return failed


def _segment_for_job(db: Session, job: ProductionJob) -> ProductionSegment | None:
    if job.target_type != "production_segment":
        return None
    return db.query(ProductionSegment).filter(ProductionSegment.id == job.target_id).first()


def _mark_segment_running_for_job(db: Session, job: ProductionJob) -> None:
    segment = _segment_for_job(db, job)
    if not segment:
        return
    if job.stage == "image_generation":
        segment.status = SEGMENT_IMAGE_RUNNING
    elif job.stage == "video_generation":
        segment.status = SEGMENT_VIDEO_RUNNING
    else:
        return
    db.commit()


def _mark_segment_failed_for_job(db: Session, job: ProductionJob) -> None:
    segment = _segment_for_job(db, job)
    if not segment:
        return
    segment.status = SEGMENT_FAILED
    db.commit()


def _mark_segment_blocked_for_job(db: Session, job: ProductionJob) -> None:
    segment = _segment_for_job(db, job)
    if not segment:
        return
    segment.status = SEGMENT_BLOCKED_BY_REVIEW


def _result_provider_task_id(result: Any) -> str | None:
    data = None
    if isinstance(result, ProductionActionResult):
        data = result.data
    elif isinstance(result, dict):
        data = result
    if not isinstance(data, dict):
        return None
    provider_result = data.get("provider_result") if isinstance(data.get("provider_result"), dict) else data
    return provider_result.get("provider_task_id") or provider_result.get("stage_task_id") or provider_result.get("task_id")


def _model_config_body(model_config: dict) -> dict:
    config = {}
    for key in ("config_json", "config"):
        value = model_config.get(key)
        if isinstance(value, dict):
            config.update(value)
    return config


def _image_model_supports_references(model_config: dict) -> bool:
    config = _model_config_body(model_config)
    capabilities = config.get("capabilities") if isinstance(config.get("capabilities"), dict) else {}
    limits = config.get("limits") if isinstance(config.get("limits"), dict) else {}
    if not capabilities and not limits:
        return True
    if capabilities.get("multi_reference_to_image") or capabilities.get("image_to_image"):
        return True
    try:
        return int(limits.get("max_reference_images") or 0) > 0
    except (TypeError, ValueError):
        return False


def _strip_text_only_image_prompt(prompt: str) -> str:
    clean = re.sub(r"@Image\s+\d+\s+locks[^.。]*(?:[.。]\s*)?", "", str(prompt or ""))
    clean = re.sub(r"Style reference images lock[^.。]*(?:[.。]\s*)?", "", clean)
    return " ".join(clean.split())


def _image_frame_for_model(frame: dict, model_config: dict) -> dict:
    if _image_model_supports_references(model_config):
        return frame
    style_constraints = dict(frame.get("style_constraints") or {})
    continuity_notes = _strip_text_only_image_prompt(style_constraints.get("continuity_notes", ""))
    return {
        **frame,
        "reference_urls": [],
        "reference_instructions": "",
        "image_prompt": _strip_text_only_image_prompt(frame.get("image_prompt", "")),
        "style_constraints": {**style_constraints, "continuity_notes": continuity_notes},
    }


def _storyboard_for_text_only_image_model(storyboard: dict | None) -> dict:
    sanitized = copy.deepcopy(storyboard or {})
    frames = sanitized.get("frames")
    if isinstance(frames, list):
        for frame in frames:
            if not isinstance(frame, dict):
                continue
            frame["reference_urls"] = []
            frame["character_reference_urls"] = []
            frame["style_reference_urls"] = []
            frame["reference_instructions"] = ""
            frame["image_prompt"] = _strip_text_only_image_prompt(frame.get("image_prompt", ""))
            frame["video_prompt"] = _strip_text_only_image_prompt(frame.get("video_prompt", ""))
    sanitized["provider_reference_policy"] = "text_only_no_reference_images"
    return sanitized


def _image_stage_context_for_model(context: dict, model_config: dict) -> dict:
    if _image_model_supports_references(model_config):
        return context
    sanitized = copy.deepcopy(context)
    sanitized["provider_reference_policy"] = "text_only_no_reference_images"
    sanitized["provider_reference_note"] = (
        "Selected image model is text-to-image only and declares max_reference_images=0; "
        "do not require reference_urls for this provider path."
    )
    sanitized["storyboard"] = _storyboard_for_text_only_image_model(sanitized.get("storyboard"))
    sanitized["episode_storyboard"] = _storyboard_for_text_only_image_model(sanitized.get("episode_storyboard"))
    return sanitized


def _job_spec(db: Session, run: VideoProductionRun, job: ProductionJob) -> dict:
    from app.services import video_production_service as video_service

    _guard_creative_patch_job(db, run, job)
    if job.stage == "image_generation":
        frame = _find_frame(video_service.image_stage_frames(run, db=db), job.target_id)
        model_config = resolve_runtime_model_config(db, "image_generation")
        frame = {
            **_image_frame_for_model(frame, model_config),
            "provider_parameters": video_service.redact_runtime_model_config(model_config),
        }
        if (
            get_run_type(run) == REAL_SHORT_E2E
            and _image_model_supports_references(model_config)
            and not frame.get("reference_urls")
        ):
            raise ProductionRepairableError(
                code=ProductionErrorCode.REVIEW_GATE_BLOCKED,
                message="Real image generation worker payload is missing reference images.",
                cause="worker_image_stage_reference_urls_missing",
                repair_action="Regenerate the style lock and storyboard so each production segment carries character and scene reference URLs.",
                repair_route=f"/video-production/{run.id}",
                retryable=False,
                affected_ids=[str(job.target_id)],
            )
        return {"scene_key": "image_generation", "payload": {"frame": frame}}
    if job.stage == "video_generation":
        frame = _find_frame(video_service.video_stage_frames(db, run), job.target_id)
        model_config = resolve_runtime_model_config(db, "video_rendering")
        frame = {
            **frame,
            "provider_parameters": video_service.redact_runtime_model_config(model_config),
        }
        return {"scene_key": "video_rendering", "payload": {"frame": frame}}
    if job.stage in COMPOSE_STAGES:
        return {
            "scene_key": "video_composition",
            "payload": {
                "segments": video_service.compose_segments(db, run),
                "edit_manifest": video_service.default_edit_manifest(run),
            },
        }
    raise ProductionRepairableError(
        code=ProductionErrorCode.PROVIDER_SUBMIT_FAILED,
        message=f"Unsupported real worker job stage: {job.stage}",
        cause="unsupported_real_worker_stage",
        repair_action="Retry with a supported real provider stage.",
        repair_route=f"/video-production/{run.id}",
        retryable=False,
        affected_ids=[job.id],
    )


def _guard_creative_patch_job(db: Session, run: VideoProductionRun, job: ProductionJob) -> None:
    stage_gate = CREATIVE_PATCH_STAGE_GATES.get(job.stage)
    if not stage_gate:
        return
    gate = unresolved_patch_gate(db, run, stage=stage_gate)
    if not gate.get("blocked"):
        return
    raise ProductionRepairableError(
        code=ProductionErrorCode.REVIEW_GATE_BLOCKED,
        message=f"Creative patches are pending in the director workbench: {gate['blocking_count']} unresolved.",
        cause="creative_patch_gate_blocked",
        repair_action=gate["repair_action"],
        repair_route=gate["repair_route"],
        retryable=False,
        affected_ids=gate["patch_ids"],
    )


def _find_frame(frames: list[dict], target_id: str) -> dict:
    for frame in frames:
        if frame.get("production_segment_id") == target_id or frame.get("frame_id") == target_id:
            return frame
    raise ProductionRepairableError(
        code=ProductionErrorCode.SEGMENT_PLAN_MISSING,
        message=f"Worker job target is missing from the production payload: {target_id}",
        cause="worker_target_missing",
        repair_action="Regenerate the production plan or retry the stage enqueue.",
        repair_route="/video-production",
        retryable=False,
        affected_ids=[target_id],
    )


class PixelleStageClientAdapter:
    def __init__(self, db: Session, run: VideoProductionRun, job: ProductionJob):
        self.db = db
        self.run = run
        self.job = job

    async def submit(self, payload: dict) -> dict:
        from app.services import video_production_service as video_service

        model_config = payload["model_config"]
        provider_template = _provider_stage_template(payload)
        if self.job.stage == "image_generation":
            response = await video_service.submit_image_batch(
                db=self.db,
                run_id=self.run.id,
                episode_id=self.run.episode_id,
                frames=[payload["frame"]],
                model_config=model_config,
                template_config=provider_template,
            )
        elif self.job.stage == "video_generation":
            response = await video_service.submit_video_batch(
                db=self.db,
                run_id=self.run.id,
                frames=[payload["frame"]],
                model_config=model_config,
                template_config=provider_template,
            )
        elif self.job.stage in COMPOSE_STAGES:
            compose_kwargs = {
                "db": self.db,
                "run_id": self.run.id,
                "segments": payload["segments"],
                "edit_manifest": payload["edit_manifest"],
                "model_config": model_config,
            }
            if _callable_accepts_provider_stage_metadata(video_service.submit_compose):
                compose_kwargs.update(provider_template)
            response = await video_service.submit_compose(**compose_kwargs)
        else:
            response = {}
        stage_task_id = response.get("stage_task_id") or response.get("provider_task_id") or response.get("task_id")
        return {**response, "provider_task_id": stage_task_id}

    async def sync(self, provider_task_id: str) -> dict:
        from app.services import video_production_service as video_service

        status = await video_service.get_stage_task(self.db, provider_task_id)
        return {**status, "provider_task_id": provider_task_id, "stage_task_id": provider_task_id}


def _provider_stage_template(payload: dict) -> dict:
    return {
        "external_task_id": payload.get("external_task_id"),
        "provider_stage_task_id": payload.get("provider_stage_task_id"),
        "provider_idempotency_key": payload.get("provider_idempotency_key"),
    }


def _callable_accepts_provider_stage_metadata(fn) -> bool:
    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError):
        return True
    if any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()):
        return True
    return "external_task_id" in signature.parameters


def _persist_completed_provider_result(
    db: Session,
    run: VideoProductionRun,
    job: ProductionJob,
    result: ProductionActionResult,
) -> bool:
    from app.services import video_production_service as video_service
    from app.domains.video_production.asset_storage_guard import persist_provider_asset

    provider_result = result.data.get("provider_result", {}) if isinstance(result.data, dict) else {}
    provider_task_id = _result_provider_task_id(result)
    provider_stage_task_id = result.data.get("provider_stage_task_id") if isinstance(result.data, dict) else None
    assets = provider_result.get("assets") or []
    if not assets:
        return False
    if provider_stage_task_id:
        assets = [
            {**asset, "provider_stage_task_id": asset.get("provider_stage_task_id") or provider_stage_task_id}
            for asset in assets
        ]
    if job.stage == "image_generation":
        saved = video_service.mark_image_stage_assets(db, run, assets, pixelle_task_id=provider_task_id)
        persisted = _persist_registered_assets(db, saved, persist_provider_asset)
        run_ai_audit_for_assets(db, run, persisted)
    elif job.stage == "video_generation":
        saved = video_service.mark_video_stage_assets(db, run, assets, pixelle_task_id=provider_task_id)
        persisted = _persist_registered_assets(db, saved, persist_provider_asset)
        run_ai_audit_for_assets(db, run, persisted)
    elif job.stage in COMPOSE_STAGES:
        run.pixelle_stage_task_id = provider_task_id
        db.commit()
        final_asset = video_service.persist_final_video(db, run, assets[0], run_audit=False)
        persisted = _persist_registered_assets(db, [final_asset], persist_provider_asset)
        if persisted:
            video_service.run_final_audit_for_asset(db, run, persisted[0])
    return True


def _asset_ready_for_review(asset) -> bool:
    return bool(asset.copy_status == "persisted" and asset.checksum and asset.storage_path)


def _persist_registered_assets(db: Session, assets: list, persist_provider_asset) -> list:
    persisted = []
    for asset in assets:
        if _asset_ready_for_review(asset):
            persisted.append(asset)
            continue
        try:
            persisted.append(
                persist_provider_asset(
                    db,
                    asset.id,
                    output_root="output/video-production",
                    pixelle_output_root=_pixelle_output_root(),
                )
            )
        except ProductionRepairableError:
            db.refresh(asset)
    return persisted


def _remaining_claimable_jobs(db: Session, plan_id: str) -> int:
    now = bj_now()
    return db.query(ProductionJob).filter(
        ProductionJob.plan_id == plan_id,
        ProductionJob.status.in_([JOB_QUEUED, JOB_RETRY_WAIT]),
        ((ProductionJob.retry_after.is_(None)) | (ProductionJob.retry_after <= now)),
        ProductionJob.scheduled_at <= now,
    ).count()


def _open_stage_jobs(db: Session, plan_id: str, stage: str) -> int:
    return db.query(ProductionJob).filter(
        ProductionJob.plan_id == plan_id,
        ProductionJob.stage == stage,
        ProductionJob.status.in_([JOB_QUEUED, JOB_LEASED, JOB_RUNNING, JOB_RETRY_WAIT]),
    ).count()


def _failed_stage_jobs(db: Session, plan_id: str, stage: str) -> int:
    return db.query(ProductionJob).filter(
        ProductionJob.plan_id == plan_id,
        ProductionJob.stage == stage,
        ProductionJob.status == JOB_FAILED,
    ).count()


def _blocked_stage_jobs(db: Session, plan_id: str, stage: str) -> int:
    return db.query(ProductionJob).filter(
        ProductionJob.plan_id == plan_id,
        ProductionJob.stage == stage,
        ProductionJob.status == JOB_BLOCKED,
    ).count()


def _update_run_status_after_stage_job(db: Session, run: VideoProductionRun, stage: str) -> None:
    if not run.production_plan_id:
        return
    if stage == "image_generation" and run.status == "image_approved":
        return
    if stage == "video_generation" and run.status == "video_segments_approved":
        return
    if stage in COMPOSE_STAGES and run.status == "completed":
        return
    if _failed_stage_jobs(db, run.production_plan_id, stage):
        run.status = "failed"
        run.current_stage = stage
        run.updated_at = bj_now()
        db.commit()
        db.refresh(run)
        return
    if _blocked_stage_jobs(db, run.production_plan_id, stage):
        if stage == "image_generation":
            run.status = "image_human_review_required"
            run.current_stage = "image_review"
        elif stage == "video_generation":
            run.status = "video_human_review_required"
            run.current_stage = "video_review"
        elif stage in COMPOSE_STAGES:
            run.status = "final_review_pending"
            run.current_stage = "final_review"
        run.updated_at = bj_now()
        db.commit()
        db.refresh(run)
        return
    stage_open_jobs = _open_stage_jobs(db, run.production_plan_id, stage)
    if stage == "image_generation":
        if stage_open_jobs:
            run.status = "image_batch_running"
            run.current_stage = "image_generation"
        else:
            run.status = "image_review_pending"
            run.current_stage = "image_review"
    elif stage == "video_generation":
        if stage_open_jobs:
            run.status = "video_batch_running"
            run.current_stage = "video_rendering"
        else:
            run.status = "video_review_pending"
            run.current_stage = "video_review"
    elif stage in COMPOSE_STAGES and not stage_open_jobs:
        run.status = "final_review_pending"
        run.current_stage = "final_review"
    else:
        return
    run.updated_at = bj_now()
    db.commit()
    db.refresh(run)

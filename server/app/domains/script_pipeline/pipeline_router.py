"""流水线编排 API — thin layer for legacy script pipeline runs."""
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.db.models.script_pipeline import PipelineRun
from app.deps import require_role
from app.db.models import Episode, Series
from app.domains.pixelle_integration.pixelle_client import _pixelle_request
from app.domains.agency_operations.agency_orchestrator import AgencyOrchestrator
from app.domains.model_configuration.runtime_model_config import RuntimeModelConfigError, resolve_runtime_model_config
from app.domains.agency_operations.video_agency_team import build_agency_context

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

BJT = timezone(timedelta(hours=8))
PROVIDER_RENDERING_REQUIRES_JOB = "Script pipeline provider rendering requires a production run job."


class PipelineStartRequest(BaseModel):
    series_id: str
    episode_id: str | None = None
    director_plan: dict | None = None


def _load_director_plan_from_episode(db: Session, series_id: str, episode_id: str | None) -> dict | None:
    if not episode_id:
        return None
    episode = db.query(Episode).filter(
        Episode.id == episode_id,
        Episode.series_id == series_id,
    ).first()
    if not episode:
        raise HTTPException(404, "Episode not found")
    storyboard = episode.storyboard_json or {}
    if not storyboard.get("frames"):
        raise HTTPException(400, "Episode storyboard_json is empty. Run /api/director/auto-plan first.")
    return storyboard


def _pipeline_trace_status(trace: dict | None) -> str:
    if not trace:
        return "missing"
    stage_status = trace.get("stage_status")
    if trace.get("error_code"):
        return "failed" if stage_status == "failed" else "blocked"
    if stage_status in {"failed", "blocked", "warning", "partial"}:
        return stage_status
    if stage_status == "completed":
        return "complete"
    return stage_status or "missing"


def _layers_agency_trace_status(layers: dict) -> str:
    if not layers:
        return "missing"
    statuses = []
    saw_legacy = False
    for layer in layers.values():
        if not isinstance(layer, dict):
            continue
        if layer.get("agency_trace"):
            statuses.append(_pipeline_trace_status(layer.get("agency_trace")))
        elif layer.get("agency_trace_status") == "legacy_summary":
            saw_legacy = True
    if statuses:
        if "failed" in statuses:
            return "failed"
        if "blocked" in statuses:
            return "blocked"
        if "warning" in statuses:
            return "warning"
        if "partial" in statuses:
            return "partial"
        if all(status == "complete" for status in statuses):
            return "complete"
    return "legacy_summary" if saw_legacy else "missing"


def _serialize_run(run: PipelineRun) -> dict:
    layers = run.layers_json or {}
    agency_trace_status = _layers_agency_trace_status(layers)
    return {
        "id": run.id,
        "series_id": run.series_id,
        "episode_id": run.episode_id,
        "mode": run.mode,
        "model_ids": run.model_ids or {},
        "layers_json": layers,
        "agency_trace_status": agency_trace_status,
        "current_layer": run.current_layer,
        "status": run.status,
        "error_log": run.error_log,
        "actual_cost_so_far": run.actual_cost_so_far,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


def _agency_layer_summary(
    series: Series | None,
    phase: str,
    status: str,
    input_summary: dict | None = None,
    output_summary: dict | None = None,
    error: str = "",
    agency_trace: dict | None = None,
) -> dict:
    context = build_agency_context(series.story_bible_json if series else {})
    summary = {
        "status": status,
        "agency_trace_status": "legacy_summary",
        "agency_roles": context.get("core_roles") or [],
        "quality_gates": (context.get("quality_gates") or {}).get(phase, []),
        "input_summary": input_summary or {},
        "output_summary": output_summary or {},
        "error": error,
    }
    if agency_trace:
        summary["agency_trace"] = agency_trace
        summary["agency_trace_status"] = _pipeline_trace_status(agency_trace)
        summary["agency_invocation_ids"] = agency_trace.get("invocation_ids") or []
    return summary


def _missing_pipeline_agency_trace(stage: str, exc: Exception) -> dict:
    return {
        "stage": stage,
        "stage_status": "blocked",
        "invocation_ids": [],
        "invocations": [],
        "error_code": "EXPERT_MODEL_CONFIG_MISSING",
        "error_message": str(exc),
    }


def _provider_rendering_block_trace() -> dict:
    return {
        "stage": "provider_rendering",
        "stage_status": "blocked",
        "invocation_ids": [],
        "invocations": [],
        "error_code": "PROVIDER_RENDERING_REQUIRES_PRODUCTION_JOB",
        "error_message": PROVIDER_RENDERING_REQUIRES_JOB,
    }


def _pipeline_trace_blocks(trace: dict | None) -> bool:
    return _pipeline_trace_status(trace) in {"blocked", "failed"}


def _pipeline_block_detail(run: PipelineRun, trace: dict) -> dict:
    return {
        "code": trace.get("error_code") or "AGENCY_REVIEW_BLOCKED",
        "message": trace.get("error_message") or "Agency expert review blocked this pipeline stage.",
        "stage": trace.get("stage"),
        "run_id": run.id,
        "agency_trace_status": _pipeline_trace_status(trace),
    }


def _store_pipeline_stage_trace(
    db: Session,
    run: PipelineRun,
    *,
    layer: int,
    phase: str,
    trace: dict,
    series: Series | None,
    status: str | None = None,
    input_summary: dict | None = None,
    output_summary: dict | None = None,
    error: str = "",
) -> None:
    layers = dict(run.layers_json or {})
    layer_key = str(layer)
    current = dict(layers.get(layer_key) or {})
    current.update(
        _agency_layer_summary(
            series,
            phase,
            status or current.get("status") or "running",
            input_summary=input_summary or current.get("input_summary") or {},
            output_summary=output_summary or current.get("output_summary") or {},
            error=error or current.get("error") or "",
            agency_trace=trace,
        )
    )
    layers[layer_key] = current
    run.layers_json = layers
    db.commit()


def _block_pipeline_stage(
    db: Session,
    run: PipelineRun,
    *,
    layer: int,
    phase: str,
    trace: dict,
    series: Series | None,
) -> None:
    trace_status = _pipeline_trace_status(trace)
    run.status = "failed" if trace_status == "failed" else "blocked"
    run.current_layer = layer
    run.error_log = trace.get("error_message") or trace.get("error_code") or trace_status
    _store_pipeline_stage_trace(
        db,
        run,
        layer=layer,
        phase=phase,
        trace=trace,
        series=series,
        status=trace_status,
        error=run.error_log,
    )


async def _run_pipeline_agency_stage(
    db: Session,
    run: PipelineRun,
    *,
    stage: str,
    stage_context: dict,
    episode: Episode | None = None,
) -> dict:
    try:
        runtime_config = resolve_runtime_model_config(db, "llm_agency_expert_review")
    except RuntimeModelConfigError as exc:
        return _missing_pipeline_agency_trace(stage, exc)

    orchestrator = AgencyOrchestrator()
    kwargs = {
        "series_id": run.series_id,
        "episode_id": episode.id if episode else run.episode_id,
        "pipeline_run_id": run.id,
        "stage_context": stage_context,
        "runtime_config": runtime_config,
    }
    if stage == "storyboard":
        return await orchestrator.run_storyboard_review(db, **kwargs)
    if stage == "image_stage":
        return await orchestrator.run_image_stage_review(db, **kwargs)
    if stage == "video_stage":
        return await orchestrator.run_video_stage_review(db, **kwargs)
    return await orchestrator.run_compose_review(db, **kwargs)


def _block_provider_rendering_without_job(
    db: Session,
    run: PipelineRun,
    *,
    series: Series | None,
    layer: int,
    phase: str = "render",
) -> None:
    run.status = "blocked"
    run.current_layer = layer
    run.error_log = PROVIDER_RENDERING_REQUIRES_JOB
    layers = dict(run.layers_json or {})
    for key, value in list(layers.items()):
        if key != str(layer) and isinstance(value, dict) and value.get("status") == "running" and len(value) == 1:
            layers[key] = {"status": "pending"}
    layers[str(layer)] = _agency_layer_summary(
        series,
        phase,
        "blocked",
        error=PROVIDER_RENDERING_REQUIRES_JOB,
        output_summary={"message": PROVIDER_RENDERING_REQUIRES_JOB},
        agency_trace=_provider_rendering_block_trace(),
    )
    run.layers_json = layers
    db.commit()


async def _run_all_layers(run_id: str) -> None:
    db = SessionLocal()
    try:
        run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        if not run:
            return
        series = db.query(Series).filter(Series.id == run.series_id).first()
        episode = None
        if run.episode_id:
            episode = db.query(Episode).filter(Episode.id == run.episode_id).first()
        storyboard = (episode.storyboard_json if episode else None) or run.layers_json or {}
        frames = storyboard.get("frames") or []
        if not frames:
            raise HTTPException(400, "Episode storyboard_json is empty. Run /api/director/auto-plan first.")

        run.started_at = run.started_at or datetime.now(BJT)
        run.current_layer = 0
        run.layers_json = {str(i): {"status": "pending"} for i in range(6)}
        db.commit()

        storyboard_trace = await _run_pipeline_agency_stage(
            db,
            run,
            stage="storyboard",
            episode=episode,
            stage_context={
                "storyboard": storyboard,
                "style_lock": ((series.story_bible_json or {}).get("style_lock") if series else {}),
            },
        )
        if _pipeline_trace_blocks(storyboard_trace):
            _block_pipeline_stage(db, run, layer=1, phase="storyboard", trace=storyboard_trace, series=series)
            return
        _store_pipeline_stage_trace(
            db,
            run,
            layer=1,
            phase="storyboard",
            trace=storyboard_trace,
            series=series,
            status="completed",
            input_summary={"frame_count": len(frames)},
            output_summary={"frame_count": len(frames)},
        )

        title_result = await _pixelle_request("POST", "/api/content/title", db, json={
            "series_id": run.series_id,
            "episode_id": run.episode_id,
            "storyboard": storyboard,
        })
        title = title_result.get("title") or (episode.title if episode else "") or storyboard.get("title", "")

        image_trace = await _run_pipeline_agency_stage(
            db,
            run,
            stage="image_stage",
            episode=episode,
            stage_context={"frames": frames, "style_lock": ((series.story_bible_json or {}).get("style_lock") if series else {})},
        )
        if _pipeline_trace_blocks(image_trace):
            _block_pipeline_stage(db, run, layer=2, phase="render", trace=image_trace, series=series)
            return
        _store_pipeline_stage_trace(
            db,
            run,
            layer=2,
            phase="render",
            trace=image_trace,
            series=series,
            status="completed",
            output_summary={"reference_urls": [f.get("reference_urls") or [] for f in frames]},
        )

        rendered_segments = []
        for index, frame in enumerate(frames):
            frame_id = frame.get("frame_id") or f"frame-{index + 1:03d}"
            narration_result = await _pixelle_request("POST", "/api/content/narration", db, json={
                "frame_id": frame_id,
                "narration": frame.get("narration", ""),
                "action": frame.get("action", ""),
                "emotion": frame.get("emotion", ""),
            })
            image_prompt_result = await _pixelle_request("POST", "/api/content/image-prompt", db, json={
                "frame_id": frame_id,
                "image_prompt": frame.get("image_prompt", ""),
                "reference_urls": frame.get("reference_urls") or [],
                "continuity_notes": frame.get("continuity_notes", ""),
            })
            rendered_segments.append({
                "frame_id": frame_id,
                "duration": frame.get("duration") or 5,
                "narration": narration_result.get("narration") or frame.get("narration", ""),
                "image_prompt": image_prompt_result.get("image_prompt") or frame.get("image_prompt", ""),
            })

        _block_provider_rendering_without_job(db, run, series=series, layer=4)
        return

    except Exception as exc:
        run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        if run:
            run.status = "failed"
            run.error_log = str(exc)
            layers = dict(run.layers_json or {})
            failed_layer = str(run.current_layer or 4)
            series = db.query(Series).filter(Series.id == run.series_id).first()
            layers[failed_layer] = _agency_layer_summary(series, "render", "failed", error=str(exc))
            run.layers_json = layers
            db.commit()
    finally:
        db.close()


@router.post("/start")
async def pipeline_start(
    body: PipelineStartRequest,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    if not body.director_plan and not body.episode_id:
        run = PipelineRun(
            series_id=body.series_id,
            episode_id=None,
            mode="step_by_step",
            model_ids={},
            layers_json={"0": {"status": "queued", "provider": "pixelle", "agency_trace_status": "legacy_summary"}},
            current_layer=0,
            status="pending",
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return {"ok": True, "run_id": run.id, "status": run.status}

    director_plan = body.director_plan or _load_director_plan_from_episode(
        db,
        body.series_id,
        body.episode_id,
    )
    if not director_plan:
        raise HTTPException(400, "director_plan is required when episode_id is not provided")

    run = PipelineRun(
        series_id=body.series_id,
        episode_id=body.episode_id,
        mode="storyboard",
        model_ids={},
        layers_json={"0": {"status": "queued", "provider": "pixelle", "agency_trace_status": "legacy_summary"}},
        current_layer=0,
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    series = db.query(Series).filter(Series.id == body.series_id).first()
    episode = None
    if body.episode_id:
        episode = db.query(Episode).filter(Episode.id == body.episode_id).first()
    storyboard_trace = await _run_pipeline_agency_stage(
        db,
        run,
        stage="storyboard",
        episode=episode,
        stage_context={
            "storyboard": director_plan,
            "style_lock": ((series.story_bible_json or {}).get("style_lock") if series else {}),
        },
    )
    if _pipeline_trace_blocks(storyboard_trace):
        _block_pipeline_stage(db, run, layer=1, phase="storyboard", trace=storyboard_trace, series=series)
        raise HTTPException(status_code=409, detail=_pipeline_block_detail(run, storyboard_trace))
    _store_pipeline_stage_trace(
        db,
        run,
        layer=1,
        phase="storyboard",
        trace=storyboard_trace,
        series=series,
        status="completed",
        input_summary={"frame_count": len(director_plan.get("frames") or [])},
        output_summary={"frame_count": len(director_plan.get("frames") or [])},
    )

    _block_provider_rendering_without_job(db, run, series=series, layer=0)
    raise HTTPException(409, PROVIDER_RENDERING_REQUIRES_JOB)


@router.get("/runs/{series_id}")
async def list_pipeline_runs(
    series_id: str,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    runs = db.query(PipelineRun).filter(
        PipelineRun.series_id == series_id,
    ).order_by(PipelineRun.created_at.desc()).all()
    return {"ok": True, "runs": [_serialize_run(r) for r in runs]}


@router.get("/runs/by-id/{run_id}")
async def get_pipeline_run_by_id(
    run_id: str,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if not run:
        raise HTTPException(404, "Pipeline run not found")
    return {"ok": True, "run": _serialize_run(run)}


@router.get("/runs/{series_id}/{run_id}")
async def get_pipeline_run(
    series_id: str,
    run_id: str,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    run = db.query(PipelineRun).filter(
        PipelineRun.id == run_id,
        PipelineRun.series_id == series_id,
    ).first()
    if not run:
        raise HTTPException(404, "Pipeline run not found")
    return {"ok": True, "run": _serialize_run(run)}

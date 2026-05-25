"""流水线编排 API — thin layer: director_plan → Pixelle-Video → result."""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_role
from app.db_models import Episode, PipelineRun, GeneratedVideo
from app.services.pixelle_client import _pixelle_request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

BJT = timezone(timedelta(hours=8))
POLL_INTERVAL = 10
POLL_MAX = 180
CIRCUIT_BREAKER_COOLDOWN = 60
_circuit_open_until = 0.0


class PipelineStartRequest(BaseModel):
    series_id: str
    episode_id: str | None = None
    director_plan: dict | None = None


def _build_storyboard_payload(plan: dict) -> dict:
    return {
        "mode": "storyboard",
        "title": plan.get("title", ""),
        "frames": plan.get("frames", []),
        "config": plan.get("config", {}),
    }


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


def _serialize_run(run: PipelineRun) -> dict:
    return {
        "id": run.id,
        "series_id": run.series_id,
        "episode_id": run.episode_id,
        "mode": run.mode,
        "model_ids": run.model_ids or {},
        "layers_json": run.layers_json or {},
        "current_layer": run.current_layer,
        "status": run.status,
        "error_log": run.error_log,
        "actual_cost_so_far": run.actual_cost_so_far,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


async def _submit_and_poll(payload: dict, db: Session) -> dict:
    import time as _time
    now = _time.time()
    global _circuit_open_until
    if now < _circuit_open_until:
        raise HTTPException(503, "Pixelle-Video temporarily unavailable (circuit open)")

    submit = await _pixelle_request("POST", "/api/video/generate/async", db, json=payload)

    task_id = submit.get("task_id") or submit.get("id", "")
    if not task_id:
        raise HTTPException(502, "Pixelle-Video returned no task_id")

    for attempt in range(POLL_MAX):
        await asyncio.sleep(POLL_INTERVAL)
        try:
            status = await _pixelle_request("GET", f"/api/tasks/{task_id}", db)
        except Exception as e:
            if attempt >= 2:
                _circuit_open_until = _time.time() + CIRCUIT_BREAKER_COOLDOWN
                raise HTTPException(502, f"Pixelle-Video polling failed: {e}")
            continue

        status_val = status.get("status", "")
        if status_val in ("completed", "succeeded", "done"):
            return {"provider": "pixelle", "status": "completed", "task_id": task_id, **status}
        if status_val in ("failed", "error"):
            raise HTTPException(500, f"Video generation failed: {status.get('error', status_val)}")

    raise HTTPException(504, f"Video generation timed out ({POLL_MAX * POLL_INTERVAL}s)")


@router.post("/start")
async def pipeline_start(
    body: PipelineStartRequest,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    if not body.director_plan and not body.episode_id:
        raise HTTPException(400, "director_plan is required when episode_id is not provided")

    director_plan = body.director_plan or _load_director_plan_from_episode(
        db,
        body.series_id,
        body.episode_id,
    )
    if not director_plan:
        raise HTTPException(400, "director_plan is required when episode_id is not provided")

    payload = _build_storyboard_payload(director_plan)

    run = PipelineRun(
        series_id=body.series_id,
        episode_id=body.episode_id,
        mode="storyboard",
        model_ids={},
        layers_json={"0": {"status": "queued", "provider": "pixelle"}},
        current_layer=0,
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        result = await _submit_and_poll(payload, db)
    except Exception:
        run.status = "failed"
        db.commit()
        raise

    video_path = result.get("video_path") or result.get("final_video_path", "")
    video = GeneratedVideo(
        task_id=str(run.id),
        keyword=director_plan.get("title", ""),
        title=director_plan.get("title", ""),
        video_path=video_path,
        duration=result.get("duration", 0),
        status="completed",
        pixelle_task_id=result.get("task_id", ""),
    )
    db.add(video)

    run.status = "completed"
    run.layers_json = {"0": {"status": "completed", "provider": "pixelle", **result}}
    run.completed_at = datetime.now(BJT)
    db.commit()

    return {
        "run_id": run.id,
        "status": "completed",
        "video_id": video.id,
        "video_path": video_path,
        "task_id": result.get("task_id", ""),
    }


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

"""流水线编排 API — 启动/状态查询/断点续传."""
import asyncio
import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.deps import verify_admin_token
from app.db_models import PipelineRun, Series

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])
PROXY_URL = "http://127.0.0.1:8000/api/pipeline-proxy"


async def _proxy_post(path: str, body: dict) -> dict:
    async with httpx.AsyncClient(base_url=PROXY_URL,
                                 timeout=httpx.Timeout(600, connect=10)) as c:
        r = await c.post(path, json=body)
        r.raise_for_status()
        return r.json()


@router.post("/start")
async def pipeline_start(series_id: str, episode_id: str = None,
                         mode: str = "step_by_step",
                         db: Session = Depends(get_db),
                         _: str = Depends(verify_admin_token)):
    """创建并启动新流水线."""
    run = PipelineRun(
        series_id=series_id, episode_id=episode_id,
        mode=mode, status="running",
    )
    db.add(run); db.commit(); db.refresh(run)
    run_id = run.id

    # Fire-and-forget with OWN session (not request-scoped as it closes after response)
    task = asyncio.create_task(_run_all_layers(run_id))
    task.add_done_callback(
        lambda t: logger.error(f"Pipeline task failed: {t.exception()}") if t.exception() else None
    )

    return {"ok": True, "run_id": run_id}


async def _run_all_layers(run_id: str):
    """顺序执行所有流水线层 (使用自有 DB session)."""
    db = SessionLocal()
    try:
        run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        if not run:
            return
        common = {"series_id": run.series_id, "episode_id": run.episode_id or ""}
        layer_endpoints = [
            "/assets/generate", "/story/generate", "/director/generate",
            "/render/execute", "/postproduction/execute",
        ]
        for i, ep in enumerate(layer_endpoints):
            run.current_layer = i
            db.commit()
            result = await _proxy_post(ep, common)
            layers = run.layers_json or {}
            layers[str(i)] = {"status": "completed", "result": result}
            run.layers_json = layers
            db.commit()
        run.status = "completed"
    except Exception as e:
        run.status = "failed"
        run.error_log = str(e)
    finally:
        db.commit()
        db.close()


@router.post("/resume/{run_id}")
async def pipeline_resume(run_id: str, db: Session = Depends(get_db),
                          _: str = Depends(verify_admin_token)):
    """从断点恢复流水线."""
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if not run or run.status not in ("pending", "running", "paused"):
        raise HTTPException(400, "PipelineRun not resumable")
    run.status = "running"; db.commit()
    task = asyncio.create_task(_run_all_layers(run_id))
    task.add_done_callback(
        lambda t: logger.error(f"Pipeline resume failed: {t.exception()}") if t.exception() else None
    )
    return {"ok": True, "run_id": run.id}


@router.get("/runs/{series_id}")
def list_runs(series_id: str, db: Session = Depends(get_db)):
    """查询某系列的所有流水线运行."""
    runs = db.query(PipelineRun).filter(
        PipelineRun.series_id == series_id
    ).order_by(PipelineRun.created_at.desc()).all()
    return {"ok": True, "runs": [
        {col.name: getattr(r, col.name) for col in PipelineRun.__table__.columns}
        for r in runs
    ]}


@router.get("/runs/{series_id}/{run_id}")
def get_run(series_id: str, run_id: str, db: Session = Depends(get_db)):
    """查询单个流水线运行详情 (用于前端轮询)."""
    run = db.query(PipelineRun).filter(
        PipelineRun.id == run_id, PipelineRun.series_id == series_id
    ).first()
    if not run:
        raise HTTPException(404, "PipelineRun not found")
    return {"ok": True, "run": {
        col.name: getattr(run, col.name) for col in PipelineRun.__table__.columns
    }}

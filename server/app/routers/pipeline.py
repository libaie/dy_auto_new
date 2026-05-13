"""流水线编排 API — 启动/状态查询/断点续传."""
import asyncio
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import PipelineRun, Series

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])
PROXY_URL = "http://127.0.0.1:8000/api/pipeline-proxy"
LAYER_COUNT = 6  # 0=assets, 1=story, 2=director, 3=render, 4=post, 5=done


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

    # Fire-and-forget: 异步执行所有层
    asyncio.ensure_future(_run_all_layers(db, run))

    return {"ok": True, "run_id": run.id}


async def _run_all_layers(db: Session, run: PipelineRun):
    """顺序执行所有流水线层."""
    common = {"series_id": run.series_id, "episode_id": run.episode_id or ""}
    layer_endpoints = [
        "/assets/generate", "/story/generate", "/director/generate",
        "/render/execute", "/postproduction/execute",
    ]
    try:
        for i, ep in enumerate(layer_endpoints):
            run.current_layer = i
            db.commit()
            await _proxy_post(ep, common)
            layers = run.layers_json or {}
            layers[str(i)] = {"status": "completed"}
            run.layers_json = layers
            db.commit()
        run.status = "completed"
    except Exception as e:
        run.status = "failed"
        run.error_log = str(e)
    finally:
        db.commit()


@router.post("/resume/{run_id}")
async def pipeline_resume(run_id: str, db: Session = Depends(get_db),
                          _: str = Depends(verify_admin_token)):
    """从断点恢复流水线."""
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if not run or run.status not in ("pending", "running", "paused"):
        raise HTTPException(400, "PipelineRun not resumable")
    run.status = "running"; db.commit()
    asyncio.ensure_future(_run_all_layers(db, run))
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

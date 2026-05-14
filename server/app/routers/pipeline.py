"""流水线编排 API — 启动/状态查询/断点续传."""
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.deps import verify_admin_token
from app.db_models import PipelineRun, Series
from app.services.pixelle_client import _pixelle_request

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

LAYER_ENDPOINTS = [
    ("POST", "/api/image/generate",           "assets"),
    ("POST", "/api/content/narration",         "story_narration"),
    ("GET",  "/api/content/title",             "story_title"),
    ("POST", "/api/content/image-prompt",      "director"),
    ("POST", "/api/video/generate/async",      "render"),
    ("POST", "/api/postproduction/execute",    "postproduction"),
]


@router.post("/start")
async def pipeline_start(series_id: str, episode_id: str = None,
                         mode: str = "step_by_step",
                         db: Session = Depends(get_db),
                         _: str = Depends(verify_admin_token)):
    """创建并启动新流水线."""
    # 幂等性检查 — 同一 series 不允许有运行中的重复 PipelineRun
    existing = db.query(PipelineRun).filter(
        PipelineRun.series_id == series_id,
        PipelineRun.status.in_(["pending", "running"]),
    ).first()
    if existing:
        raise HTTPException(409, f"Series {series_id} 已有运行中的流水线 (run_id={existing.id})")

    run = PipelineRun(
        series_id=series_id, episode_id=episode_id,
        mode=mode, status="running",
    )
    db.add(run); db.commit(); db.refresh(run)
    run_id = run.id

    task = asyncio.create_task(_run_all_layers(run_id))
    task.add_done_callback(
        lambda t: logger.error(f"Pipeline task failed: {t.exception()}") if t.exception() else None
    )

    return {"ok": True, "run_id": run_id}


async def _run_all_layers(run_id: str):
    """顺序执行所有流水线层 (使用自有 DB session)，支持从 checkpoint 恢复."""
    db = SessionLocal()
    run = None
    try:
        run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        if not run:
            return
        common = {"series_id": run.series_id, "episode_id": run.episode_id or ""}
        start_layer = run.current_layer
        for i in range(start_layer, len(LAYER_ENDPOINTS)):
            method, path, label = LAYER_ENDPOINTS[i]
            # Skip layers already marked completed in layers_json
            layers = run.layers_json or {}
            if layers.get(str(i), {}).get("status") == "completed":
                continue
            run.current_layer = i
            db.commit()
            result = await _pixelle_request(method, path, json=common)
            logger.info("Pipeline layer %d/%d (%s) — %s %s — OK",
                         i, len(LAYER_ENDPOINTS), label, method, path)
            layers[str(i)] = {"status": "completed", "result": result}
            run.layers_json = layers
            db.commit()
        run.status = "completed"
    except Exception as e:
        if run is not None:
            import traceback
            tb = traceback.format_exc()
            logger.error("Pipeline %s failed: %s\n%s", run_id, e, tb)
            run.status = "failed"
            run.error_log = f"{e}\n{tb}"
        else:
            logger.error(f"Pipeline _run_all_layers failed before run loaded: {e}")
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

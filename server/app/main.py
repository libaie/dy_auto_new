"""FastAPI application entry point."""
import sys
from pathlib import Path

# Allow running as `python app/main.py` from server/ directory
_server_dir = str(Path(__file__).resolve().parent.parent)
if _server_dir not in sys.path:
    sys.path.insert(0, _server_dir)

import asyncio
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from app.config import bj_now
from app.database import get_db, init_db, SessionLocal
from app.seed import seed_all
from app.routers import device, tasks, accounts, devices, auth, selectors, stats, content, account_groups, chains, settings, channels, prompt_templates, data, videos, pixelle, ai_config, characters, scenes, series, pipeline, audit, director, reference_data, dm_sequences, video_production, agency
from app.routers import image_creation, image_production
from app.routers import system_health
from app.services.ai_generator import ai_generator


async def _style_lock_worker(interval_seconds: float | None = None, batch_size: int | None = None):
    """Consume durable style-lock jobs so /style-lock does not depend on the page staying open."""
    import logging
    from app.routers import series as series_router

    interval = interval_seconds
    if interval is None:
        interval = float(os.getenv("STYLE_LOCK_WORKER_INTERVAL_SECONDS", "5"))
    interval = max(0.1, float(interval))
    worker_batch_size = batch_size
    if worker_batch_size is None:
        worker_batch_size = int(os.getenv("STYLE_LOCK_WORKER_BATCH_SIZE", "1"))
    worker_batch_size = max(1, min(int(worker_batch_size), 20))
    lease_id = f"style-lock-worker:{os.getpid()}"
    log = logging.getLogger("app.style_lock_worker")

    while True:
        db = SessionLocal()
        try:
            result = await series_router._run_style_lock_worker_step(
                db,
                lease_id=lease_id,
                batch_size=worker_batch_size,
            )
            if result.get("processed", 0) <= 0:
                await asyncio.sleep(interval)
            else:
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.warning("style-lock worker cycle failed", exc_info=True)
            await asyncio.sleep(interval)
        finally:
            db.close()


async def _one_sentence_reference_worker(interval_seconds: float | None = None, batch_size: int | None = None):
    """Resume one-sentence reference-generation jobs after page refresh or server restart."""
    import logging
    from app.db_models import VideoProductionRun
    from app.services.one_sentence_video_service import (
        ONE_SENTENCE_REFERENCE_RUNNING_STATUS,
        complete_one_sentence_reference_generation,
    )

    interval = interval_seconds
    if interval is None:
        interval = float(os.getenv("ONE_SENTENCE_REFERENCE_WORKER_INTERVAL_SECONDS", "10"))
    interval = max(1.0, float(interval))
    worker_batch_size = batch_size
    if worker_batch_size is None:
        worker_batch_size = int(os.getenv("ONE_SENTENCE_REFERENCE_WORKER_BATCH_SIZE", "1"))
    worker_batch_size = max(1, min(int(worker_batch_size), 5))
    log = logging.getLogger("app.one_sentence_reference_worker")

    while True:
        db = SessionLocal()
        processed = 0
        try:
            runs = (
                db.query(VideoProductionRun)
                .filter(VideoProductionRun.status == ONE_SENTENCE_REFERENCE_RUNNING_STATUS)
                .order_by(VideoProductionRun.created_at.asc(), VideoProductionRun.id.asc())
                .limit(worker_batch_size)
                .all()
            )
            for run in runs:
                trace = dict((run.model_trace_json or {}).get("one_sentence") or {})
                autostart = bool(trace.get("autostart_images_after_references"))
                try:
                    await complete_one_sentence_reference_generation(db, run.id, autostart_images=autostart)
                except Exception:
                    log.warning("one-sentence reference completion failed for run %s", run.id, exc_info=True)
                processed += 1
            await asyncio.sleep(0 if processed else interval)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.warning("one-sentence reference worker cycle failed", exc_info=True)
            await asyncio.sleep(interval)
        finally:
            db.close()


async def _offline_checker():
    """Background task: mark devices offline based on heartbeat staleness only.
    Uses in-memory cache from WS pings + DB from HTTP polls. Flushes
    in-memory heartbeats to DB each cycle so both sources are current.
    """
    from app.db_models import Device
    from app.ws_manager import pair_ws_manager
    from datetime import timedelta

    while True:
        await asyncio.sleep(30)
        db = SessionLocal()
        try:
            now = bj_now()

            # 1. Flush in-memory heartbeats to DB
            mem_heartbeats = pair_ws_manager.drain_heartbeats()
            if mem_heartbeats:
                try:
                    for device_id, seen_at in mem_heartbeats.items():
                        dev = db.query(Device).filter(Device.id == device_id).first()
                        if dev:
                            dev.last_seen_at = seen_at
                            dev.status = "online"
                    db.commit()
                except Exception:
                    # Re-merge on failure so next cycle retries
                    import logging
                    _hb_log = logging.getLogger("app.heartbeat")
                    _hb_log.warning("heartbeat flush failed, re-queuing %d", len(mem_heartbeats), exc_info=True)
                    for device_id, seen_at in mem_heartbeats.items():
                        if device_id not in pair_ws_manager._device_last_seen:
                            pair_ws_manager._device_last_seen[device_id] = seen_at

            # 2. Check liveness: both in-memory (already drained, checked above)
            #    and DB last_seen_at. Stale if >2 min without heartbeat.
            online_devices = db.query(Device).filter(Device.status == "online").all()
            cutoff_dt = now - timedelta(seconds=120)
            stale_ids = [
                d.id for d in online_devices
                if d.last_seen_at is None or d.last_seen_at < cutoff_dt
            ]

            if stale_ids:
                db.query(Device).filter(Device.id.in_(stale_ids)).update(
                    {"status": "offline"}, synchronize_session=False
                )
                db.commit()

                for device_id in stale_ids:
                    await pair_ws_manager.broadcast_to_admins({
                        "event": "device_status_changed",
                        "device_id": device_id,
                        "status": "offline",
                    }, user_ids=[db.get(Device, device_id).user_id])

            # Recovery uses the same duration-aware deadline as device dispatch.
            from app.services.task_service import task_service
            task_service.recover_stale_tasks(db, now=now)
        except Exception:
            import logging
            logging.getLogger("app.offline_checker").warning("checker cycle failed", exc_info=True)
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB and seed. Shutdown: stop checker."""
    if get_db not in app.dependency_overrides:
        seed_all()
        # Seed reference data at startup (idempotent)
        db = SessionLocal()
        try:
            from app.routers.reference_data import seed_reference_data
            seed_reference_data(db)
            from app.routers.ai_config import seed_ai_models
            seed_ai_models(db)
        finally:
            db.close()
    task = asyncio.create_task(_offline_checker())
    style_lock_task = asyncio.create_task(_style_lock_worker())
    one_sentence_reference_task = asyncio.create_task(_one_sentence_reference_worker())
    yield
    task.cancel()
    style_lock_task.cancel()
    one_sentence_reference_task.cancel()
    await asyncio.gather(task, style_lock_task, one_sentence_reference_task, return_exceptions=True)
    await ai_generator.aclose()
    from app.services import pixelle_client
    await pixelle_client.close_client()


app = FastAPI(
    title="抖音自动化助手",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_static_dir = Path(__file__).resolve().parent / "static"
_static_dir.mkdir(parents=True, exist_ok=True)
if not any(route.path == "/static" for route in app.routes):
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# Global exception log middleware — catches unhandled 500s with full traceback
from fastapi import Request
from fastapi.responses import JSONResponse
import traceback as _traceback
import logging
_logger = logging.getLogger("app")

@app.middleware("http")
async def _catch_unhandled_errors(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        _logger.error("UNHANDLED 500: %s %s\n%s", request.method, request.url.path, _traceback.format_exc())
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


app.include_router(device.router)
app.include_router(tasks.router)
app.include_router(accounts.router)
app.include_router(devices.router)
app.include_router(auth.router)
app.include_router(selectors.router)
app.include_router(stats.router)
app.include_router(content.router)
app.include_router(account_groups.router)
app.include_router(chains.router)
app.include_router(settings.router)
app.include_router(channels.router)
app.include_router(prompt_templates.router)
app.include_router(data.router)
app.include_router(videos.router)
app.include_router(pixelle.router)
app.include_router(pixelle.proxy_router)

app.include_router(ai_config.router)
app.include_router(characters.router)
app.include_router(scenes.router)
app.include_router(series.router)
app.include_router(pipeline.router)
app.include_router(audit.router)
app.include_router(director.router)
app.include_router(video_production.router)
app.include_router(agency.router)
app.include_router(image_creation.router)
app.include_router(image_production.router)
app.include_router(system_health.router)
app.include_router(reference_data.router)
app.include_router(dm_sequences.router)


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "0.3.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

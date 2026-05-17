"""FastAPI application entry point."""
import sys
from pathlib import Path

# Allow running as `python app/main.py` from server/ directory
_server_dir = str(Path(__file__).resolve().parent.parent)
if _server_dir not in sys.path:
    sys.path.insert(0, _server_dir)

import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import bj_now
from app.database import get_db, init_db, SessionLocal
from app.seed import seed_all
from app.routers import device, tasks, accounts, devices, auth, selectors, stats, content, account_groups, chains, settings, channels, prompt_templates, data, videos, pixelle, seedance, ai_config, characters, scenes, series, pipeline, audit, director, reference_data
from app.services.ai_generator import ai_generator


async def _offline_checker():
    """Background task: mark devices offline based on heartbeat staleness only.
    WS connection is a push optimization, not a liveness signal — devices
    fall back to HTTP polling when WS drops, and are still online as long
    as their heartbeat (last_seen_at) is current.
    """
    from app.db_models import Device
    from app.ws_manager import pair_ws_manager
    from datetime import timedelta

    while True:
        await asyncio.sleep(30)
        db = SessionLocal()
        try:
            now = bj_now()

            online_devices = db.query(Device).filter(Device.status == "online").all()

            # Stale heartbeat (>2 min) → device is truly offline
            cutoff_dt = now - timedelta(seconds=120)
            stale_ids = [
                d.id for d in online_devices
                if d.last_seen_at is None or d.last_seen_at < cutoff_dt
            ]

            if stale_ids:
                db.query(Device).filter(Device.id.in_(stale_ids)).update(
                    {"status": "offline"}, synchronize_session=False
                )

                # Mark RUNNING tasks on offline devices as FAILED
                from app.db_models import Task as DBTask
                orphaned = db.query(DBTask).filter(
                    DBTask.device_id.in_(stale_ids),
                    DBTask.status == "running",
                ).all()
                for t in orphaned:
                    t.status = "failed"
                    t.result = {"error": "设备离线，任务中断"}
                    t.completed_at = now

                db.commit()

                for device_id in stale_ids:
                    await pair_ws_manager.broadcast_to_admins({
                        "event": "device_status_changed",
                        "device_id": device_id,
                        "status": "offline",
                    })
        except Exception:
            pass
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
    yield
    task.cancel()
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
app.include_router(seedance.api_router)
app.include_router(seedance.proxy_router)
app.include_router(ai_config.router)
app.include_router(characters.router)
app.include_router(scenes.router)
app.include_router(series.router)
app.include_router(pipeline.router)
app.include_router(audit.router)
app.include_router(director.router)
app.include_router(reference_data.router)


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "0.3.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

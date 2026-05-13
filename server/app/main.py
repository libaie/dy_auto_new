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

from app.database import get_db, init_db, SessionLocal
from app.seed import seed_all
from app.routers import device, tasks, accounts, devices, auth, selectors, stats, content, account_groups, chains, settings, channels, prompt_templates, data, videos, pixelle, seedance, ai_config, characters, scenes, series, pipeline_proxy, pipeline, audit
from app.services.ai_generator import ai_generator


async def _offline_checker():
    """Background task: mark devices offline if no heartbeat or no WS connection."""
    from app.db_models import Device
    from app.ws_manager import pair_ws_manager
    from datetime import datetime, timezone, timedelta

    while True:
        await asyncio.sleep(30)
        db = SessionLocal()
        try:
            now = bj_now()

            # 1. Devices online in DB but with no active WS connection → offline immediately
            online_devices = db.query(Device).filter(Device.status == "online").all()
            no_ws_ids = [
                d.id for d in online_devices
                if not pair_ws_manager.is_device_online(d.id)
            ]

            # 2. Devices with stale heartbeat (>5 min) → offline
            cutoff_dt = now - timedelta(seconds=300)
            stale_ids = [
                d.id for d in online_devices
                if d.id not in no_ws_ids and d.last_seen_at and d.last_seen_at < cutoff_dt
            ]

            all_offline_ids = no_ws_ids + stale_ids
            if all_offline_ids:
                # Mark devices offline
                db.query(Device).filter(Device.id.in_(all_offline_ids)).update(
                    {"status": "offline"}, synchronize_session=False
                )

                # Mark RUNNING tasks on offline devices as FAILED (设备意外退出)
                from app.db_models import Task as DBTask
                orphaned = db.query(DBTask).filter(
                    DBTask.device_id.in_(all_offline_ids),
                    DBTask.status == "running",
                ).all()
                for t in orphaned:
                    t.status = "failed"
                    t.result = {"error": "设备离线，任务中断"}
                    t.completed_at = now

                db.commit()

                for device_id in all_offline_ids:
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
    # Skip production init if a test DB override is already in place
    if get_db not in app.dependency_overrides:
        seed_all()
    task = asyncio.create_task(_offline_checker())
    yield
    task.cancel()
    await ai_generator.aclose()


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
app.include_router(pipeline_proxy.router)
app.include_router(pipeline.router)
app.include_router(audit.router)


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "0.3.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

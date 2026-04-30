"""FastAPI application entry point."""
import sys
from pathlib import Path

# Allow running as `python app/main.py` from server/ directory
_server_dir = str(Path(__file__).resolve().parent.parent)
if _server_dir not in sys.path:
    sys.path.insert(0, _server_dir)

import asyncio
from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.database import get_db, init_db, SessionLocal
from app.seed import seed_all
from app.routers import device, tasks, accounts, devices, auth, selectors, stats, content, account_groups, chains
from app.services.ai_generator import ai_generator


async def _offline_checker():
    """Background task: mark devices offline if no heartbeat or no WS connection."""
    from app.db_models import Device
    from app.ws_manager import pair_ws_manager
    from datetime import datetime, timezone, timedelta

    while True:
        await asyncio.sleep(30)
        try:
            db = SessionLocal()
            now = datetime.now(timezone.utc).replace(tzinfo=None)

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
                db.query(Device).filter(Device.id.in_(all_offline_ids)).update(
                    {"status": "offline"}, synchronize_session=False
                )
                db.commit()

                for device_id in all_offline_ids:
                    await pair_ws_manager.broadcast_to_admins({
                        "event": "device_status_changed",
                        "device_id": device_id,
                        "status": "offline",
                    })
            db.close()
        except Exception:
            pass


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


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "0.3.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

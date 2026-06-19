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
from app.domains.account_operations import accounts_router, account_groups_router, chains_router, channels_router
from app.domains.content_collection import content_router, data_router, dm_sequences_router
from app.domains.creative_library import characters_router, reference_data_router, scenes_router
from app.domains.device_operations import admin_router, device_router
from app.domains.identity_access import auth_router
from app.domains.image_generation import image_creation_router, image_production_router
from app.domains.prompt_management import prompt_templates_router
from app.domains.reporting import stats_router
from app.domains.selector_management import selectors_router
from app.domains.system_operations import system_health_router
from app.domains.system_configuration import settings_router
from app.domains.task_operations import tasks_router
from app.domains.video_library import videos_router
from app.routers import pixelle, ai_config, series, pipeline, audit, director, video_production, agency
from app.services.ai_generator import ai_generator


async def _style_lock_worker(interval_seconds: float | None = None, batch_size: int | None = None):
    """Consume durable style-lock jobs so /style-lock does not depend on the page staying open."""
    import logging
    from app.domains.ai_video_series import style_lock

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
            result = await style_lock.run_style_lock_worker_step(
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


async def _story_plan_worker(interval_seconds: float | None = None, batch_size: int | None = None):
    """Consume durable story-planning jobs so the series page can safely refresh."""
    import logging
    from app.domains.ai_video_series import story_planning

    interval = interval_seconds
    if interval is None:
        interval = float(os.getenv("STORY_PLAN_WORKER_INTERVAL_SECONDS", "5"))
    interval = max(0.1, float(interval))
    worker_batch_size = batch_size
    if worker_batch_size is None:
        worker_batch_size = int(os.getenv("STORY_PLAN_WORKER_BATCH_SIZE", "1"))
    worker_batch_size = max(1, min(int(worker_batch_size), 20))
    lease_id = f"story-plan-worker:{os.getpid()}"
    log = logging.getLogger("app.story_plan_worker")

    while True:
        db = SessionLocal()
        try:
            result = await story_planning.run_story_plan_worker_step(
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
            log.warning("story-plan worker cycle failed", exc_info=True)
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
    from app.domains.device_operations.status_lifecycle import offline_checker

    await offline_checker()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB and seed. Shutdown: stop checker."""
    if get_db not in app.dependency_overrides:
        seed_all()
        # Seed reference data at startup (idempotent)
        db = SessionLocal()
        try:
            from app.domains.creative_library.reference_data_router import seed_reference_data
            seed_reference_data(db)
            from app.routers.ai_config import seed_ai_models
            seed_ai_models(db)
        finally:
            db.close()
    task = asyncio.create_task(_offline_checker())
    style_lock_task = asyncio.create_task(_style_lock_worker())
    story_plan_task = asyncio.create_task(_story_plan_worker())
    one_sentence_reference_task = asyncio.create_task(_one_sentence_reference_worker())
    yield
    task.cancel()
    style_lock_task.cancel()
    story_plan_task.cancel()
    one_sentence_reference_task.cancel()
    await asyncio.gather(task, style_lock_task, story_plan_task, one_sentence_reference_task, return_exceptions=True)
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


app.include_router(device_router.router)
app.include_router(tasks_router.router)
app.include_router(accounts_router.router)
app.include_router(admin_router.router)
app.include_router(auth_router.router)
app.include_router(selectors_router.router)
app.include_router(stats_router.router)
app.include_router(content_router.router)
app.include_router(account_groups_router.router)
app.include_router(chains_router.router)
app.include_router(settings_router.router)
app.include_router(channels_router.router)
app.include_router(prompt_templates_router.router)
app.include_router(data_router.router)
app.include_router(videos_router.router)
app.include_router(pixelle.router)
app.include_router(pixelle.proxy_router)

app.include_router(ai_config.router)
app.include_router(characters_router.router)
app.include_router(scenes_router.router)
app.include_router(series.router)
app.include_router(pipeline.router)
app.include_router(audit.router)
app.include_router(director.router)
app.include_router(video_production.router)
app.include_router(agency.router)
app.include_router(image_creation_router.router)
app.include_router(image_production_router.router)
app.include_router(system_health_router.router)
app.include_router(reference_data_router.router)
app.include_router(dm_sequences_router.router)


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "0.3.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

"""FastAPI application entry point."""
from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.database import get_db, init_db
from app.seed import seed_all
from app.routers import device, tasks, accounts, devices, auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB and seed. Shutdown: nothing."""
    # Skip production init if a test DB override is already in place
    if get_db not in app.dependency_overrides:
        seed_all()
    yield


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


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "0.3.0"}

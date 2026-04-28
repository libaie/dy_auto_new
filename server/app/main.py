from fastapi import FastAPI
from app.routers import device, tasks
from app.config import DEBUG

app = FastAPI(
    title="抖音自动化助手",
    version="0.1.0-mvp",
    debug=DEBUG,
)

app.include_router(device.router)
app.include_router(tasks.router)


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "0.1.0-mvp"}

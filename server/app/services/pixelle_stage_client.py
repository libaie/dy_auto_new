"""Client for Pixelle-Video stage APIs."""
from sqlalchemy.orm import Session

from app.services.pixelle_client import _pixelle_request


async def submit_image_batch(
    db: Session | None,
    run_id: str,
    episode_id: str,
    frames: list[dict],
    model_config: dict,
    template_config: dict | None = None,
) -> dict:
    payload = {
        "external_run_id": run_id,
        "episode_id": episode_id,
        "frames": frames,
        "model_config": model_config,
        "template_config": template_config or {},
    }
    return await _pixelle_request("POST", "/api/stages/images/batch", db, json=payload)


async def get_stage_task(db: Session | None, stage_task_id: str) -> dict:
    return await _pixelle_request("GET", f"/api/stages/tasks/{stage_task_id}", db)

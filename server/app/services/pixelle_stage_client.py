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


async def submit_video_batch(
    db: Session | None,
    run_id: str,
    frames: list[dict],
    model_config: dict,
    template_config: dict | None = None,
) -> dict:
    payload = {
        "external_run_id": run_id,
        "frames": frames,
        "model_config": model_config,
        "template_config": template_config or {},
    }
    return await _pixelle_request("POST", "/api/stages/videos/batch", db, json=payload)


async def submit_compose(
    db: Session | None,
    run_id: str,
    segments: list[dict],
    edit_manifest: dict,
    model_config: dict | None = None,
) -> dict:
    payload = {
        "external_run_id": run_id,
        "segments": segments,
        "edit_manifest": edit_manifest,
        "model_config": model_config or {"provider": "mock", "model": "compose"},
    }
    return await _pixelle_request("POST", "/api/stages/compose", db, json=payload)

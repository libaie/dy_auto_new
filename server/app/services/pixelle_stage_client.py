"""Client for Pixelle-Video stage APIs."""
from sqlalchemy.orm import Session

from app.services.pixelle_client import _pixelle_request


def _provider_stage_metadata(
    template_config: dict | None,
    *,
    external_task_id: str | None,
    provider_stage_task_id: str | None,
    provider_idempotency_key: str | None,
) -> dict:
    template = template_config if isinstance(template_config, dict) else {}
    return {
        "external_task_id": external_task_id or template.get("external_task_id"),
        "provider_stage_task_id": provider_stage_task_id or template.get("provider_stage_task_id"),
        "provider_idempotency_key": provider_idempotency_key or template.get("provider_idempotency_key"),
    }


def _add_provider_stage_metadata(payload: dict, metadata: dict) -> None:
    for key, value in metadata.items():
        if value:
            payload[key] = value


async def submit_image_batch(
    db: Session | None,
    run_id: str,
    episode_id: str,
    frames: list[dict],
    model_config: dict,
    template_config: dict | None = None,
    external_task_id: str | None = None,
    provider_stage_task_id: str | None = None,
    provider_idempotency_key: str | None = None,
) -> dict:
    payload = {
        "external_run_id": run_id,
        "episode_id": episode_id,
        "frames": frames,
        "model_config": model_config,
        "template_config": template_config or {},
    }
    _add_provider_stage_metadata(
        payload,
        _provider_stage_metadata(
            template_config,
            external_task_id=external_task_id,
            provider_stage_task_id=provider_stage_task_id,
            provider_idempotency_key=provider_idempotency_key,
        ),
    )
    return await _pixelle_request("POST", "/api/stages/images/batch", db, json=payload)


async def submit_image_create(
    db: Session | None,
    external_task_id: str,
    mode: str,
    capability_key: str,
    output_mode: str = "single",
    prompt: str = "",
    negative_prompt: str = "",
    source_image_url: str = "",
    reference_images: list[dict] | None = None,
    count: int = 1,
    size: str = "",
    output_format: str = "",
    response_format: str = "",
    provider_options: dict | None = None,
    model_config: dict | None = None,
    context: dict | None = None,
) -> dict:
    if not model_config:
        raise ValueError("submit_image_create requires a non-empty model_config")

    payload = {
        "external_task_id": external_task_id,
        "mode": mode,
        "capability_key": capability_key,
        "output_mode": output_mode,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "source_image_url": source_image_url,
        "reference_images": reference_images or [],
        "count": count,
        "size": size,
        "output_format": output_format,
        "response_format": response_format,
        "provider_options": provider_options or {},
        "model_config": model_config,
        "context": context or {},
    }
    return await _pixelle_request("POST", "/api/stages/images/create", db, json=payload)


async def get_stage_task(db: Session | None, stage_task_id: str) -> dict:
    return await _pixelle_request("GET", f"/api/stages/tasks/{stage_task_id}", db)


async def submit_video_batch(
    db: Session | None,
    run_id: str,
    frames: list[dict],
    model_config: dict,
    template_config: dict | None = None,
    external_task_id: str | None = None,
    provider_stage_task_id: str | None = None,
    provider_idempotency_key: str | None = None,
) -> dict:
    payload = {
        "external_run_id": run_id,
        "frames": frames,
        "model_config": model_config,
        "template_config": template_config or {},
    }
    _add_provider_stage_metadata(
        payload,
        _provider_stage_metadata(
            template_config,
            external_task_id=external_task_id,
            provider_stage_task_id=provider_stage_task_id,
            provider_idempotency_key=provider_idempotency_key,
        ),
    )
    return await _pixelle_request("POST", "/api/stages/videos/batch", db, json=payload)


async def submit_compose(
    db: Session | None,
    run_id: str,
    segments: list[dict],
    edit_manifest: dict,
    model_config: dict | None = None,
    external_task_id: str | None = None,
    provider_stage_task_id: str | None = None,
    provider_idempotency_key: str | None = None,
) -> dict:
    if not model_config:
        raise ValueError("submit_compose requires a non-empty model_config")

    payload = {
        "external_run_id": run_id,
        "segments": segments,
        "edit_manifest": edit_manifest,
        "model_config": model_config,
    }
    if external_task_id:
        payload["external_task_id"] = external_task_id
    if provider_stage_task_id:
        payload["provider_stage_task_id"] = provider_stage_task_id
    if provider_idempotency_key:
        payload["provider_idempotency_key"] = provider_idempotency_key
    return await _pixelle_request("POST", "/api/stages/compose", db, json=payload)

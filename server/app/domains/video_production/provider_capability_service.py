from copy import deepcopy

from app.domains.video_production.production_errors import ProductionErrorCode, ProductionRepairableError


DEFAULT_REAL_PROVIDER_CAPABILITY = {
    "supports_external_task_id": False,
    "supports_task_query": False,
    "supports_cancel": False,
    "returns_usage": False,
    "returns_asset_url": False,
    "supports_text_to_image": False,
    "supports_image_to_video": False,
    "supports_video_composition": False,
    "max_duration_seconds": None,
    "max_reference_images": 0,
    "max_concurrent_tasks": 1,
    "real_paid_allowed": False,
}


def _merge_dict(target: dict, source: object) -> None:
    if isinstance(source, dict):
        target.update(source)


def capability_from_model_config(model_config: dict | None) -> dict:
    capability = deepcopy(DEFAULT_REAL_PROVIDER_CAPABILITY)
    if not model_config:
        return capability

    _merge_dict(capability, model_config.get("config_json"))
    _merge_dict(capability, model_config.get("provider_options"))
    _merge_dict(capability, model_config.get("capability"))
    return capability


def assert_real_paid_allowed(capability: dict) -> None:
    required = (
        "real_paid_allowed",
        "supports_external_task_id",
        "supports_task_query",
        "returns_asset_url",
        "returns_usage",
    )
    missing = [key for key in required if capability.get(key) is not True]
    if missing:
        raise ProductionRepairableError(
            code=ProductionErrorCode.PROVIDER_SUBMIT_FAILED,
            message="Provider model is not configured for safe real paid execution.",
            cause="provider_capability_gate_failed",
            repair_action="Enable paid execution only for providers that support external task IDs, task query, asset URLs, and usage/cost reporting.",
            repair_route="/video-production",
            retryable=False,
            affected_ids=missing,
        )

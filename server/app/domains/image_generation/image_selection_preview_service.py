from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.config import bj_now
from app.db.models.image_production import ImageProductionStrategy
from app.db_models import AIModel, ImageSelectionPreview
from app.domains.image_generation.image_creation_errors import image_error
from app.services.image_creation_service import MODE_TO_SCENE_CAPABILITY, contains_protected_provider_option_key
from app.domains.image_generation.image_model_selection_service import resolve_image_model_selection
from app.domains.image_generation.image_production_policy_runtime import estimate_image_cost, preview_image_capacity, preview_review_gate
from app.domains.image_generation.image_selection_preview_hash import selection_preview_hash_inputs, selection_preview_request_hash
from app.domains.image_generation.image_production_strategy_service import strategy_payload


def _provider_schema(model: AIModel) -> dict[str, Any]:
    schema = (model.config_json or {}).get("provider_options_schema") or {}
    return schema if isinstance(schema, dict) else {}


def _validate_provider_options(provider_options: dict[str, Any], model: AIModel) -> None:
    schema = _provider_schema(model)
    unknown = set(provider_options) - set(schema)
    if unknown or contains_protected_provider_option_key(provider_options):
        raise image_error(
            400,
            "IMAGE_PROVIDER_OPTIONS_INVALID",
            "Provider options contain unsupported fields.",
            "Use only the options exposed by the selected model configuration.",
            retryable=False,
        )

    for key, value in provider_options.items():
        spec = schema.get(key) or {}
        option_type = spec.get("type")
        if option_type == "boolean" and not isinstance(value, bool):
            raise image_error(400, "IMAGE_PROVIDER_OPTIONS_INVALID", f"{key} must be boolean.", "Fix provider options.", retryable=False)
        if option_type == "select" and value not in set(spec.get("options") or []):
            raise image_error(400, "IMAGE_PROVIDER_OPTIONS_INVALID", f"{key} is not an allowed option.", "Fix provider options.", retryable=False)
        if option_type == "number":
            try:
                numeric = float(value)
            except (TypeError, ValueError) as exc:
                raise image_error(400, "IMAGE_PROVIDER_OPTIONS_INVALID", f"{key} must be numeric.", "Fix provider options.", retryable=False) from exc
            if spec.get("min") is not None and numeric < float(spec["min"]):
                raise image_error(400, "IMAGE_PROVIDER_OPTIONS_INVALID", f"{key} is below the allowed minimum.", "Fix provider options.", retryable=False)
            if spec.get("max") is not None and numeric > float(spec["max"]):
                raise image_error(400, "IMAGE_PROVIDER_OPTIONS_INVALID", f"{key} exceeds the allowed maximum.", "Fix provider options.", retryable=False)


def _get_strategy(db: Session, strategy_id: str | None) -> ImageProductionStrategy | None:
    if not strategy_id:
        return None
    strategy = db.query(ImageProductionStrategy).filter(ImageProductionStrategy.id == strategy_id).first()
    if not strategy:
        raise image_error(
            404,
            "IMAGE_STRATEGY_NOT_FOUND",
            "Image production strategy was not found.",
            "Choose another strategy.",
            retryable=False,
            affected_ids=[strategy_id],
        )
    if strategy.status != "active":
        raise image_error(
            409,
            "IMAGE_STRATEGY_ARCHIVED",
            "Strategy is not active.",
            "Choose an active strategy.",
            retryable=False,
            affected_ids=[strategy_id],
        )
    return strategy


def _selected_model_payload(model: AIModel, scene_key: str, capability_key: str) -> dict[str, Any]:
    config = model.config_json or {}
    return {
        "model_id": model.id,
        "name": model.name,
        "provider": model.provider,
        "model_name": model.model_name,
        "scene_key": scene_key,
        "capability_key": capability_key,
        "config_version": config.get("config_version", 1),
    }


def create_selection_preview(db: Session, payload: dict[str, Any], user_id: str | None = None) -> dict[str, Any]:
    mode = payload.get("mode")
    if mode not in MODE_TO_SCENE_CAPABILITY:
        raise image_error(400, "IMAGE_MODE_UNSUPPORTED", "Unsupported image mode.", "Choose a supported image mode.", retryable=False)

    scene_key, capability_key, _output_mode = MODE_TO_SCENE_CAPABILITY[mode]
    strategy = _get_strategy(db, payload.get("strategy_id"))
    if strategy and payload.get("strategy_version") is not None and int(payload["strategy_version"]) != strategy.version:
        raise image_error(
            409,
            "IMAGE_STRATEGY_VERSION_CONFLICT",
            "Strategy version is stale.",
            "Reload the strategy and run selection preview again.",
            retryable=False,
            affected_ids=[strategy.id],
        )
    if strategy and mode not in (strategy.supported_modes_json or []):
        raise image_error(
            422,
            "IMAGE_STRATEGY_MODE_UNSUPPORTED",
            "Strategy does not support this mode.",
            "Choose another strategy or mode.",
            retryable=False,
            affected_ids=[strategy.id],
        )

    selection = resolve_image_model_selection(
        db,
        scene_key=scene_key,
        capability_key=capability_key,
        requested_model_id=payload.get("model_id"),
        strategy=strategy,
    )
    selected_model = selection["selected_model"]
    fallback_candidates = selection["fallback_candidates"]
    selected_model_id = selected_model["model_id"] if selected_model else None
    cost_estimate = estimate_image_cost(db, payload=payload, strategy=strategy, model_config=None)
    capacity = preview_image_capacity(db, strategy, selected_model_id)
    review_gate = preview_review_gate(db, strategy, payload.get("destination_role"))

    if not selected_model and fallback_candidates:
        return {
            "ok": False,
            "preview_blocked": True,
            "confirmation_required": True,
            "error_code": "IMAGE_FALLBACK_REQUIRES_CONFIRMATION",
            "message": "Primary model cannot satisfy this request, but fallback models are available.",
            "selected_model": None,
            "strategy": strategy_payload(strategy) if strategy else None,
            "selection_explanation": {
                "requested_mode": mode,
                "destination_role": payload.get("destination_role"),
                "strategy_id": strategy.id if strategy else None,
                "strategy_version": strategy.version if strategy else None,
                "candidate_count": selection["candidate_count"],
                "rejected_candidates": selection["rejected_candidates"],
                "selected_model_id": None,
                "selected_reason": None,
                "fallback_candidates": fallback_candidates,
            },
            "cost_estimate": cost_estimate,
            "time_estimate": cost_estimate.get("time_estimate") or {},
            "capacity": capacity,
            "review_gate": review_gate,
            "request_hash": None,
            "selection_preview_id": None,
            "expires_at": None,
            "warnings": selection.get("warnings") or ["fallback_requires_confirmation"],
            "fallback_candidates": fallback_candidates,
            "rescue_actions": selection.get("rescue_actions") or [],
        }

    if not selected_model:
        raise image_error(
            422,
            "IMAGE_MODEL_SELECTION_EMPTY",
            "No enabled model supports this image request.",
            "Configure a compatible image model.",
            "/ai-config",
            retryable=False,
        )

    selected = db.query(AIModel).filter(AIModel.id == selected_model["model_id"]).first()
    if not selected:
        raise image_error(
            422,
            "IMAGE_MODEL_SELECTION_EMPTY",
            "No enabled model supports this image request.",
            "Configure a compatible image model.",
            "/ai-config",
            retryable=False,
        )

    provider_options = dict(strategy.provider_options_json or {}) if strategy else {}
    provider_options.update(payload.get("provider_options") or {})
    _validate_provider_options(provider_options, selected)
    cost_estimate = estimate_image_cost(
        db,
        payload=payload,
        strategy=strategy,
        model_config={"provider": selected.provider, "config": selected.config_json or {}},
    )

    request_hash = selection_preview_request_hash(selection_preview_hash_inputs(
        payload=payload,
        mode=mode,
        destination_role=payload.get("destination_role"),
        strategy_id=strategy.id if strategy else None,
        strategy_version=strategy.version if strategy else None,
        selected_model_id=selected.id,
        selected_model_config_version=(selected.config_json or {}).get("config_version", 1),
        provider_options=provider_options,
    ))
    explanation = {
        "requested_mode": mode,
        "destination_role": payload.get("destination_role"),
        "strategy_id": strategy.id if strategy else None,
        "strategy_version": strategy.version if strategy else None,
        "candidate_count": selection["candidate_count"],
        "rejected_candidates": selection["rejected_candidates"],
        "selected_model_id": selected_model["model_id"],
        "selected_reason": selection["selected_reason"],
        "fallback_candidates": fallback_candidates,
    }
    expires_at = bj_now() + timedelta(minutes=15)
    response = {
        "ok": True,
        "selected_model": _selected_model_payload(selected, scene_key, capability_key),
        "strategy": strategy_payload(strategy) if strategy else None,
        "selection_explanation": explanation,
        "cost_estimate": cost_estimate,
        "time_estimate": cost_estimate.get("time_estimate") or {},
        "capacity": capacity,
        "review_gate": review_gate,
        "request_hash": request_hash,
        "selection_preview_id": None,
        "expires_at": expires_at.isoformat(),
        "warnings": selection.get("warnings") or [],
        "preview_blocked": False,
        "confirmation_required": False,
        "fallback_candidates": fallback_candidates,
        "rescue_actions": [],
    }

    preview = ImageSelectionPreview(
        user_id=user_id,
        strategy_id=strategy.id if strategy else None,
        strategy_version=strategy.version if strategy else None,
        mode=mode,
        destination_role=payload.get("destination_role"),
        model_id=payload.get("model_id"),
        selected_model_id=selected.id,
        request_hash=request_hash,
        response_json=response,
        expires_at=expires_at,
    )
    db.add(preview)
    db.commit()
    db.refresh(preview)
    response["selection_preview_id"] = preview.id
    preview.response_json = response
    db.commit()
    return response

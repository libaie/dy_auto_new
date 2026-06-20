from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models.image_production import ImageProductionStrategy
from app.db.models import AIModel
from app.domains.model_configuration.runtime_model_config import _model_supports_capability


def _model_identity(model: AIModel) -> dict[str, Any]:
    return {
        "model_id": model.id,
        "name": model.name,
        "provider": model.provider,
        "model_name": model.model_name,
    }


def _selected_model_payload(model: AIModel, scene_key: str, capability_key: str) -> dict[str, Any]:
    config = model.config_json or {}
    return {
        **_model_identity(model),
        "scene_key": scene_key,
        "capability_key": capability_key,
        "config_version": config.get("config_version", 1),
    }


def _rejected_candidate(model: AIModel, reason: str, detail: str, rescue_action: str) -> dict[str, Any]:
    return {
        **_model_identity(model),
        "reason": reason,
        "detail": detail,
        "rescue_action": rescue_action,
    }


def _fallback_model_payload(model: AIModel) -> dict[str, Any]:
    return {
        **_model_identity(model),
        "risk_labels": ["requires_manual_confirmation"],
    }


def _fallback_model_ids(strategy: ImageProductionStrategy | None) -> list[str]:
    if not strategy or not isinstance(strategy.fallback_model_ids_json, list):
        return []
    return [model_id for model_id in strategy.fallback_model_ids_json if isinstance(model_id, str)]


def resolve_image_model_selection(
    db: Session,
    *,
    scene_key: str,
    capability_key: str,
    requested_model_id: str | None = None,
    strategy: ImageProductionStrategy | None = None,
) -> dict[str, Any]:
    models = (
        db.query(AIModel)
        .filter(AIModel.model_type == "image")
        .order_by(AIModel.sort_order.asc(), AIModel.created_at.asc())
        .all()
    )
    fallback_ids = _fallback_model_ids(strategy)
    models_by_id = {model.id: model for model in models}
    fallback_candidates = [
        _fallback_model_payload(model)
        for model_id in fallback_ids
        if (model := models_by_id.get(model_id))
        and model.enabled
        and _model_supports_capability(model, scene_key, capability_key)
    ]
    fallback_candidate_ids = {candidate["model_id"] for candidate in fallback_candidates}

    preferred_model_id = requested_model_id or (strategy.default_model_id if strategy else None)
    preferred_reason = "requested_model" if requested_model_id else "strategy_default_model"
    selected_model = None
    selected_reason = None
    rejected_candidates: list[dict[str, Any]] = []

    for model in models:
        if not model.enabled:
            rejected_candidates.append(_rejected_candidate(
                model,
                "disabled",
                "Model is disabled.",
                "Enable the model before selecting it.",
            ))
            continue

        supports_capability = _model_supports_capability(model, scene_key, capability_key)
        if preferred_model_id:
            if model.id != preferred_model_id:
                if model.id not in fallback_candidate_ids:
                    rejected_candidates.append(_rejected_candidate(
                        model,
                        "not_preferred_model",
                        f"Selection is restricted to preferred model {preferred_model_id}.",
                        "Clear the requested model or update the strategy default model.",
                    ))
                continue
            if supports_capability:
                selected_model = model
                selected_reason = preferred_reason
            else:
                rejected_candidates.append(_rejected_candidate(
                    model,
                    "capability_not_supported",
                    f"Model does not support {scene_key}/{capability_key}.",
                    "Choose a model that supports this scene and capability.",
                ))
            continue

        if not selected_model and supports_capability:
            selected_model = model
            selected_reason = "first_supported_model"
            continue

        if not supports_capability:
            rejected_candidates.append(_rejected_candidate(
                model,
                "capability_not_supported",
                f"Model does not support {scene_key}/{capability_key}.",
                "Choose a model that supports this scene and capability.",
            ))

    warnings: list[str] = []
    rescue_actions: list[dict[str, Any]] = []
    if fallback_candidates and not selected_model:
        warnings.append("fallback_requires_confirmation")
        rescue_actions.extend({
            "type": "confirm_fallback_model",
            "label": "Use fallback model",
            "model_id": candidate["model_id"],
        } for candidate in fallback_candidates)

    return {
        "selected_model": (
            _selected_model_payload(selected_model, scene_key, capability_key)
            if selected_model
            else None
        ),
        "selected_reason": selected_reason,
        "candidate_count": len(models),
        "rejected_candidates": rejected_candidates,
        "fallback_candidates": fallback_candidates,
        "warnings": warnings,
        "rescue_actions": rescue_actions,
    }

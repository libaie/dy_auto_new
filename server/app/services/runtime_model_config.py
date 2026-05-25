"""Resolve dy_auto AIModel rows into runtime Pixelle stage payloads."""
from sqlalchemy.orm import Session

from app.db_models import AIModel
from app.services.crypto import decrypt


class RuntimeModelConfigError(ValueError):
    pass


def resolve_runtime_model_config(db: Session, scene_key: str, explicit_model_id: str | None = None) -> dict:
    query = db.query(AIModel).filter(AIModel.enabled == True)
    if explicit_model_id:
        query = query.filter(AIModel.id == explicit_model_id)
    else:
        query = query.filter(AIModel.config_json["scene_key"].as_string() == scene_key)
    model = query.order_by(AIModel.sort_order.asc(), AIModel.created_at.asc()).first()
    if not model:
        raise RuntimeModelConfigError(f"No enabled model configured for scene '{scene_key}'")

    api_key = ""
    if model.api_key:
        api_key = decrypt(model.api_key)

    config = model.config_json or {}
    return {
        "scene_key": scene_key,
        "model_id": model.id,
        "provider": model.provider,
        "model": model.model_name or "",
        "base_url": model.base_url or "",
        "api_key": api_key,
        "config": config,
        "config_version": config.get("config_version", 1),
    }


def redact_runtime_model_config(config: dict) -> dict:
    redacted = dict(config or {})
    redacted.pop("api_key", None)
    if isinstance(redacted.get("config"), dict):
        redacted["config"] = {
            key: value for key, value in redacted["config"].items()
            if "key" not in key.lower() and "secret" not in key.lower()
        }
    return redacted

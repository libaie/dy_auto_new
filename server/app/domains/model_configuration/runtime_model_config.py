"""模型配置业务域模块。

模型配置业务域，负责 AI 模型注册、运行时配置解析和连接检测。本文件负责 runtime_model_config 相关业务规则、状态转换和外部系统边界。
"""

from sqlalchemy.orm import Session

from app.db.models.model_configuration import AIModel
from app.domains.system_configuration.crypto import decrypt


class RuntimeModelConfigError(ValueError):
    """业务类：承载 RuntimeModelConfigError 相关的数据结构、状态或业务协作。"""
    pass


def _configured_scene_keys(model: AIModel) -> list[str]:
    """业务函数：处理 _configured_scene_keys 对应的业务流程、校验或数据转换。"""
    config = model.config_json or {}
    configured_scenes = config.get("scene_keys")
    if isinstance(configured_scenes, list):
        return [scene for scene in configured_scenes if isinstance(scene, str) and scene]
    scene = config.get("scene_key")
    return [scene] if isinstance(scene, str) and scene else []


def _model_supports_scene(model: AIModel, scene_key: str) -> bool:
    """业务函数：处理 _model_supports_scene 对应的业务流程、校验或数据转换。"""
    return scene_key in _configured_scene_keys(model)


def resolve_runtime_model_config(db: Session, scene_key: str, explicit_model_id: str | None = None) -> dict:
    """业务函数：处理 resolve_runtime_model_config 对应的业务流程、校验或数据转换。"""
    query = db.query(AIModel).filter(AIModel.enabled == True)
    if explicit_model_id:
        query = query.filter(AIModel.id == explicit_model_id)

    models = query.order_by(AIModel.sort_order.asc(), AIModel.created_at.asc()).all()
    model = next((candidate for candidate in models if _model_supports_scene(candidate, scene_key)), None)
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


def _model_supports_capability(model: AIModel, scene_key: str, capability_key: str) -> bool:
    """业务函数：处理 _model_supports_capability 对应的业务流程、校验或数据转换。"""
    config = model.config_json or {}
    if not _model_supports_scene(model, scene_key):
        return False

    capabilities_by_scene = config.get("capabilities_by_scene")
    if isinstance(capabilities_by_scene, dict) and isinstance(capabilities_by_scene.get(scene_key), dict):
        return bool(capabilities_by_scene[scene_key].get(capability_key))

    capabilities = config.get("capabilities")
    if isinstance(capabilities, dict):
        return bool(capabilities.get(capability_key))

    return scene_key == "image_generation" and capability_key == "text_to_image"


def resolve_image_model_for_capability(
    db: Session,
    scene_key: str,
    capability_key: str,
    explicit_model_id: str | None = None,
) -> dict:
    """业务函数：处理 resolve_image_model_for_capability 对应的业务流程、校验或数据转换。"""
    query = db.query(AIModel).filter(AIModel.enabled == True, AIModel.model_type == "image")
    if explicit_model_id:
        query = query.filter(AIModel.id == explicit_model_id)

    models = query.order_by(AIModel.sort_order.asc(), AIModel.created_at.asc()).all()
    for model in models:
        if _model_supports_capability(model, scene_key, capability_key):
            resolved = resolve_runtime_model_config(db, scene_key, explicit_model_id=model.id)
            resolved["scene_key"] = scene_key
            resolved["capability_key"] = capability_key
            return resolved

    raise RuntimeModelConfigError(
        f"IMAGE_CAPABILITY_UNSUPPORTED: no enabled image model supports scene '{scene_key}' "
        f"with capability '{capability_key}'"
    )


def redact_runtime_model_config(config: dict) -> dict:
    """业务函数：处理 redact_runtime_model_config 对应的业务流程、校验或数据转换。"""
    redacted = dict(config or {})
    redacted.pop("api_key", None)
    if isinstance(redacted.get("config"), dict):
        redacted["config"] = {
            key: value for key, value in redacted["config"].items()
            if "key" not in key.lower() and "secret" not in key.lower()
        }
    return redacted

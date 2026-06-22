"""模型配置业务域模块。

模型配置业务域，负责 AI 模型注册、运行时配置解析和连接检测。本文件负责 model_schema 相关业务规则、状态转换和外部系统边界。
"""

from app.data.model_schema_data import get_schema, SCENES, PROVIDERS, PROTOCOLS, CUSTOM_FIELD_POLICY


def get_scene_by_key(scene_key: str) -> dict | None:
    """业务函数：处理 get_scene_by_key 对应的业务流程、校验或数据转换。

    入参：scene_key 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    """Return the scene definition for a scene_key, or None if unknown."""
    for scene in SCENES:
        if scene["key"] == scene_key:
            return scene
    return None


def get_providers_for_scene(scene_key: str) -> list[str]:
    """业务函数：处理 get_providers_for_scene 对应的业务流程、校验或数据转换。

    入参：scene_key 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    """Providers available for a given scene."""
    scene = get_scene_by_key(scene_key)
    return scene["providers"] if scene else []


def get_provider_preset(provider: str) -> dict:
    """业务函数：处理 get_provider_preset 对应的业务流程、校验或数据转换。

    入参：provider 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    """Return provider metadata (label, default_base_url, protocol, test_strategy)."""
    return PROVIDERS.get(provider, {
        "label": provider,
        "default_base_url": "",
        "protocol": "http_custom",
        "test_strategy": "health_check",
        "test_path": "/",
    })


def get_schema_payload() -> dict:
    """业务函数：处理 get_schema_payload 对应的业务流程、校验或数据转换。

    入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    """Full schema for the frontend GET /api/ai-models/schema endpoint."""
    return get_schema()

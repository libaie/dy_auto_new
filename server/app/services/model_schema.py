"""Schema service — owns application scene definitions and returns metadata to the frontend."""
from app.data.model_schema_data import get_schema, SCENES, PROVIDERS, PROTOCOLS, CUSTOM_FIELD_POLICY


def get_scene_by_key(scene_key: str) -> dict | None:
    """Return the scene definition for a scene_key, or None if unknown."""
    for scene in SCENES:
        if scene["key"] == scene_key:
            return scene
    return None


def get_providers_for_scene(scene_key: str) -> list[str]:
    """Providers available for a given scene."""
    scene = get_scene_by_key(scene_key)
    return scene["providers"] if scene else []


def get_provider_preset(provider: str) -> dict:
    """Return provider metadata (label, default_base_url, protocol, test_strategy)."""
    return PROVIDERS.get(provider, {
        "label": provider,
        "default_base_url": "",
        "protocol": "http_custom",
        "test_strategy": "health_check",
        "test_path": "/",
    })


def get_schema_payload() -> dict:
    """Full schema for the frontend GET /api/ai-models/schema endpoint."""
    return get_schema()

"""Schema endpoint and model_schema service tests."""
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_schema_returns_scenes_providers_protocols(client):
    resp = client.get("/api/ai-models/schema")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert len(data["scenes"]) == 8
    assert len(data["providers"]) >= 10
    assert len(data["protocols"]) >= 5
    assert len(data["common_fields"]) == 6
    assert data["custom_field_policy"]["enabled"] is True


def test_schema_scene_has_required_keys(client):
    resp = client.get("/api/ai-models/schema")
    data = resp.json()
    for scene in data["scenes"]:
        for key in ("key", "label", "model_type", "description", "providers", "fields"):
            assert key in scene, f"Scene {scene.get('key', '?')} missing {key}"


def test_schema_providers_have_test_strategy(client):
    resp = client.get("/api/ai-models/schema")
    data = resp.json()
    for provider_key, provider in data["providers"].items():
        assert "test_strategy" in provider, f"Provider {provider_key} missing test_strategy"


def test_scene_key_mapping(client):
    """Verify scene keys map to correct model_types."""
    from app.data.model_schema_data import scene_key_to_model_type
    assert scene_key_to_model_type("script_generation") == "llm"
    assert scene_key_to_model_type("llm_agency_expert_review") == "llm"
    assert scene_key_to_model_type("image_generation") == "image"
    assert scene_key_to_model_type("image_editing") == "image"
    assert scene_key_to_model_type("video_rendering") == "video"
    assert scene_key_to_model_type("video_composition") == "video"
    assert scene_key_to_model_type("tts_synthesis") == "tts"
    assert scene_key_to_model_type("quality_audit") == "audit"


def test_schema_contains_image_editing_scene(client):
    resp = client.get("/api/ai-models/schema")
    assert resp.status_code == 200
    data = resp.json()

    scene = next(item for item in data["scenes"] if item["key"] == "image_editing")
    field_keys = {field["key"] for field in scene["fields"]}

    assert scene["label"] == "Image · 以图改图"
    assert scene["model_type"] == "image"
    assert "seedance" in scene["providers"]
    assert {"max_reference_images", "max_output_images", "supports_image_set"} <= field_keys


def test_scene_key_mapping_supports_image_editing():
    from app.data.model_schema_data import scene_key_to_model_type
    assert scene_key_to_model_type("image_editing") == "image"


def test_agency_expert_review_scene_uses_runtime_supported_providers(client):
    resp = client.get("/api/ai-models/schema")
    data = resp.json()

    scene = next(item for item in data["scenes"] if item["key"] == "llm_agency_expert_review")

    assert scene["model_type"] == "llm"
    assert scene["label"] == "LLM · 专家团队审阅"
    assert "bailian" in scene["providers"]
    assert set(scene["providers"]) <= {"openai", "ark", "doubao", "openai-compatible", "bailian"}


def test_agency_expert_review_scene_supports_bailian_provider(client):
    resp = client.get("/api/ai-models/schema")
    data = resp.json()

    scene = next(item for item in data["scenes"] if item["key"] == "llm_agency_expert_review")
    bailian = data["providers"]["bailian"]

    assert "bailian" in scene["providers"]
    assert bailian["default_base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert bailian["protocol"] == "openai_chat_completions"
    assert bailian["test_strategy"] == "list_models"


def test_scene_key_unknown_raises(client):
    from app.data.model_schema_data import scene_key_to_model_type
    with pytest.raises(ValueError, match="Unknown scene key"):
        scene_key_to_model_type("nonexistent")


def test_provider_preset_fallback(client):
    from app.services.model_schema import get_provider_preset
    preset = get_provider_preset("unknown_provider_xyz")
    assert preset["label"] == "unknown_provider_xyz"
    assert preset["test_strategy"] == "health_check"


def test_seedance_provider_uses_ark_plan_v3_endpoint(client):
    resp = client.get("/api/ai-models/schema")
    data = resp.json()

    seedance = data["providers"]["seedance"]
    assert seedance["default_base_url"] == "https://ark.cn-beijing.volces.com/api/plan/v3"
    assert "/api/v3" not in seedance["default_base_url"]
    assert seedance["protocol"] == "ark_plan_v3"
    assert seedance["test_strategy"] == "noop"


def test_video_rendering_scene_supports_bailian_wan_provider(client):
    resp = client.get("/api/ai-models/schema")
    data = resp.json()

    scene = next(item for item in data["scenes"] if item["key"] == "video_rendering")
    wan = data["providers"]["wan"]

    assert "wan" in scene["providers"]
    assert wan["default_base_url"] == "https://dashscope.aliyuncs.com/api/v1"
    assert wan["protocol"] == "dashscope_async"
    assert wan["test_strategy"] == "list_models"


def test_image_generation_scene_supports_bailian_qwen_image_provider(client):
    resp = client.get("/api/ai-models/schema")
    data = resp.json()

    image_scene = next(item for item in data["scenes"] if item["key"] == "image_generation")
    edit_scene = next(item for item in data["scenes"] if item["key"] == "image_editing")
    qwen_image = data["providers"]["qwen-image"]

    assert "qwen-image" in image_scene["providers"]
    assert "qwen-image" in edit_scene["providers"]
    assert qwen_image["default_base_url"] == "https://dashscope.aliyuncs.com/api/v1"
    assert qwen_image["protocol"] == "dashscope_multimodal_generation"
    assert qwen_image["test_strategy"] == "list_models"

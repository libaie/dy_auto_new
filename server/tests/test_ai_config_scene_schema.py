"""Tests for scene_key filter, blank secret preservation, connection test enhancements."""
import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db_models import AIModel
from app.services.crypto import encrypt, decrypt


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _seed_one(db, **kw):
    m = AIModel(
        id=kw.pop("id", str(uuid.uuid4())),
        name=kw.pop("name", "Test Model"),
        model_type=kw.pop("model_type", "llm"),
        provider=kw.pop("provider", "openai"),
        api_key=encrypt(kw.pop("api_key", "sk-test")),
        api_secret=encrypt(kw.pop("api_secret", "")),
        model_name=kw.pop("model_name", "test-model"),
        config_json=kw.pop("config_json", {}),
        enabled=kw.pop("enabled", True),
        sort_order=kw.pop("sort_order", 0),
        **kw,
    )
    db.add(m); db.commit(); db.refresh(m)
    return m


# ======== scene_key filter ========

def test_list_models_filtered_by_scene_key(client, db):
    _seed_one(db, name="VideoModel", model_type="video", provider="seedance",
              model_name="sd-video")
    _seed_one(db, name="LLMModel", model_type="llm", provider="openai",
              model_name="gpt-4")

    resp = client.get("/api/ai-models?scene_key=video_rendering")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["models"]) == 1
    assert data["models"][0]["model_type"] == "video"


def test_list_models_unknown_scene_key_returns_empty(client, db):
    _seed_one(db, name="Test", model_type="llm")
    resp = client.get("/api/ai-models?scene_key=nonexistent_scene")
    assert resp.status_code == 200
    data = resp.json()
    assert data["models"] == []


def test_options_filtered_by_scene_key(client, db):
    _seed_one(db, name="VideoModel", model_type="video", provider="seedance",
              model_name="sd-video", enabled=True)
    _seed_one(db, name="DisabledLLM", model_type="llm", provider="openai",
              model_name="gpt-4", enabled=False)

    resp = client.get("/api/ai-models/options?scene_key=video_rendering")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["options"]) == 1
    assert data["options"][0]["provider"] == "seedance"


# ======== blank secret preservation ========

def test_update_preserves_blank_secret(client, db):
    m = _seed_one(db, name="PreserveTest", api_key="original-key",
                  api_secret="original-secret")
    resp = client.put(f"/api/ai-models/{m.id}", json={
        "name": "PreserveTest-renamed",
        "api_key": "",
        "api_secret": "",
    })
    assert resp.status_code == 200
    db.refresh(m)
    assert decrypt(m.api_key) == "original-key", "api_key wiped by empty string"
    assert decrypt(m.api_secret) == "original-secret", "api_secret wiped by empty string"


def test_update_clear_secret_explicitly(client, db):
    m = _seed_one(db, name="ClearTest", api_key="to-be-cleared")
    resp = client.put(f"/api/ai-models/{m.id}", json={
        "api_key": "",
        "clear_secret": True,
    })
    assert resp.status_code == 200
    db.refresh(m)
    assert m.api_key is None, "api_key should be cleared when clear_secret is True"


def test_update_model_can_change_model_type_for_scene_rebinding(client, db):
    m = _seed_one(
        db,
        name="Image Model To Rebind",
        model_type="image",
        provider="seedance",
        model_name="doubao-seedream-5.0-lite",
        config_json={"scene_key": "image_generation"},
    )

    resp = client.put(f"/api/ai-models/{m.id}", json={
        "model_type": "llm",
        "provider": "openai-compatible",
        "base_url": "https://llm.test/v1",
        "model_name": "expert-review-model",
        "config_json": {
            "scene_key": "llm_agency_expert_review",
            "protocol": "openai_chat_completions",
        },
    })

    assert resp.status_code == 200
    db.refresh(m)
    assert m.model_type == "llm"
    assert m.provider == "openai-compatible"
    assert m.config_json["scene_key"] == "llm_agency_expert_review"


# ======== connection test ========

def test_connection_test_rejects_private_ip(client, db):
    m = _seed_one(db, name="SSRFTest", model_type="llm", provider="openai",
                  base_url="http://10.0.0.1/v1", api_key="sk-test")
    resp = client.post(f"/api/ai-models/{m.id}/test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert "内网" in data["error"]


def test_connection_test_allows_public_hostname(client, db, monkeypatch):
    calls = []

    class Response:
        is_success = True
        status_code = 200
        text = ""

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr("app.routers.ai_config.httpx.get", fake_get)
    m = _seed_one(
        db,
        name="PublicHostTest",
        model_type="llm",
        provider="openai",
        base_url="https://api.openai.com/v1",
        api_key="sk-test",
    )

    resp = client.post(f"/api/ai-models/{m.id}/test")

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert calls[0][0] == "https://api.openai.com/v1/models"


def test_connection_test_noop_strategy(client, db):
    m = _seed_one(db, name="NoopTest", model_type="video", provider="kling",
                  base_url="https://api.kling.com", api_key="sk-test")
    resp = client.post(f"/api/ai-models/{m.id}/test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert "不支持" in data["error"]
def test_default_seedance_models_use_ark_plan_v3():
    from app.routers.ai_config import DEFAULT_MODELS

    seedance_models = [m for m in DEFAULT_MODELS if m["provider"] == "seedance"]
    by_type = {m["model_type"]: m for m in seedance_models}

    assert seedance_models
    for model in seedance_models:
        assert model["base_url"] == "https://ark.cn-beijing.volces.com/api/plan/v3"
        assert "/api/v3" not in model["base_url"]
    assert by_type["image"]["model_name"] == "doubao-seedream-5.0-lite"
    assert by_type["image"]["config_json"]["default_size"] == "3K"
    assert by_type["video"]["model_name"] == "doubao-seedance-2.0"
    assert by_type["video"]["config_json"]["max_duration_seconds"] == 15


def test_default_wan_model_uses_bailian_video_task_endpoint():
    from app.routers.ai_config import DEFAULT_MODELS

    wan = next(m for m in DEFAULT_MODELS if m["name"] == "Wan 2.7")

    assert wan["model_type"] == "video"
    assert wan["provider"] == "wan"
    assert wan["base_url"] == "https://dashscope.aliyuncs.com/api/v1"
    assert wan["model_name"] == "wan2.7-i2v"
    assert wan["config_json"]["scene_key"] == "video_rendering"
    assert wan["config_json"]["provider_options_schema"]["resolution"]["options"] == ["720P", "1080P"]
    assert wan["config_json"]["capabilities"]["first_frame"] is True
    assert wan["config_json"]["capabilities"]["last_frame"] is True
    assert wan["config_json"]["max_duration_seconds"] == 15
    assert wan["config_json"]["estimated_cost"] > 0
    assert wan["config_json"]["real_paid_allowed"] is True
    assert wan["config_json"]["returns_asset_url"] is True


def test_default_qwen_image_model_uses_bailian_multimodal_generation_endpoint():
    from app.routers.ai_config import DEFAULT_MODELS

    qwen_image = next(m for m in DEFAULT_MODELS if m["name"] == "Qwen Image 2.0 Pro")

    assert qwen_image["model_type"] == "image"
    assert qwen_image["provider"] == "qwen-image"
    assert qwen_image["base_url"] == "https://dashscope.aliyuncs.com/api/v1"
    assert qwen_image["model_name"] == "qwen-image-2.0-pro"
    assert qwen_image["config_json"]["scene_keys"] == ["image_generation", "image_editing"]
    assert qwen_image["config_json"]["task_path"] == "/services/aigc/multimodal-generation/generation"
    assert qwen_image["config_json"]["capabilities"]["text_to_image"] is True
    assert qwen_image["config_json"]["estimated_cost"] > 0
    assert qwen_image["config_json"]["real_paid_allowed"] is True
    assert qwen_image["config_json"]["returns_asset_url"] is True
    assert qwen_image["config_json"]["provider_options_schema"]["size"]["options"] == [
        "1024*1024",
        "1536*2688",
        "2688*1536",
    ]


def test_default_bailian_expert_review_model_uses_chat_completions_endpoint():
    from app.routers.ai_config import DEFAULT_MODELS

    expert = next(m for m in DEFAULT_MODELS if m["name"] == "Bailian Qwen Expert Review")

    assert expert["model_type"] == "llm"
    assert expert["provider"] == "bailian"
    assert expert["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert expert["model_name"] == "qwen-plus"
    assert expert["config_json"]["scene_key"] == "llm_agency_expert_review"
    assert expert["config_json"]["protocol"] == "openai_chat_completions"
    assert expert["config_json"]["max_tokens"] == 8192
    assert expert["config_json"]["temperature"] == 0.2


def test_seed_ai_models_upgrades_unconfigured_legacy_expert_review_default(db):
    from app.db_models import AIModel
    from app.routers.ai_config import seed_ai_models

    legacy = AIModel(
        name="OpenAI Compatible Expert Review",
        model_type="llm",
        provider="openai-compatible",
        base_url="https://api.openai.com/v1",
        api_key=None,
        model_name="gpt-4o",
        enabled=True,
        config_json={
            "scene_key": "llm_agency_expert_review",
            "protocol": "openai_chat_completions",
            "max_tokens": 2048,
            "temperature": 0.2,
        },
    )
    db.add(legacy)
    db.commit()

    seed_ai_models(db)
    db.refresh(legacy)

    assert legacy.name == "Bailian Qwen Expert Review"
    assert legacy.provider == "bailian"
    assert legacy.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert legacy.model_name == "qwen-plus"
    assert legacy.config_json["scene_key"] == "llm_agency_expert_review"
    assert legacy.config_json["max_tokens"] == 8192


def test_seed_ai_models_updates_existing_legacy_seedance_base_url(db):
    from app.routers.ai_config import seed_ai_models

    legacy_base_url = "https://ark.cn-beijing.volces.com" + "/api/v3"
    model = _seed_one(
        db,
        name="Seedance 2.0",
        model_type="video",
        provider="seedance",
        base_url=legacy_base_url,
        model_name="doubao-seedance-2.0-260128",
        config_json={"default_duration": 5},
    )

    seed_ai_models(db)
    db.refresh(model)

    assert model.base_url == "https://ark.cn-beijing.volces.com/api/plan/v3"
    assert model.model_name == "doubao-seedance-2.0"
    assert model.config_json["scene_key"] == "video_rendering"


def test_seed_ai_models_updates_existing_legacy_seedance_image_model(db):
    from app.routers.ai_config import seed_ai_models

    model = _seed_one(
        db,
        name="Seedance Image",
        model_type="image",
        provider="seedance",
        base_url="https://ark.cn-beijing.volces.com/api/plan/v3",
        model_name="seedance-image",
        config_json={},
    )

    seed_ai_models(db)
    db.refresh(model)

    assert model.name == "Seedream 5.0 Lite"
    assert model.model_name == "doubao-seedream-5.0-lite"
    assert model.config_json["scene_key"] == "image_generation"

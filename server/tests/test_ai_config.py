"""AI model config CRUD API tests."""
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
    import uuid
    m = AIModel(
        id=kw.pop("id", str(uuid.uuid4())),
        name=kw.pop("name", "Test Model"),
        model_type=kw.pop("model_type", "llm"),
        provider=kw.pop("provider", "deepseek"),
        base_url=kw.pop("base_url", "https://api.test.com/v1"),
        api_key=encrypt(kw.pop("api_key", "sk-test-key")),
        api_secret=encrypt(kw.pop("api_secret", "")),
        model_name=kw.pop("model_name", "test-model"),
        config_json=kw.pop("config_json", {"max_tokens": 4096, "temperature": 0.7}),
        enabled=kw.pop("enabled", True),
        sort_order=kw.pop("sort_order", 0),
        **kw,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


# ======== LIST ========


def test_list_models(client, db):
    _seed_one(db, name="Model A", model_type="llm", provider="openai", model_name="gpt-4")
    _seed_one(db, name="Model B", model_type="image", provider="seedance", model_name="sd-img")

    resp = client.get("/api/ai-models")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert len(data["models"]) >= 2
    for m in data["models"]:
        assert "id" in m
        assert "name" in m
        assert "model_type" in m
        assert "api_key_configured" in m
        assert m["api_key"] == "****" or m["api_key"] == ""


def test_list_models_filter_by_type(client, db):
    _seed_one(db, name="LLM-1", model_type="llm", provider="openai", model_name="gpt-4")
    _seed_one(db, name="IMG-1", model_type="image", provider="seedance", model_name="sd-img")

    resp = client.get("/api/ai-models?model_type=llm")
    assert resp.status_code == 200
    models = resp.json()["models"]
    assert all(m["model_type"] == "llm" for m in models)
    assert len(models) >= 1


def test_list_models_filter_by_enabled(client, db):
    _seed_one(db, name="Enabled", enabled=True, provider="openai", model_name="en-mod")
    _seed_one(db, name="Disabled", enabled=False, provider="openai", model_name="dis-mod")

    resp = client.get("/api/ai-models?enabled=true")
    assert resp.status_code == 200
    models = resp.json()["models"]
    assert all(m["enabled"] for m in models)


# ======== GET / OPTIONS ========


def test_get_options(client, db):
    _seed_one(db, name="Opt A", model_type="llm", provider="deepseek", model_name="opt-a")
    _seed_one(db, name="Opt B", model_type="llm", provider="openai", model_name="opt-b")
    _seed_one(db, name="Opt C", model_type="image", provider="seedance", model_name="opt-c", enabled=False)

    resp = client.get("/api/ai-models/options?model_type=llm")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    options = data["options"]
    assert len(options) >= 2
    for opt in options:
        assert "id" in opt
        assert "name" in opt
        assert "model_type" in opt
        assert "provider" in opt
        assert opt["model_type"] == "llm"


def test_get_model_detail(client, db):
    m = _seed_one(db, name="Detail Test", api_key="raw-key-123")

    resp = client.get(f"/api/ai-models/{m.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    model = data["model"]
    assert model["name"] == "Detail Test"
    assert model["api_key"] == "raw-key-123"


def test_get_model_not_found(client):
    resp = client.get("/api/ai-models/nonexistent-id")
    assert resp.status_code == 404


# ======== CREATE ========


def test_create_model(client, db):
    resp = client.post("/api/ai-models", json={
        "name": "New Model",
        "model_type": "llm",
        "provider": "deepseek",
        "base_url": "https://api.ds.com/v1",
        "api_key": "sk-new-key",
        "model_name": "deepseek-v4",
        "config_json": {"thinking_enabled": True, "max_tokens": 8192},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["model"]["name"] == "New Model"
    assert data["model"]["api_key"] == "sk-new-key"
    assert data["model"]["api_key_configured"] is True


def test_create_model_duplicate(client, db):
    _seed_one(db, name="Dup", model_type="llm", provider="deepseek", model_name="dup-model")

    resp = client.post("/api/ai-models", json={
        "name": "Dup 2",
        "model_type": "llm",
        "provider": "deepseek",
        "model_name": "dup-model",
    })
    assert resp.status_code == 409


def test_create_model_minimal(client):
    """Create with only required fields."""
    resp = client.post("/api/ai-models", json={
        "name": "Minimal",
        "model_type": "tts",
        "provider": "edge-tts",
    })
    assert resp.status_code == 200
    assert resp.json()["model"]["name"] == "Minimal"


# ======== UPDATE ========


def test_update_model(client, db):
    m = _seed_one(db, name="Before", provider="openai", model_name="before-mod")

    resp = client.put(f"/api/ai-models/{m.id}", json={
        "name": "After",
        "enabled": False,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["model"]["name"] == "After"
    assert data["model"]["enabled"] is False
    assert data["model"]["provider"] == "openai"


def test_update_model_not_found(client):
    resp = client.put("/api/ai-models/nonexistent-id", json={"name": "X"})
    assert resp.status_code == 404


# ======== DELETE ========


def test_delete_model(client, db):
    m = _seed_one(db, name="To Delete", provider="openai", model_name="del-mod")

    resp = client.delete(f"/api/ai-models/{m.id}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    resp2 = client.get(f"/api/ai-models/{m.id}")
    assert resp2.status_code == 404


def test_delete_model_not_found(client):
    resp = client.delete("/api/ai-models/nonexistent-id")
    assert resp.status_code == 404

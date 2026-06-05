"""Model registry resolution tests."""
import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db_models import AIModel
from app.services.crypto import encrypt
from app.services.model_registry import get_model_for_scene, ModelResolutionError


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _seed(db, **kw):
    m = AIModel(
        id=kw.pop("id", str(uuid.uuid4())),
        name=kw.pop("name", "Test Model"),
        model_type=kw.pop("model_type", "llm"),
        provider=kw.pop("provider", "openai"),
        api_key=encrypt(kw.pop("api_key", "sk-test")),
        api_secret=encrypt(kw.pop("api_secret", "")),
        model_name=kw.pop("model_name", "test-model"),
        enabled=kw.pop("enabled", True),
        sort_order=kw.pop("sort_order", 0),
        **kw,
    )
    db.add(m); db.commit(); db.refresh(m)
    return m


def test_registry_explicit_model_returns_decrypted(client, db):
    m = _seed(db, name="GPT-4o", model_type="llm")
    result = get_model_for_scene(db, "script_generation", explicit_model_id=m.id)
    assert result["id"] == m.id
    assert result["api_key"] == "sk-test"
    assert result["resolution_source"] == "explicit"


def test_registry_fallback_returns_default_enabled(client, db):
    _seed(db, name="GPT-4o", model_type="llm", sort_order=0, model_name="gpt-4o")
    _seed(db, name="Claude", model_type="llm", sort_order=1, model_name="claude-opus")
    result = get_model_for_scene(db, "script_generation")
    assert result["name"] == "GPT-4o"
    assert result["resolution_source"] == "default"


def test_registry_missing_model_raises(client, db):
    with pytest.raises(ModelResolutionError) as exc:
        get_model_for_scene(db, "script_generation")
    assert exc.value.status_code == 400


def test_registry_disabled_model_raises(client, db):
    m = _seed(db, name="GPT-4o", model_type="llm", enabled=False, model_name="gpt-4o-disabled")
    with pytest.raises(ModelResolutionError) as exc:
        get_model_for_scene(db, "script_generation", explicit_model_id=m.id)
    assert "禁用" in exc.value.repair_action


def test_registry_wrong_type_raises(client, db):
    m = _seed(db, name="Seedance", model_type="video", provider="seedance", model_name="sd-video")
    with pytest.raises(ModelResolutionError) as exc:
        get_model_for_scene(db, "script_generation", explicit_model_id=m.id)
    assert exc.value.status_code == 400


def test_registry_decrypts_secrets_for_runtime(client, db):
    m = _seed(db, name="Secure", model_type="llm", api_key="secret-123")
    result = get_model_for_scene(db, "script_generation", explicit_model_id=m.id)
    assert result["api_key"] == "secret-123"


def test_registry_nonexistent_explicit_id_raises(client, db):
    with pytest.raises(ModelResolutionError) as exc:
        get_model_for_scene(db, "script_generation", explicit_model_id="nonexistent-id")
    assert "不存在" in exc.value.repair_action


def test_registry_returns_config_json_key(client, db):
    """Regression: registry must return 'config_json' (not 'config')."""
    m = _seed(db, name="ConfigTest", model_type="llm",
              config_json={"temperature": 0.5, "max_tokens": 2048})
    result = get_model_for_scene(db, "script_generation", explicit_model_id=m.id)
    assert "config_json" in result, "Registry must return 'config_json' key"
    assert result["config_json"] == {"temperature": 0.5, "max_tokens": 2048}
    assert result["resolution_source"] == "explicit"

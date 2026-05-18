"""AI config resolution tests — dual llm_* / ai_* key compatibility."""
import pytest
from app.db_models import SystemSetting
from app.database import get_db
from app.main import app


@pytest.fixture
def db():
    gen = app.dependency_overrides[get_db]()
    session = next(gen)
    yield session
    session.rollback()
    gen.close()


def _clean_settings(db):
    db.query(SystemSetting).delete()
    db.commit()


def _set_setting(db, key, value):
    s = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if s:
        s.value = value
    else:
        db.add(SystemSetting(key=key, value=value))
    db.commit()


def test_llm_key_takes_priority(db):
    """When both llm_* and ai_* keys exist, llm_* wins."""
    _clean_settings(db)
    _set_setting(db, "llm_api_key", "sk-new-key")
    _set_setting(db, "ai_api_key", "sk-old-key")
    _set_setting(db, "llm_base_url", "https://llm.example.com")
    _set_setting(db, "ai_base_url", "https://ai.example.com")
    _set_setting(db, "llm_model", "llm-model-v2")
    _set_setting(db, "ai_model", "ai-model-v1")

    from app.config import get_ai_config_with_key
    cfg = get_ai_config_with_key(db)

    assert cfg is not None
    assert cfg["api_key"] == "sk-new-key"
    assert "llm.example.com" in cfg["api_url"]
    assert cfg["model"] == "llm-model-v2"


def test_ai_key_fallback(db):
    """When only ai_* keys exist, fall back to them."""
    _clean_settings(db)
    _set_setting(db, "ai_api_key", "sk-legacy-key")
    _set_setting(db, "ai_base_url", "https://legacy.example.com")
    _set_setting(db, "ai_model", "legacy-model")

    from app.config import get_ai_config_with_key
    cfg = get_ai_config_with_key(db)

    assert cfg is not None
    assert cfg["api_key"] == "sk-legacy-key"
    assert "legacy.example.com" in cfg["api_url"]
    assert cfg["model"] == "legacy-model"


def test_env_var_fallback_when_db_empty(db, monkeypatch):
    """When DB has no ai_* or llm_* keys, fall back to environment variables."""
    _clean_settings(db)
    monkeypatch.setenv("AI_API_KEY", "sk-env-key")

    from app.config import get_ai_config_with_key
    cfg = get_ai_config_with_key(db)

    assert cfg is not None
    assert cfg["api_key"] == "sk-env-key"


def test_llm_thinking_key_priority(db):
    """llm_thinking should take priority over ai_thinking."""
    _clean_settings(db)
    _set_setting(db, "llm_thinking", "low")
    _set_setting(db, "ai_thinking", "xhigh")

    from app.config import _resolve_ai_config
    cfg = _resolve_ai_config(db)

    assert cfg["thinking_level"] == "low"
    assert cfg["thinking_budget"] == 2048


def test_empty_api_key_returns_none(db):
    """When no API key is configured anywhere, get_ai_config returns None."""
    _clean_settings(db)
    import os
    old_val = os.environ.pop("AI_API_KEY", None)
    try:
        from app.config import get_ai_config
        cfg = get_ai_config(db)
        assert cfg is None
    finally:
        if old_val:
            os.environ["AI_API_KEY"] = old_val

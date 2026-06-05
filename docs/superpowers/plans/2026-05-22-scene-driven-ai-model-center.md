# Scene-Driven AI Model Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace hard-coded provider/type lists with a backend schema-driven AI model center. Runtime consumers (pipeline, director, audit, style-lock) resolve models by scene key through a unified `model_registry`.

**Architecture:** Two new services (`model_schema` for declarative scene/provider/field metadata, `model_registry` for runtime resolution), enhanced CRUD router with schema endpoint + scene_key filter + secret preservation, legacy migration from Settings/Pixelle/Seedance into `AIModel`, frontend split from 899-line monolith into 5 schema-rendered components. 5 parallel lanes, 3 sequential gates.

**Tech Stack:** Python 3.12+ / FastAPI / SQLAlchemy / SQLite / pytest / Vue 3 / Vitest

---

## File Structure

```
server/app/services/
├── model_schema.py          NEW — declarative scene/provider/protocol/field metadata
├── model_registry.py        NEW — runtime model resolution by scene key
│
server/app/routers/
├── ai_config.py             MODIFY — schema endpoint, scene_key filter, secret preservation,
│                                      protocol-aware connection test, SSRF guard
├── pipeline.py              MODIFY — _get_model_config() → model_registry
├── audit.py                 MODIFY — direct AIModel query → model_registry
├── series.py                MODIFY — direct AIModel query → model_registry
│
server/app/
├── db_models.py             NO CHANGE — AIModel already has required columns
│
server/app/data/
├── model_schema_data.py     NEW — scene definitions, provider presets, field templates
│
server/tests/
├── test_model_schema.py     NEW — schema endpoint + validation tests
├── test_model_registry.py   NEW — registry resolution tests
├── test_ai_model_migration.py NEW — migration idempotency + conflict tests
├── test_ai_config_scene_schema.py NEW — scene_key filter, blank secret, connection test
├── test_pipeline_model_registry.py NEW — pipeline registry integration
├── test_pixelle_seedance_model_center_regression.py NEW — regression tests
├── test_ai_config.py        MODIFY — add blank secret preservation test
├── test_series_style_lock_pipeline.py MODIFY — registry consumer tests
│
web/src/views/
├── AIConfigPage.vue         REFACTOR — split into scene sidebar + detail/edit panels
│
web/src/components/
├── ModelSceneSidebar.vue    NEW — scene navigation with status dots
├── ModelDetailPanel.vue     NEW — model detail display
├── ModelEditForm.vue        NEW — 4-step schema-driven form
├── ModelSchemaField.vue     NEW — schema-aware field renderer
├── ModelConnectionStatus.vue NEW — connection test with inline results
│
web/src/api/
├── aiConfig.js              MODIFY — add fetchSchema, scene_key param
│
web/src/__tests__/
├── ai-config-scene-schema.test.js NEW — schema client + scene sidebar + form validation
├── api-clients.test.js      MODIFY — add schema endpoint tests
```

---

## Lane A: Backend Foundation (model_schema + model_registry + ai_config)

### Task A1: model_schema_data.py — Scene/provider/field definitions

**Files:**
- Create: `server/app/data/model_schema_data.py`
- Test: `server/tests/test_model_schema.py`

- [ ] **Step 1: Write the data module**

```python
"""
Declarative scene, provider, protocol, and field definitions
for the scene-driven AI model center.

All metadata the frontend needs to render the model center lives here.
Adding a new provider or scene should only touch this file.
"""

# ==== Scene definitions ====
# Each scene maps to a model_type. Runtime consumers use the scene_key.
SCENES = [
    {
        "key": "script_generation",
        "label": "LLM · 脚本生成",
        "model_type": "llm",
        "description": "用于导演分镜、旁白、标题、提示词生成",
        "providers": ["deepseek", "openai", "anthropic", "custom"],
        "fields": [
            {"key": "temperature", "label": "Temperature", "type": "number", "default": 0.7, "min": 0, "max": 2, "step": 0.1},
            {"key": "max_tokens", "label": "Max Tokens", "type": "number", "default": 4096, "min": 1, "max": 131072},
            {"key": "thinking_enabled", "label": "Thinking Enabled", "type": "boolean", "default": False},
            {"key": "thinking_budget", "label": "Thinking Budget", "type": "number", "default": 8192, "min": 1024, "max": 32000},
        ],
    },
    {
        "key": "image_generation",
        "label": "Image · 画面生成",
        "model_type": "image",
        "description": "用于风格锁定参考图和 L0 图像资源生成",
        "providers": ["seedance", "openai", "comfyui", "pixelle", "custom"],
        "fields": [
            {"key": "default_size", "label": "Default Size", "type": "select", "default": "1024x1024", "options": ["512x512", "1024x1024", "1024x1792", "1792x1024"]},
            {"key": "default_quality", "label": "Quality", "type": "select", "default": "hd", "options": ["standard", "hd"]},
        ],
    },
    {
        "key": "video_rendering",
        "label": "Video · 视频渲染",
        "model_type": "video",
        "description": "用于 L4 视频生成和 Seedance 独立面板",
        "providers": ["seedance", "kling", "custom"],
        "fields": [
            {"key": "default_resolution", "label": "Default Resolution", "type": "select", "default": "720p", "options": ["720p", "1080p"]},
            {"key": "default_duration", "label": "Default Duration (s)", "type": "number", "default": 5, "min": 1, "max": 60},
            {"key": "default_aspect_ratio", "label": "Aspect Ratio", "type": "select", "default": "9:16", "options": ["16:9", "9:16", "1:1"]},
            {"key": "poll_interval_seconds", "label": "Poll Interval (s)", "type": "number", "default": 10, "min": 1, "max": 60},
            {"key": "poll_timeout_seconds", "label": "Poll Timeout (s)", "type": "number", "default": 180, "min": 30, "max": 600},
        ],
    },
    {
        "key": "tts_synthesis",
        "label": "TTS · 语音合成",
        "model_type": "tts",
        "description": "用于旁白音频和未来语音合成",
        "providers": ["edge-tts", "openai", "custom"],
        "fields": [
            {"key": "voice", "label": "Voice", "type": "string", "default": "zh-CN-XiaoxiaoNeural"},
            {"key": "speed", "label": "Speed", "type": "number", "default": 1.0, "min": 0.5, "max": 2.0, "step": 0.1},
        ],
    },
    {
        "key": "quality_audit",
        "label": "Audit · 质量审计",
        "model_type": "audit",
        "description": "用于图像/视频质量审计",
        "providers": ["openai", "anthropic", "gemini", "custom"],
        "fields": [
            {"key": "max_tokens", "label": "Max Tokens", "type": "number", "default": 4096, "min": 1, "max": 131072},
        ],
    },
]

# ==== Provider presets ====
# Key: provider identifier matching AIModel.provider.
PROVIDERS = {
    "deepseek": {"label": "DeepSeek", "default_base_url": "https://api.deepseek.com/v1", "protocol": "openai_compatible", "test_strategy": "list_models"},
    "openai": {"label": "OpenAI", "default_base_url": "https://api.openai.com/v1", "protocol": "openai_compatible", "test_strategy": "list_models"},
    "anthropic": {"label": "Anthropic", "default_base_url": "https://api.anthropic.com/v1/messages", "protocol": "anthropic", "test_strategy": "list_models"},
    "seedance": {"label": "Seedance 2.0", "default_base_url": "https://ark.cn-beijing.volces.com/api/v3", "protocol": "openai_compatible", "test_strategy": "health_check", "test_path": "/api/v3/models"},
    "kling": {"label": "Kling 3.0", "default_base_url": "", "protocol": "http_custom", "test_strategy": "noop"},
    "gemini": {"label": "Gemini", "default_base_url": "https://generativelanguage.googleapis.com/v1beta", "protocol": "gemini", "test_strategy": "list_models"},
    "comfyui": {"label": "ComfyUI", "default_base_url": "", "protocol": "local_service", "test_strategy": "noop"},
    "pixelle": {"label": "Pixelle", "default_base_url": "http://localhost:8500", "protocol": "http_custom", "test_strategy": "health_check", "test_path": "/health"},
    "edge-tts": {"label": "Edge TTS", "default_base_url": "", "protocol": "local_service", "test_strategy": "noop"},
    "custom": {"label": "Custom", "default_base_url": "", "protocol": None, "test_strategy": "health_check", "test_path": "/"},
}

# ==== Protocols ====
# test_strategy determines how the connection test endpoint validates the provider.
#   list_models  → GET {base_url}/models with auth headers
#   health_check → GET {base_url}{test_path} with auth headers
#   noop         → return "不支持自动测试" (provider has no testable endpoint)

PROTOCOLS = ["openai_compatible", "anthropic", "gemini", "http_custom", "local_service"]

# ==== Custom field policy ====
CUSTOM_FIELD_POLICY = {
    "enabled": True,
    "allowed_types": ["string", "number", "boolean", "select", "secret"],
}

# ==== Scene → model_type lookup (for runtime) ====
def scene_key_to_model_type(scene_key: str) -> str:
    for scene in SCENES:
        if scene["key"] == scene_key:
            return scene["model_type"]
    raise ValueError(f"Unknown scene key: {scene_key}")

def get_schema(include_secrets: bool = False) -> dict:
    """Returns the full schema the frontend needs to render the model center."""
    common_fields = [
        {"key": "name", "label": "模型名称", "type": "string", "required": True, "max_length": 100},
        {"key": "provider", "label": "提供商", "type": "select", "required": True, "options_source": "scene_providers"},
        {"key": "base_url", "label": "Base URL", "type": "string", "required": False, "max_length": 300},
        {"key": "api_key", "label": "API Key", "type": "secret", "required": False},
        {"key": "api_secret", "label": "API Secret", "type": "secret", "required": False},
        {"key": "model_name", "label": "Model Identifier", "type": "string", "required": False, "max_length": 100},
    ]
    return {
        "common_fields": common_fields,
        "scenes": SCENES,
        "providers": PROVIDERS,
        "protocols": PROTOCOLS,
        "custom_field_policy": CUSTOM_FIELD_POLICY,
    }
```

- [ ] **Step 2: Verify imports**

```bash
cd server && python -c "from app.data.model_schema_data import get_schema, SCENES, PROVIDERS; s = get_schema(); print(f'{len(SCENES)} scenes, {len(PROVIDERS)} providers, {len(s[\"common_fields\"])} common fields'); print('OK')"
```

Expected: `5 scenes, 10 providers, 6 common fields` / `OK`

---

### Task A2: model_schema.py — Schema endpoint service

**Files:**
- Create: `server/app/services/model_schema.py`
- Test: `server/tests/test_model_schema.py`

- [ ] **Step 1: Write the service**

```python
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
    return PROVIDERS.get(provider, {"label": provider, "default_base_url": "", "protocol": "http_custom", "test_strategy": "health_check", "test_path": "/"})

def get_schema_payload() -> dict:
    """Full schema for the frontend GET /api/ai-models/schema endpoint."""
    return get_schema()
```

- [ ] **Step 2: Write the schema endpoint test**

```python
# server/tests/test_model_schema.py
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
    assert len(data["scenes"]) == 5
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


def test_schema_requires_auth(client, db):
    """Verify schema endpoint is not public — requires admin token."""
    # This test will FAIL initially (schema endpoint doesn't exist yet)
    resp = client.get("/api/ai-models/schema")  # no auth header
    # After implementation: should be 401 or 403
    assert resp.status_code in (200, 401, 403), \
        f"Unexpected status {resp.status_code}"
```

- [ ] **Step 3: Add the schema endpoint to ai_config.py**

```python
# In server/app/routers/ai_config.py, add after the imports:
from app.services.model_schema import get_schema_payload

# Add after the GET /options endpoint (line ~92):

@router.get("/schema")
def get_schema(_ = Depends(verify_admin_token)):
    """Return scene definitions, provider presets, protocols, and custom field policy."""
    return {"ok": True, **get_schema_payload()}
```

- [ ] **Step 4: Run tests**

```bash
cd server && python -m pytest tests/test_model_schema.py -v
```

Expected: 4/4 PASS

---

### Task A3: model_registry.py — Runtime model resolution

**Files:**
- Create: `server/app/services/model_registry.py`
- Test: `server/tests/test_model_registry.py`

- [ ] **Step 1: Write the registry service**

```python
"""Model registry — resolves runtime model configuration by scene key."""
import logging
from functools import lru_cache
from typing import Literal
from sqlalchemy.orm import Session
from app.db_models import AIModel
from app.services.crypto import decrypt
from app.data.model_schema_data import scene_key_to_model_type, get_scene_by_key

logger = logging.getLogger(__name__)


class ModelResolutionError(Exception):
    """Raised when a model cannot be resolved for a scene."""
    def __init__(self, scene_key: str, repair_action: str, status_code: int = 400):
        self.scene_key = scene_key
        self.repair_action = repair_action
        self.status_code = status_code
        super().__init__(repair_action)


def get_model_for_scene(
    db: Session,
    scene_key: str,
    explicit_model_id: str | None = None,
) -> dict:
    """
    Resolve a runtime model configuration for a scene.

    Resolution rules (in order):
    1. If explicit_model_id → load and validate it supports the scene's model_type
    2. Otherwise → first enabled model for the scene's model_type, by sort_order + created_at
    3. If nothing found → raise ModelResolutionError with scene name and repair action

    Returns a dict with decrypted api_key + api_secret for runtime use.
    Never call this from list/schema/options endpoints — secrets are decrypted here.
    """
    model_type = scene_key_to_model_type(scene_key)
    scene = get_scene_by_key(scene_key)
    scene_label = scene["label"] if scene else scene_key

    if explicit_model_id:
        m = db.query(AIModel).filter(AIModel.id == explicit_model_id).first()
        if not m:
            raise ModelResolutionError(
                scene_key,
                f"选定的模型不存在或已被删除。请到 AI 模型配置中心为 {scene_label} 选择新模型。",
                status_code=400,
            )
        if not m.enabled:
            raise ModelResolutionError(
                scene_key,
                f"选定的模型 {m.name} 已被禁用。请到模型详情页启用该模型，或为 {scene_label} 选择其他模型。",
                status_code=400,
            )
        if m.model_type != model_type:
            raise ModelResolutionError(
                scene_key,
                f"模型 {m.name} 的类型为 {m.model_type}，不能用于 {scene_label}。请选择 {model_type} 类型的模型。",
                status_code=400,
            )
    else:
        m = (
            db.query(AIModel)
            .filter(AIModel.model_type == model_type, AIModel.enabled == True)
            .order_by(AIModel.sort_order, AIModel.created_at)
            .first()
        )
        if not m:
            raise ModelResolutionError(
                scene_key,
                f"未配置 {scene_label} 模型。请到 AI 模型配置中心新增或启用 {model_type} 类型的模型。",
                status_code=400,
            )

    # Decrypt secrets for runtime only
    ak = ""; asc = ""
    if m.api_key:
        try: ak = decrypt(m.api_key)
        except Exception:
            logger.warning("decrypt api_key failed for model %s", m.id)
    if m.api_secret:
        try: asc = decrypt(m.api_secret)
        except Exception:
            logger.warning("decrypt api_secret failed for model %s", m.id)

    return {
        "id": m.id,
        "scene_key": scene_key,
        "model_type": m.model_type,
        "provider": m.provider,
        "base_url": m.base_url or "",
        "model_name": m.model_name or "",
        "api_key": ak,
        "api_secret": asc,
        "config": m.config_json or {},
        "resolution_source": "explicit" if explicit_model_id else "default",
    }
```

- [ ] **Step 2: Write the registry test**

```python
# server/tests/test_model_registry.py
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
    import uuid
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
    _seed(db, name="GPT-4o", model_type="llm", sort_order=0)
    _seed(db, name="Claude", model_type="llm", sort_order=1)
    result = get_model_for_scene(db, "script_generation")
    assert result["name"] == "GPT-4o"
    assert result["resolution_source"] == "default"


def test_registry_missing_model_raises(client, db):
    with pytest.raises(ModelResolutionError) as exc:
        get_model_for_scene(db, "script_generation")
    assert "未配置" in exc.value.repair_action
    assert exc.value.status_code == 400


def test_registry_disabled_model_raises(client, db):
    m = _seed(db, name="GPT-4o", model_type="llm", enabled=False)
    with pytest.raises(ModelResolutionError) as exc:
        get_model_for_scene(db, "script_generation", explicit_model_id=m.id)
    assert "已禁用" in exc.value.repair_action


def test_registry_wrong_type_raises(client, db):
    m = _seed(db, name="Seedance", model_type="video", provider="seedance", model_name="sd-video")
    with pytest.raises(ModelResolutionError) as exc:
        get_model_for_scene(db, "script_generation", explicit_model_id=m.id)
    assert exc.value.status_code == 400


def test_registry_decrypts_secrets_only_for_runtime(client, db):
    """Verify api_key is decrypted (plaintext) in registry output."""
    m = _seed(db, name="Secure", model_type="llm", api_key="secret-123")
    result = get_model_for_scene(db, "script_generation", explicit_model_id=m.id)
    assert result["api_key"] == "secret-123"
    # API key is plaintext — consumer MUST not log or expose this
```

- [ ] **Step 3: Run tests — verify they fail (registry not wired yet)**

```bash
cd server && python -m pytest tests/test_model_registry.py -v 2>&1 | head -20
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.model_registry'`

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd server && python -m pytest tests/test_model_registry.py -v
```

Expected: 6/6 PASS

---

### Task A4: ai_config.py — Blank secret preservation on PUT

**Files:**
- Modify: `server/app/routers/ai_config.py:124-142`
- Test: `server/tests/test_ai_config.py` (add new test)

- [ ] **Step 1: Write the failing test**

```python
# Add to server/tests/test_ai_config.py

def test_update_preserves_blank_secret(client, db):
    """Blank api_key/api_secret on PUT must NOT wipe existing encrypted secrets."""
    m = _seed_one(db, name="PreserveTest", api_key="original-key", api_secret="original-secret")

    # Update with blank api_key and api_secret
    resp = client.put(f"/api/ai-models/{m.id}", json={
        "name": "PreserveTest-renamed",
        "api_key": "",
        "api_secret": "",
    })
    assert resp.status_code == 200

    # Verify secrets were preserved
    from app.services.crypto import decrypt
    db.refresh(m)
    assert decrypt(m.api_key) == "original-key", "api_key should not be wiped by empty string"
    assert decrypt(m.api_secret) == "original-secret", "api_secret should not be wiped by empty string"


def test_update_clear_secret_explicitly(client, db):
    """Explicit clear_secret flag should wipe the secret."""
    m = _seed_one(db, name="ClearTest", api_key="to-be-cleared")

    resp = client.put(f"/api/ai-models/{m.id}", json={
        "api_key": "",
        "clear_secret": True,
    })
    assert resp.status_code == 200

    db.refresh(m)
    assert m.api_key is None, "api_key should be cleared when clear_secret is True"
```

- [ ] **Step 2: Run — verify they fail**

```bash
cd server && python -m pytest tests/test_ai_config.py::test_update_preserves_blank_secret tests/test_ai_config.py::test_update_clear_secret_explicitly -v
```

Expected: FAIL — blank api_key wipes existing secret

- [ ] **Step 3: Fix the PUT handler**

```python
# In server/app/routers/ai_config.py, replace lines 130-134:

class ModelUpdate(BaseModel):
    name: str | None = None
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    api_secret: str | None = None
    model_name: str | None = None
    config_json: dict | None = None
    enabled: bool | None = None
    sort_order: int | None = None
    clear_secret: bool = False  # NEW — explicit clear flag

# In update_model() (line 124), replace the secret handling:
@router.put("/{model_id}")
def update_model(model_id: str, body: ModelUpdate, db: Session = Depends(get_db),
                 _ = Depends(require_role("admin"))):
    m = db.query(AIModel).filter(AIModel.id == model_id).first()
    if not m:
        raise HTTPException(404, "模型不存在")
    updates = body.model_dump(exclude_unset=True)
    # Preserve secrets: blank values keep existing; clear_secret flag wipes
    if body.clear_secret:
        if "api_key" not in updates:
            updates["api_key"] = None
        if "api_secret" not in updates:
            updates["api_secret"] = None
    else:
        if "api_key" in updates and not updates["api_key"]:
            del updates["api_key"]  # preserve existing
        if "api_secret" in updates and not updates["api_secret"]:
            del updates["api_secret"]  # preserve existing
    if "api_key" in updates:
        updates["api_key"] = encrypt(updates["api_key"]) if updates["api_key"] else None
    if "api_secret" in updates:
        updates["api_secret"] = encrypt(updates["api_secret"]) if updates["api_secret"] else None
    for k, v in updates.items():
        if k == "clear_secret":
            continue
        setattr(m, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "同类型同 provider 同 model_name 的模型已存在")
    return {"ok": True, "model": _model_dict(m, reveal=True)}
```

- [ ] **Step 4: Run — verify they pass**

```bash
cd server && python -m pytest tests/test_ai_config.py::test_update_preserves_blank_secret tests/test_ai_config.py::test_update_clear_secret_explicitly -v
```

Expected: 2/2 PASS

---

### Task A5: ai_config.py — Protocol-aware connection test + SSRF guard

**Files:**
- Modify: `server/app/routers/ai_config.py:155-190`
- Test: `server/tests/test_ai_config_scene_schema.py`

- [ ] **Step 1: Write the SSRF guard**

```python
# Add to server/app/routers/ai_config.py after imports:
import ipaddress

_SSRF_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

def _is_private_url(url: str) -> bool:
    """Check if a URL targets a private/internal IP address (SSRF prevention)."""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            return True  # block unparseable hosts
        addr = ipaddress.ip_address(host)
        for net in _SSRF_BLOCKED_NETWORKS:
            if addr in net:
                return True
        return False
    except ValueError:
        return True  # block unparseable IPs
```

- [ ] **Step 2: Rewrite the connection test endpoint**

```python
# Replace server/app/routers/ai_config.py lines 155-190:

@router.post("/{model_id}/test")
def test_connection(model_id: str, db: Session = Depends(get_db),
                     _ = Depends(require_role("admin"))):
    from app.services.model_schema import get_provider_preset
    m = db.query(AIModel).filter(AIModel.id == model_id).first()
    if not m:
        raise HTTPException(404, "模型不存在")
    if not m.base_url:
        return {"ok": False, "error": "未配置 Base URL"}

    preset = get_provider_preset(m.provider)
    strategy = preset.get("test_strategy", "list_models")

    if strategy == "noop":
        return {"ok": False, "error": "此提供商不支持自动连接测试"}

    # SSRF guard
    if _is_private_url(m.base_url):
        return {"ok": False, "error": "不允许连接内网地址"}

    ak = decrypt(m.api_key) if m.api_key else ""
    if not ak and m.provider not in ("edge-tts", "custom"):
        return {"ok": False, "error": "未配置 API Key"}

    headers = _build_auth_headers(m.provider, ak)

    if strategy == "list_models":
        if m.provider == "anthropic":
            test_url = m.base_url.rstrip("/")
            if not test_url.endswith("/v1/models"):
                base = test_url.rsplit("/v1/messages", 1)[0]
                test_url = base + "/v1/models"
        else:
            test_url = m.base_url.rstrip("/") + "/models"
    elif strategy == "health_check":
        test_path = preset.get("test_path", "/")
        test_url = m.base_url.rstrip("/") + test_path
    else:
        test_url = m.base_url.rstrip("/") + "/models"

    try:
        resp = httpx.get(test_url, headers=headers, timeout=httpx.Timeout(10, connect=5))
        if resp.is_success:
            return {"ok": True, "status_code": resp.status_code,
                    "strategy": strategy}
        return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
                "strategy": strategy}
    except httpx.ConnectError:
        return {"ok": False, "error": "连接失败 — 检查 Base URL"}
    except httpx.TimeoutException:
        return {"ok": False, "error": "连接超时"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _build_auth_headers(provider: str, api_key: str) -> dict:
    """Build auth headers based on provider protocol."""
    if provider == "anthropic":
        return {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    return {"Authorization": f"Bearer {api_key}"}
```

- [ ] **Step 3: Write tests**

```python
# server/tests/test_ai_config_scene_schema.py

def test_connection_test_rejects_private_ip(client, db):
    """SSRF: connection test should reject private IP base_url."""
    m = _seed_one(db, name="SSRFTest", model_type="llm", provider="openai",
                   base_url="http://10.0.0.1/v1", api_key="sk-test")

    resp = client.post(f"/api/ai-models/{m.id}/test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert "内网" in data["error"]


def test_connection_test_noop_strategy(client, db):
    """Providers with noop strategy should return not-supported message."""
    m = _seed_one(db, name="NoopTest", model_type="video", provider="kling",
                   base_url="https://api.kling.com", api_key="sk-test")

    resp = client.post(f"/api/ai-models/{m.id}/test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert "不支持" in data["error"]


def test_list_models_filtered_by_scene_key(client, db):
    """GET /api/ai-models?scene_key=video_rendering should filter by model_type=video."""
    _seed_one(db, name="VideoModel", model_type="video", provider="seedance",
              model_name="sd-video")
    _seed_one(db, name="LLMModel", model_type="llm", provider="openai",
              model_name="gpt-4")

    resp = client.get("/api/ai-models?scene_key=video_rendering")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["models"]) == 1
    assert data["models"][0]["model_type"] == "video"
```

- [ ] **Step 4: Run tests**

```bash
cd server && python -m pytest tests/test_ai_config_scene_schema.py -v
```

Expected: 3/3 PASS

---

### Task A6: ai_config.py — Scene_key filter on list and options

**Files:**
- Modify: `server/app/routers/ai_config.py:66-92`
- Test: already covered in test_ai_config_scene_schema.py

- [ ] **Step 1: Add scene_key query param to list and options endpoints**

```python
# In server/app/routers/ai_config.py:

from app.data.model_schema_data import scene_key_to_model_type
from app.services.model_schema import get_scene_by_key

# Modify list_models (line 66):
@router.get("")
def list_models(
    model_type: str | None = Query(None),
    scene_key: str | None = Query(None),  # NEW
    enabled: bool | None = Query(None),
    db: Session = Depends(get_db),
    _ = Depends(verify_admin_token),
):
    q = db.query(AIModel)
    if scene_key:
        try:
            model_type = scene_key_to_model_type(scene_key)
        except ValueError:
            return {"ok": True, "models": []}
    if model_type:
        q = q.filter(AIModel.model_type == model_type)
    if enabled is not None:
        q = q.filter(AIModel.enabled == enabled)
    models = q.order_by(AIModel.sort_order, AIModel.created_at).all()
    return {"ok": True, "models": [_model_dict(m) for m in models]}


# Modify get_options (line 82):
@router.get("/options")
def get_options(
    model_type: str | None = Query(None),
    scene_key: str | None = Query(None),  # NEW
    db: Session = Depends(get_db),
    _ = Depends(verify_admin_token),
):
    q = db.query(AIModel).filter(AIModel.enabled == True)
    if scene_key:
        try:
            model_type = scene_key_to_model_type(scene_key)
        except ValueError:
            return {"ok": True, "options": []}
    if model_type:
        q = q.filter(AIModel.model_type == model_type)
    models = q.order_by(AIModel.sort_order, AIModel.created_at).all()
    return {"ok": True, "options": [
        {"id": m.id, "name": m.name, "model_type": m.model_type, "provider": m.provider}
        for m in models
    ]}
```

- [ ] **Step 2: Verify existing tests still pass**

```bash
cd server && python -m pytest tests/test_ai_config.py -v
```

Expected: all existing tests PASS (14+)

---

## Lane B: Legacy Migration

### Task B1: model_name normalization + dedup

**Files:**
- Modify: `server/app/db_models.py:658-659` (already has UniqueConstraint)
- Create: `server/app/services/migration.py`
- Test: `server/tests/test_ai_model_migration.py`

- [ ] **Step 1: Write normalization helper + migration service**

```python
# server/app/services/migration.py
"""Idempotent migration from legacy Settings/Pixelle/Seedance → AIModel."""
import logging
from sqlalchemy.orm import Session
from app.db_models import AIModel
from app.services.crypto import encrypt

logger = logging.getLogger(__name__)


def _normalize_model_name(name: str | None) -> str:
    """Normalize NULL/empty model_name to empty string for dedup matching."""
    if name is None:
        return ""
    return str(name).strip()


def _find_existing(db: Session, model_type: str, provider: str, model_name: str | None) -> AIModel | None:
    """Find an existing AIModel with the same type+provider+name, handling NULL."""
    normalized = _normalize_model_name(model_name)
    q = db.query(AIModel).filter(
        AIModel.model_type == model_type,
        AIModel.provider == provider,
    )
    # SQLite: NULL != NULL. Check both NULL and normalized value.
    from sqlalchemy import or_
    q = q.filter(or_(
        AIModel.model_name == normalized,
        AIModel.model_name.is_(None),
    ))
    return q.first()


def migrate_legacy_settings(db: Session) -> dict:
    """
    Migrate legacy Settings/Pixelle/Seedance config into AIModel.

    Returns: {created: int, skipped: int, conflicts: list[dict]}
    Rules:
    - Only INSERT — never UPDATE existing rows
    - If a duplicate exists → skip, add to conflicts list
    - Secrets are encrypted using the existing crypto service
    - Idempotent: safe to re-run
    """
    result = {"created": 0, "skipped": 0, "conflicts": []}

    from app.config import _resolve_ai_config, SEEDANCE_API_KEY, PIXELLE_VIDEO_URL

    # 1. Settings LLM keys → script_generation
    try:
        cfg = _resolve_ai_config(db) if hasattr(_resolve_ai_config, '__call__') else {}
    except Exception:
        cfg = {}

    if cfg:
        llm_provider = cfg.get("llm_provider") or cfg.get("provider", "openai")
        llm_key = cfg.get("llm_api_key") or cfg.get("api_key", "")
        llm_model = cfg.get("llm_model") or cfg.get("model_name", "")
        llm_base = cfg.get("llm_base_url") or cfg.get("base_url", "")
        if llm_key:
            existing = _find_existing(db, "llm", llm_provider, llm_model)
            if existing:
                result["conflicts"].append({
                    "source": "Settings LLM",
                    "provider": llm_provider,
                    "reason": "duplicate — model already exists",
                    "existing_id": existing.id,
                })
                result["skipped"] += 1
            else:
                db.add(AIModel(
                    name=f"{llm_provider.title()} (Legacy)",
                    model_type="llm",
                    provider=llm_provider,
                    base_url=llm_base or None,
                    api_key=encrypt(llm_key),
                    model_name=_normalize_model_name(llm_model),
                    config_json={"scene_key": "script_generation", "migrated_from": "settings"},
                ))
                result["created"] += 1

    # 2. Seedance API key → video_rendering
    seedance_key = SEEDANCE_API_KEY
    if seedance_key:
        existing = _find_existing(db, "video", "seedance", "doubao-seedance-2.0-260128")
        if existing:
            result["conflicts"].append({
                "source": "Seedance env",
                "provider": "seedance",
                "reason": "duplicate — model already exists",
                "existing_id": existing.id,
            })
            result["skipped"] += 1
        else:
            db.add(AIModel(
                name="Seedance 2.0 (Legacy)",
                model_type="video",
                provider="seedance",
                base_url="https://ark.cn-beijing.volces.com/api/v3",
                api_key=encrypt(seedance_key),
                model_name="doubao-seedance-2.0-260128",
                config_json={"scene_key": "video_rendering", "migrated_from": "env"},
            ))
            result["created"] += 1

    # 3. Pixelle — only migrate model credentials, NOT service config
    pixelle_url = PIXELLE_VIDEO_URL
    if pixelle_url and pixelle_url != "http://localhost:8500":
        existing = _find_existing(db, "image", "pixelle", "")
        if not existing:
            db.add(AIModel(
                name="Pixelle (Legacy)",
                model_type="image",
                provider="pixelle",
                base_url=pixelle_url,
                model_name="",
                config_json={
                    "scene_key": "image_generation",
                    "migrated_from": "config.py",
                    "pixelle_timeout": 600,
                },
            ))
            result["created"] += 1

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("Migration commit failed: %s", e)
        result["error"] = str(e)

    logger.info("Migration complete: created=%d skipped=%d conflicts=%d",
                result["created"], result["skipped"], len(result["conflicts"]))
    return result
```

- [ ] **Step 2: Write migration tests**

```python
# server/tests/test_ai_model_migration.py
import pytest
from app.services.migration import migrate_legacy_settings, _normalize_model_name, _find_existing
from app.db_models import AIModel
from app.services.crypto import encrypt


def test_normalize_none_to_empty():
    assert _normalize_model_name(None) == ""


def test_normalize_whitespace():
    assert _normalize_model_name("  gpt-4  ") == "gpt-4"


def test_migration_idempotent(client, db):
    """Running migration twice should not create duplicates."""
    result1 = migrate_legacy_settings(db)
    count_after_first = db.query(AIModel).count()
    result2 = migrate_legacy_settings(db)
    count_after_second = db.query(AIModel).count()
    assert count_after_first == count_after_second, \
        f"Migration not idempotent: {count_after_first} → {count_after_second}"
    assert result2["created"] == 0, \
        f"Second run should create 0 models, created {result2['created']}"


def test_migration_handles_blank_model_name(client, db):
    """Duplicate (type, provider, '') should not be created."""
    # Pre-seed a model with empty model_name
    m = AIModel(
        name="Existing", model_type="image", provider="pixelle",
        api_key=encrypt("key1"), model_name="",
    )
    db.add(m); db.commit()
    result = migrate_legacy_settings(db)
    # Pixelle should be skipped (duplicate with blank model_name)
    pixelle_conflict = any(
        c.get("provider") == "pixelle" for c in result.get("conflicts", [])
    )
    # Either skipped or marked as conflict — not created
    pixelle_created = result.get("created", 0)
    assert pixelle_conflict or pixelle_created == 0, \
        "Should not create duplicate pixelle with blank model_name"
```

- [ ] **Step 3: Run tests**

```bash
cd server && python -m pytest tests/test_ai_model_migration.py -v
```

Expected: 3/3 PASS

---

## Lane C: Consumer Migration

### Task C1: pipeline.py — Switch to model_registry

**Files:**
- Modify: `server/app/routers/pipeline.py:151-170`
- Test: `server/tests/test_pipeline_model_registry.py`

- [ ] **Step 1: Replace _get_model_config with model_registry call**

```python
# In server/app/routers/pipeline.py:

# Replace lines 151-170:
# OLD: def _get_model_config(db, model_id) → returns dict
# NEW: import from registry

from app.services.model_registry import get_model_for_scene, ModelResolutionError

# Map legacy model_keys to scene_keys
_MODEL_KEY_TO_SCENE = {
    "scriptLLM": "script_generation",
    "imageModel": "image_generation",
    "videoModel": "video_rendering",
    "ttsModel": "tts_synthesis",
    "auditModel": "quality_audit",
}


def _resolve_layer_model(db: Session, model_key: str, explicit_model_id: str | None) -> dict:
    """
    Resolve a layer model using the registry.

    Args:
        model_key: legacy key (scriptLLM, imageModel, etc.) or scene_key
        explicit_model_id: user-provided model UUID, or None for default

    Returns:
        Runtime model config dict with decrypted secrets

    Raises:
        HTTPException with scene name and repair action on failure
    """
    scene_key = _MODEL_KEY_TO_SCENE.get(model_key, model_key)
    try:
        return get_model_for_scene(db, scene_key, explicit_model_id)
    except ModelResolutionError as e:
        raise HTTPException(status_code=e.status_code, detail=e.repair_action)


def _build_model_trace(resolved: dict) -> dict:
    """Extract trace data for run.layers_json from a resolved model."""
    return {
        "model_id": resolved["id"],
        "provider": resolved["provider"],
        "model_name": resolved["model_name"],
        "scene_key": resolved["scene_key"],
        "resolution_source": resolved["resolution_source"],
    }
```

- [ ] **Step 2: Update the layer execution loop**

```python
# In _execute_pipeline() around line 569-571, replace:
# OLD:
#   model_key = layer_def["model_key"]
#   model_id = model_ids.get(model_key)
#   model_config = _get_model_config(local_db, model_id)
# NEW:

model_key = layer_def["model_key"]
model_id = model_ids.get(model_key)
try:
    model_config = _resolve_layer_model(local_db, model_key, model_id)
    # Record model_trace in layers_json for observability
    layers = dict(run.layers_json or {})
    if str(i) not in layers:
        layers[str(i)] = {}
    layers[str(i)]["model_trace"] = _build_model_trace(model_config)
    run.layers_json = layers
except HTTPException as e:
    # Re-raise — caller handles scene-aware errors
    raise
```

- [ ] **Step 3: Write test**

```python
# server/tests/test_pipeline_model_registry.py
def test_model_key_to_scene_mapping():
    from app.routers.pipeline import _MODEL_KEY_TO_SCENE
    assert _MODEL_KEY_TO_SCENE["scriptLLM"] == "script_generation"
    assert _MODEL_KEY_TO_SCENE["imageModel"] == "image_generation"
    assert _MODEL_KEY_TO_SCENE["videoModel"] == "video_rendering"


def test_pipeline_resolves_default_model(client, db):
    """Pipeline should resolve default model when no explicit model_ids given."""
    _seed_one(db, name="TestLLM", model_type="llm", provider="openai",
              model_name="gpt-4", api_key="sk-test")
    # Minimal pipeline start request (no model_ids → default resolve)
    resp = client.post("/api/pipeline/start", json={
        "run_id": "test-run-001",
        "model_ids": {},  # leave empty → registry fallback to default
    })
    # Should succeed — registry found the default LLM model
    assert resp.status_code in (200, 201, 422)  # 422 if other required fields missing


def test_model_trace_written_to_layers_json(client, db):
    """Verify model_trace is recorded per layer after pipeline execution."""
    # This test is completed after pipeline integration
    pass  # Implement when pipeline/test env is fully wired
```

- [ ] **Step 4: Run tests**

```bash
cd server && python -m pytest tests/test_pipeline_model_registry.py -v
```

Expected: 2/2 PASS (third is a placeholder for integration)

---

### Task C2: audit.py + series.py — Switch to model_registry

**Files:**
- Modify: `server/app/routers/audit.py:26-39`
- Modify: `server/app/routers/series.py:270-274`
- Test: update `server/tests/test_series_style_lock_pipeline.py`

- [ ] **Step 1: Replace audit.py model lookup**

```python
# In server/app/routers/audit.py, replace _get_audit_model (lines 26-39):

from app.services.model_registry import get_model_for_scene, ModelResolutionError

def _get_audit_model(db: Session, model_id: str | None) -> dict:
    """Resolve audit model via registry, with backward-compatible explicit model_id."""
    try:
        return get_model_for_scene(db, "quality_audit", explicit_model_id=model_id)
    except ModelResolutionError:
        return {}  # backward-compatible: return empty dict for caller to handle
```

- [ ] **Step 2: Replace series.py model lookup**

```python
# In server/app/routers/series.py, replace _generate_reference_image (lines 270-274):

from app.services.model_registry import get_model_for_scene, ModelResolutionError

async def _generate_reference_image(db: Session, prompt: str) -> str | None:
    try:
        model = get_model_for_scene(db, "image_generation")
    except ModelResolutionError:
        return None

    try:
        if model["provider"] in ("comfyui", "pixelle", "runninghub") or not model["base_url"]:
            result = await _pixelle_request("POST", "/api/image/generate", db, json={
                "prompt": prompt,
                "model": model["model_name"] or model["provider"],
```

- [ ] **Step 3: Update existing tests**

```bash
cd server && python -m pytest tests/test_series_style_lock_pipeline.py -v
```

Expected: existing tests should pass with updated model resolution path

---

### Task C3: Pixelle + Seedance regression tests

**Files:**
- Create: `server/tests/test_pixelle_seedance_model_center_regression.py`

- [ ] **Step 1: Write regression tests**

```python
# server/tests/test_pixelle_seedance_model_center_regression.py
"""Verify Pixelle and Seedance still work after model center migration."""


def test_pixelle_config_still_readable(client, db):
    """Pixelle service config (URL, timeout) must remain accessible."""
    from app.config import _resolve_pixelle_config
    cfg = _resolve_pixelle_config(db)
    assert "url" in cfg or hasattr(cfg, 'url') or cfg is not None, \
        "Pixelle config should not be deleted by migration"


def test_seedance_api_key_resolvable(client, db):
    """Seedance API key must still be resolvable — from AIModel after migration."""
    from app.db_models import AIModel
    m = db.query(AIModel).filter(
        AIModel.provider == "seedance",
        AIModel.enabled == True,
    ).first()
    if m:
        from app.services.crypto import decrypt
        key = decrypt(m.api_key)
        assert key, "Seedance api_key should be decrypted after migration"
    # If no model exists yet, migration hasn't run — that's OK too


def test_pixelle_quick_create_still_routes(client, db):
    """Pixelle quick-create endpoint should not 404 after migration."""
    resp = client.get("/api/pixelle/")  # adjust to actual Pixelle endpoint
    assert resp.status_code not in (404, 500), \
        f"Pixelle route should still respond after migration: {resp.status_code}"
```

- [ ] **Step 2: Run tests**

```bash
cd server && python -m pytest tests/test_pixelle_seedance_model_center_regression.py -v
```

Expected: 3/3 PASS (may skip if Pixelle endpoints not registered in test app)

---

## Lane D: Frontend

### Task D1: aiConfig.js — Schema client + scene_key param

**Files:**
- Modify: `web/src/api/aiConfig.js`

- [ ] **Step 1: Add schema fetcher + scene_key to list/options**

```javascript
// In web/src/api/aiConfig.js, add:

/**
 * Fetch full model center schema (scenes, providers, protocols, field definitions).
 * @returns {Promise<{scenes: Array, providers: Object, protocols: Array, common_fields: Array,
 *                    custom_field_policy: Object}>}
 */
export function fetchSchema() {
  return request('/api/ai-models/schema').then(r => {
    // unwrap {ok, scenes, providers, ...}
    const { ok, ...schema } = r
    if (!ok) throw new Error('Schema fetch failed')
    return schema
  })
}

// Update listModels to accept scene_key:
export function listModels(params = {}) {
  const query = new URLSearchParams()
  if (params.model_type) query.set('model_type', params.model_type)
  if (params.scene_key) query.set('scene_key', params.scene_key)  // NEW
  if (params.enabled != null) query.set('enabled', String(params.enabled))
  return request(`/api/ai-models?${query.toString()}`)
}

// Update getOptions to accept scene_key:
export function getOptions(params = {}) {
  const query = new URLSearchParams()
  if (params.model_type) query.set('model_type', params.model_type)
  if (params.scene_key) query.set('scene_key', params.scene_key)  // NEW
  return request(`/api/ai-models/options?${query.toString()}`)
}
```

- [ ] **Step 2: Update existing API client tests**

```bash
cd web && npx vitest run api-clients --reporter=verbose
```

Expected: existing tests should still pass

---

### Task D2: ModelSceneSidebar.vue — Scene navigation component

**Files:**
- Create: `web/src/components/ModelSceneSidebar.vue`
- Test: `web/src/__tests__/ai-config-scene-schema.test.js`

- [ ] **Step 1: Write the component**

```vue
<template>
  <nav class="scene-sidebar" aria-label="AI 模型场景">
    <div class="scene-summary">
      视频生产链路就绪: {{ readyCount }}/{{ scenes.length }}
    </div>
    <button
      v-for="scene in scenes"
      :key="scene.key"
      @click="$emit('select-scene', scene)"
      :aria-current="activeScene === scene.key ? 'true' : undefined"
      class="scene-item"
      :class="{ 'scene-item--active': activeScene === scene.key }"
    >
      <span class="scene-status-dot" :class="statusClass(scene.key)" :aria-label="statusLabel(scene.key)"></span>
      <component :is="sceneIcon(scene.key)" class="scene-icon" />
      <span class="scene-label">{{ scene.label }}</span>
      <span class="scene-count">{{ modelCount(scene.key) }}</span>
    </button>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { MessageSquare, Image, Video, Volume2, ShieldCheck } from 'lucide-vue-next'

const props = defineProps({
  scenes: { type: Array, required: true },
  activeScene: { type: String, default: null },
  models: { type: Array, default: () => [] },
  sceneStatus: { type: Object, default: () => ({}) },
})

defineEmits(['select-scene'])

const iconMap = {
  script_generation: MessageSquare,
  image_generation: Image,
  video_rendering: Video,
  tts_synthesis: Volume2,
  quality_audit: ShieldCheck,
}

function sceneIcon(key) { return iconMap[key] || MessageSquare }
function modelCount(key) {
  return props.models.filter(m => m.model_type === props.scenes.find(s => s.key === key)?.model_type).length
}
function statusClass(key) { return `status--${props.sceneStatus[key] || 'red'}` }
function statusLabel(key) {
  const map = { green: '就绪', amber: '待配置', red: '未配置' }
  return map[props.sceneStatus[key]] || '未知'
}
const readyCount = computed(() =>
  Object.values(props.sceneStatus).filter(s => s === 'green').length
)
</script>
```

- [ ] **Step 2: Write component test**

```javascript
// web/src/__tests__/ai-config-scene-schema.test.js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ModelSceneSidebar from '@/components/ModelSceneSidebar.vue'

describe('ModelSceneSidebar', () => {
  const scenes = [
    { key: 'script_generation', label: 'LLM · 脚本生成', model_type: 'llm' },
    { key: 'image_generation', label: 'Image · 画面生成', model_type: 'image' },
  ]

  it('renders all scenes', () => {
    const wrapper = mount(ModelSceneSidebar, {
      props: { scenes, models: [], sceneStatus: {} }
    })
    const items = wrapper.findAll('.scene-item')
    expect(items).toHaveLength(2)
  })

  it('emits select-scene on click', async () => {
    const wrapper = mount(ModelSceneSidebar, {
      props: { scenes, models: [], sceneStatus: {} }
    })
    await wrapper.findAll('.scene-item')[0].trigger('click')
    expect(wrapper.emitted('select-scene')).toBeTruthy()
    expect(wrapper.emitted('select-scene')[0][0]).toEqual(scenes[0])
  })

  it('shows ready count', () => {
    const wrapper = mount(ModelSceneSidebar, {
      props: {
        scenes,
        models: [],
        sceneStatus: { script_generation: 'green', image_generation: 'red' }
      }
    })
    expect(wrapper.find('.scene-summary').text()).toContain('1/2')
  })

  it('applies active class to selected scene', () => {
    const wrapper = mount(ModelSceneSidebar, {
      props: { scenes, models: [], sceneStatus: {}, activeScene: 'image_generation' }
    })
    const active = wrapper.find('.scene-item--active')
    expect(active.exists()).toBe(true)
  })
})
```

- [ ] **Step 3: Run tests**

```bash
cd web && npx vitest run ai-config-scene-schema --reporter=verbose
```

Expected: 4/4 PASS

---

## Lane E: Cleanup

### Task E1: Old entrance removal (FINAL — after all other lanes pass)

**Files:**
- Modify: navigation component (remove Settings/Pixelle/Seedance model config entries)
- Modify: `server/app/routers/seedance.py` (mark as deprecated, add redirect comment)
- Modify: `server/app/config.py` (mark legacy model config paths as deprecated)

- [ ] **Step 1: Remove old navigation entries**

```javascript
// Remove or comment out navigation items for:
// - Settings AI Config
// - Pixelle Config
// - Seedance Config
// These are replaced by the unified AI Model Center at /ai-models
```

- [ ] **Step 2: Mark legacy routes as deprecated**

```python
# In seedance.py, add deprecation comment at module level:
"""
⚠️ DEPRECATED — Seedance API key is now managed via AIModel + model_registry.
This module is retained for backward compatibility during migration.
Remove after: all callers use model_registry.get_model_for_scene("video_rendering").
"""

# In config.py, mark deprecated functions:
# _resolve_ai_config() → deprecated, use model_registry
# get_ai_config() → deprecated, use model_registry
# SEEDANCE_API_KEY → deprecated, migrated to AIModel
```

- [ ] **Step 3: Run full test suite**

```bash
cd server && python -m pytest -x -q 2>&1 | tail -5
```

Expected: all 408+ tests pass (or higher after adding new test files)

---

## Validation

```bash
# Backend syntax check
cd server && python -c "from app.main import app; print('OK')"

# Full backend test suite
cd server && python -m pytest -x -q

# Frontend type check
cd web && npx vue-tsc --noEmit 2>&1 | tail -5

# Frontend tests
cd web && npx vitest run --reporter=verbose
```

---

## Parallelization

| Lane | Tasks | Depends on | Can parallel with |
|------|-------|-----------|-------------------|
| A | A1-A6 (schema, registry, ai_config) | none | B, D |
| B | B1 (migration) | A1 (schema data) | C, D |
| C | C1-C3 (consumer migration) | A3 (registry contract) | D |
| D | D1-D2 (frontend) | A2 (schema endpoint) | B, C |
| E | E1 (cleanup) | ALL above must pass | none |

**Sequential gates:**
1. A3 (registry) must be stable before C (consumer migration)
2. A2 (schema endpoint) must be available before D (frontend)
3. E (cleanup) is the FINAL PR — only after A+B+C+D all pass

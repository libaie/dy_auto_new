# Bailian High-Quality Video Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configure and verify a dy_auto -> Pixelle-Video-dy high-quality video pipeline using Bailian `qwen3.7-plus` for script generation, expert review, and quality audit, with visible expert involvement and bounded paid smoke tests.

**Architecture:** Keep dy_auto as the orchestration and review layer. Store Bailian provider keys only in ignored local env/runtime DB, pass provider model config to Pixelle stage APIs, and use a separate local Pixelle bridge key for dy_auto-to-Pixelle authentication. Make one LLM model row usable by multiple LLM scenes via `scene_keys`, add a Bailian audit model row for quality audit, and keep paid media execution behind explicit safety gates.

**Tech Stack:** Python 3.12+/FastAPI/SQLAlchemy/Pydantic, pytest, SQLite runtime DB, Pixelle-Video-dy FastAPI stage API, Bailian DashScope OpenAI-compatible API.

---

## File Structure

- Modify `server/app/services/runtime_model_config.py`
  - Resolve runtime model config by either `config_json.scene_key` or membership in `config_json.scene_keys`.
- Modify `server/app/data/model_schema_data.py`
  - Allow Bailian in `script_generation` and `quality_audit` scenes.
- Modify `server/app/routers/ai_config.py`
  - Seed `qwen3.7-plus` as the default Bailian text model.
  - Seed a Bailian audit model for `quality_audit`.
  - Preserve compatibility with existing `qwen-plus` rows by adding newer rows without deleting old user data.
- Modify `server/scripts/smoke_bailian_one_sentence_e2e.py`
  - Stop bypassing expert gates by default.
  - Add an explicit `--bypass-expert-gates` escape hatch.
  - Log expert/audit evidence at the end of a smoke run.
- Modify tests:
  - `server/tests/test_runtime_model_config.py`
  - `server/tests/test_model_schema.py`
  - `server/tests/test_ai_config_scene_schema.py`
- Runtime-only files changed during execution:
  - `server/.env` (ignored)
  - `server/app/data/dy_auto.db` (ignored)
  - local processes for dy_auto backend/frontend and Pixelle API
- Do not modify `D:/codex/Pixelle-Video-dy/config.yaml` with secrets. It is tracked in that repository despite `.gitignore`.

---

### Task 1: Runtime Model Resolution and Bailian Defaults

**Files:**
- Modify: `server/app/services/runtime_model_config.py`
- Modify: `server/app/data/model_schema_data.py`
- Modify: `server/app/routers/ai_config.py`
- Test: `server/tests/test_runtime_model_config.py`
- Test: `server/tests/test_model_schema.py`
- Test: `server/tests/test_ai_config_scene_schema.py`

- [ ] **Step 1: Add failing runtime config tests for multi-scene LLM and Bailian audit**

Append to `server/tests/test_runtime_model_config.py`:

```python
def test_resolve_runtime_model_config_supports_scene_keys_array(db):
    model = AIModel(
        name="Bailian Qwen 3.7 Plus",
        model_type="llm",
        provider="bailian",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=encrypt("bailian-key"),
        model_name="qwen3.7-plus",
        enabled=True,
        sort_order=-100,
        config_json={
            "scene_keys": ["script_generation", "llm_agency_expert_review"],
            "protocol": "openai_chat_completions",
            "config_version": 37,
            "max_tokens": 8192,
            "temperature": 0.2,
        },
    )
    db.add(model)
    db.commit()

    script = resolve_runtime_model_config(db, "script_generation")
    expert = resolve_runtime_model_config(db, "llm_agency_expert_review")

    assert script["scene_key"] == "script_generation"
    assert expert["scene_key"] == "llm_agency_expert_review"
    assert script["model"] == "qwen3.7-plus"
    assert expert["model"] == "qwen3.7-plus"
    assert script["api_key"] == "bailian-key"
    assert expert["config"]["protocol"] == "openai_chat_completions"


def test_resolve_runtime_model_config_supports_bailian_quality_audit(db):
    model = AIModel(
        name="Bailian Qwen 3.7 Quality Audit",
        model_type="audit",
        provider="bailian",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=encrypt("audit-key"),
        model_name="qwen3.7-plus",
        enabled=True,
        sort_order=-100,
        config_json={
            "scene_key": "quality_audit",
            "protocol": "openai_chat_completions",
            "audit_mode": "image_quality_gate",
            "max_tokens": 2048,
            "temperature": 0.1,
        },
    )
    db.add(model)
    db.commit()

    resolved = resolve_runtime_model_config(db, "quality_audit")

    assert resolved["scene_key"] == "quality_audit"
    assert resolved["provider"] == "bailian"
    assert resolved["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert resolved["model"] == "qwen3.7-plus"
    assert resolved["api_key"] == "audit-key"
```

- [ ] **Step 2: Run the focused runtime tests and confirm failure**

Run:

```powershell
cd D:\codex\dy_auto_new\server
.\.venv\Scripts\python.exe -m pytest tests/test_runtime_model_config.py -q
```

Expected before implementation: the new `scene_keys` test fails because `resolve_runtime_model_config` only filters on `config_json.scene_key`.

- [ ] **Step 3: Implement runtime multi-scene matching**

Replace the query body in `server/app/services/runtime_model_config.py` with this implementation:

```python
def _model_matches_scene(model: AIModel, scene_key: str) -> bool:
    config = model.config_json or {}
    if config.get("scene_key") == scene_key:
        return True
    scene_keys = config.get("scene_keys")
    return isinstance(scene_keys, list) and scene_key in scene_keys


def resolve_runtime_model_config(db: Session, scene_key: str, explicit_model_id: str | None = None) -> dict:
    query = db.query(AIModel).filter(AIModel.enabled == True)
    if explicit_model_id:
        query = query.filter(AIModel.id == explicit_model_id)
        model = query.first()
        if not model or not _model_matches_scene(model, scene_key):
            raise RuntimeModelConfigError(f"No enabled model configured for scene '{scene_key}'")
    else:
        model = None
        for candidate in query.order_by(AIModel.sort_order.asc(), AIModel.created_at.asc()).all():
            if _model_matches_scene(candidate, scene_key):
                model = candidate
                break
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
```

- [ ] **Step 4: Add schema/default tests for Bailian script and audit scenes**

Append to `server/tests/test_model_schema.py`:

```python
def test_script_generation_scene_supports_bailian_provider(client):
    response = client.get("/api/ai-models/schema", headers={"Authorization": "Bearer test-admin"})
    data = response.json()
    scene = next(item for item in data["scenes"] if item["key"] == "script_generation")
    bailian = data["providers"]["bailian"]

    assert "bailian" in scene["providers"]
    assert bailian["default_base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert bailian["protocol"] == "openai_chat_completions"


def test_quality_audit_scene_supports_bailian_provider(client):
    response = client.get("/api/ai-models/schema", headers={"Authorization": "Bearer test-admin"})
    data = response.json()
    scene = next(item for item in data["scenes"] if item["key"] == "quality_audit")

    assert "bailian" in scene["providers"]
```

Update `server/tests/test_ai_config_scene_schema.py` so the Bailian expert default assertions expect `qwen3.7-plus`, and append:

```python
def test_default_bailian_text_model_targets_qwen37_plus_for_script_and_expert():
    model = next(m for m in DEFAULT_MODELS if m["name"] == "Bailian Qwen 3.7 Plus")

    assert model["model_type"] == "llm"
    assert model["provider"] == "bailian"
    assert model["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert model["model_name"] == "qwen3.7-plus"
    assert model["config_json"]["scene_keys"] == ["script_generation", "llm_agency_expert_review"]
    assert model["config_json"]["max_tokens"] >= 8192


def test_default_bailian_quality_audit_model_targets_qwen37_plus():
    model = next(m for m in DEFAULT_MODELS if m["name"] == "Bailian Qwen 3.7 Quality Audit")

    assert model["model_type"] == "audit"
    assert model["provider"] == "bailian"
    assert model["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert model["model_name"] == "qwen3.7-plus"
    assert model["config_json"]["scene_key"] == "quality_audit"
```

- [ ] **Step 5: Run schema/default tests and confirm failure**

Run:

```powershell
cd D:\codex\dy_auto_new\server
.\.venv\Scripts\python.exe -m pytest tests/test_model_schema.py tests/test_ai_config_scene_schema.py -q
```

Expected before implementation: the new schema/default assertions fail.

- [ ] **Step 6: Implement schema and defaults**

In `server/app/data/model_schema_data.py`, add `"bailian"` to `script_generation.providers` and `quality_audit.providers`.

In `server/app/routers/ai_config.py`, add constants:

```python
BAILIAN_QWEN_37_PLUS_MODEL = "qwen3.7-plus"
```

Add these entries to `DEFAULT_MODELS` before lower-priority OpenAI/DeepSeek defaults:

```python
{
    "name": "Bailian Qwen 3.7 Plus",
    "model_type": "llm",
    "provider": "bailian",
    "base_url": BAILIAN_COMPATIBLE_BASE_URL,
    "model_name": BAILIAN_QWEN_37_PLUS_MODEL,
    "config_json": {
        "scene_keys": ["script_generation", "llm_agency_expert_review"],
        "protocol": "openai_chat_completions",
        "thinking_enabled": False,
        "thinking_budget": 8192,
        "max_tokens": 8192,
        "temperature": 0.2,
        "quality_priority": "high",
    },
}
```

```python
{
    "name": "Bailian Qwen 3.7 Quality Audit",
    "model_type": "audit",
    "provider": "bailian",
    "base_url": BAILIAN_COMPATIBLE_BASE_URL,
    "model_name": BAILIAN_QWEN_37_PLUS_MODEL,
    "config_json": {
        "scene_key": "quality_audit",
        "protocol": "openai_chat_completions",
        "audit_mode": "image_quality_gate",
        "max_tokens": 2048,
        "temperature": 0.1,
    },
}
```

Keep the legacy `Bailian Qwen Expert Review` entry for compatibility, but change its `model_name` to `qwen3.7-plus` only if doing so does not create a duplicate default. The preferred implementation is the new multi-scene `Bailian Qwen 3.7 Plus` row plus disabling old lower-priority rows during local configuration.

- [ ] **Step 7: Run focused tests and commit**

Run:

```powershell
cd D:\codex\dy_auto_new\server
.\.venv\Scripts\python.exe -m pytest tests/test_runtime_model_config.py tests/test_model_schema.py tests/test_ai_config_scene_schema.py -q
```

Expected: all selected tests pass.

Commit:

```powershell
cd D:\codex\dy_auto_new
git add server/app/services/runtime_model_config.py server/app/data/model_schema_data.py server/app/routers/ai_config.py server/tests/test_runtime_model_config.py server/tests/test_model_schema.py server/tests/test_ai_config_scene_schema.py
git commit -m "feat: configure bailian qwen high quality model scenes"
```

---

### Task 2: Expert-Involved Smoke Harness

**Files:**
- Modify: `server/scripts/smoke_bailian_one_sentence_e2e.py`
- Test: `server/tests/test_bailian_smoke_script_contract.py`

- [ ] **Step 1: Add failing smoke script contract tests**

Create `server/tests/test_bailian_smoke_script_contract.py`:

```python
import argparse

from scripts import smoke_bailian_one_sentence_e2e as smoke


def test_smoke_parser_does_not_bypass_expert_gates_by_default(monkeypatch):
    monkeypatch.setattr(
        smoke.argparse.ArgumentParser,
        "parse_args",
        lambda self: argparse.Namespace(
            prompt="测试",
            title="测试",
            budget=5.0,
            duration=15,
            worker_batch_size=1,
            max_worker_rounds=80,
            resume_run_id="",
            bypass_expert_gates=False,
        ),
    )

    args = smoke._parse_args()

    assert args.bypass_expert_gates is False


def test_smoke_installs_gate_overrides_only_when_requested(monkeypatch):
    calls = []
    monkeypatch.setattr(smoke, "_install_smoke_gate_overrides", lambda: calls.append("override"))

    smoke._maybe_install_smoke_gate_overrides(False)
    assert calls == []

    smoke._maybe_install_smoke_gate_overrides(True)
    assert calls == ["override"]
```

- [ ] **Step 2: Run the new smoke script tests and confirm failure**

Run:

```powershell
cd D:\codex\dy_auto_new\server
.\.venv\Scripts\python.exe -m pytest tests/test_bailian_smoke_script_contract.py -q
```

Expected before implementation: import or attribute failures because `_maybe_install_smoke_gate_overrides` and the parser flag do not exist.

- [ ] **Step 3: Implement the explicit expert bypass flag**

In `server/scripts/smoke_bailian_one_sentence_e2e.py`, update `_parse_args()`:

```python
    parser.add_argument(
        "--bypass-expert-gates",
        action="store_true",
        help="Bypass agency/expert provider gates. Default is false so paid smoke exercises expert involvement.",
    )
```

Add this helper after `_install_smoke_gate_overrides()`:

```python
def _maybe_install_smoke_gate_overrides(enabled: bool) -> None:
    if enabled:
        _install_smoke_gate_overrides()
        _log("expert_gates_bypassed", explicit=True)
    else:
        _log("expert_gates_active", explicit=True)
```

Replace this line in `_main()`:

```python
    _install_smoke_gate_overrides()
```

with:

```python
    _maybe_install_smoke_gate_overrides(args.bypass_expert_gates)
```

Move `args = _parse_args()` before `_maybe_install_smoke_gate_overrides(...)`.

- [ ] **Step 4: Add expert evidence logging**

Add imports:

```python
from app.db_models import AgencyInvocation, ProductionAuditEvent
```

Add this helper near `_approve_assets()`:

```python
def _log_expert_evidence(db, run_id: str) -> None:
    invocation_count = (
        db.query(AgencyInvocation)
        .filter(AgencyInvocation.run_id == run_id)
        .count()
    )
    audit_event_count = (
        db.query(ProductionAuditEvent)
        .filter(ProductionAuditEvent.run_id == run_id)
        .count()
    )
    _log(
        "expert_evidence",
        run_id=run_id,
        agency_invocation_count=invocation_count,
        production_audit_event_count=audit_event_count,
        expert_involvement_visible=invocation_count > 0 or audit_event_count > 0,
    )
```

Call it before the final `"completed"` log:

```python
        _log_expert_evidence(db, run.id)
```

- [ ] **Step 5: Run smoke contract tests and commit**

Run:

```powershell
cd D:\codex\dy_auto_new\server
.\.venv\Scripts\python.exe -m pytest tests/test_bailian_smoke_script_contract.py -q
```

Expected: pass.

Commit:

```powershell
cd D:\codex\dy_auto_new
git add server/scripts/smoke_bailian_one_sentence_e2e.py server/tests/test_bailian_smoke_script_contract.py
git commit -m "test: keep bailian smoke expert gates active by default"
```

---

### Task 3: Local Secret and Model Configuration

**Files:**
- Modify runtime-only: `server/.env`
- Modify runtime-only: `server/app/data/dy_auto.db`
- Do not modify tracked Pixelle `config.yaml`.

- [ ] **Step 1: Set process-only secret variables**

Run in the same PowerShell session that will execute the configuration script. Assign the values from the user-provided Bailian keys in the active thread. Do not print the values.

```powershell
$env:BAILIAN_KEY_PRIMARY = Read-Host -Prompt 'Paste Bailian key 1'
$env:BAILIAN_KEY_SECONDARY = Read-Host -Prompt 'Paste Bailian key 2'
$env:PIXELLE_BRIDGE_KEY = [guid]::NewGuid().ToString("N")
```

The literal key values must not be written into the plan, committed files, or final report.

- [ ] **Step 2: Verify the preferred Qwen model with the real key**

Run:

```powershell
cd D:\codex\dy_auto_new\server
@'
import os
import httpx

base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
key = os.environ["BAILIAN_KEY_PRIMARY"]
candidate_order = ["qwen3.7-plus", "qwen3.7-max", "qwen3.6-plus", "qwen-plus-latest"]

with httpx.Client(timeout=httpx.Timeout(30, connect=10), trust_env=False) as client:
    models_resp = client.get(
        f"{base_url}/models",
        headers={"Authorization": f"Bearer {key}"},
    )
    print("MODELS_STATUS", models_resp.status_code)
    models_resp.raise_for_status()
    model_ids = {item.get("id") for item in models_resp.json().get("data", [])}
    selected = next((model for model in candidate_order if model in model_ids), "")
    if not selected:
        selected = "qwen3.7-plus"
    chat_resp = client.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "content-type": "application/json"},
        json={
            "model": selected,
            "messages": [{"role": "user", "content": "只回复 OK"}],
            "max_tokens": 8,
            "temperature": 0,
        },
    )
    print("CHAT_STATUS", chat_resp.status_code)
    chat_resp.raise_for_status()
    print("SELECTED_MODEL", selected)
'@ | .\.venv\Scripts\python.exe -
```

Expected: `MODELS_STATUS 200`, `CHAT_STATUS 200`, and `SELECTED_MODEL qwen3.7-plus` unless the key/region does not expose that model. If the selected model is not `qwen3.7-plus`, record the printed selected model in the final report and continue with that verified fallback.

- [ ] **Step 3: Apply dy_auto local env and DB settings**

Run:

```powershell
cd D:\codex\dy_auto_new\server
@'
import os
from pathlib import Path

from app.database import SessionLocal
from app.db_models import AIModel, SystemSetting
from app.services.crypto import encrypt

SERVER_DIR = Path.cwd()
env_path = SERVER_DIR / ".env"
primary = os.environ["BAILIAN_KEY_PRIMARY"]
secondary = os.environ["BAILIAN_KEY_SECONDARY"]
bridge = os.environ["PIXELLE_BRIDGE_KEY"]
selected_model = os.environ.get("QWEN_TEXT_MODEL", "qwen3.7-plus")

def upsert_env(path: Path, updates: dict[str, str]) -> None:
    existing = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                existing[key] = value
    existing.update(updates)
    path.write_text("\n".join(f"{key}={value}" for key, value in existing.items()) + "\n", encoding="utf-8")

def upsert_setting(db, key: str, value: str) -> None:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(SystemSetting(key=key, value=value))

def upsert_model(db, *, name, model_type, provider, base_url, model_name, api_key, config_json, sort_order):
    row = db.query(AIModel).filter(
        AIModel.model_type == model_type,
        AIModel.provider == provider,
        AIModel.model_name == model_name,
    ).first()
    if not row:
        row = AIModel(
            name=name,
            model_type=model_type,
            provider=provider,
            model_name=model_name,
        )
        db.add(row)
    row.name = name
    row.base_url = base_url
    row.api_key = encrypt(api_key)
    row.config_json = config_json
    row.enabled = True
    row.sort_order = sort_order
    return row

upsert_env(env_path, {
    "AI_API_KEY": primary,
    "AI_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode",
    "AI_MODEL": selected_model,
    "AI_PROVIDER": "bailian",
    "AI_THINKING": "disabled",
    "PIXELLE_VIDEO_URL": "http://localhost:8500",
    "PIXELLE_API_KEY": bridge,
    "PIXELLE_CONFIG_PATH": "D:/codex/Pixelle-Video-dy/config.yaml",
    "DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT": "1",
})

db = SessionLocal()
try:
    upsert_setting(db, "llm_api_key", primary)
    upsert_setting(db, "llm_base_url", "https://dashscope.aliyuncs.com/compatible-mode")
    upsert_setting(db, "llm_model", selected_model)
    upsert_setting(db, "llm_thinking", "disabled")
    upsert_setting(db, "pixelle_video_url", "http://localhost:8500")
    upsert_setting(db, "pixelle_api_key", bridge)
    upsert_setting(db, "pixelle_video_timeout", "600")

    upsert_model(
        db,
        name="Bailian Qwen 3.7 Plus",
        model_type="llm",
        provider="bailian",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_name=selected_model,
        api_key=primary,
        sort_order=-100,
        config_json={
            "scene_keys": ["script_generation", "llm_agency_expert_review"],
            "protocol": "openai_chat_completions",
            "max_tokens": 8192,
            "temperature": 0.2,
            "quality_priority": "high",
        },
    )
    upsert_model(
        db,
        name="Bailian Qwen 3.7 Quality Audit",
        model_type="audit",
        provider="bailian",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_name=selected_model,
        api_key=primary,
        sort_order=-100,
        config_json={
            "scene_key": "quality_audit",
            "protocol": "openai_chat_completions",
            "audit_mode": "image_quality_gate",
            "max_tokens": 2048,
            "temperature": 0.1,
        },
    )
    upsert_model(
        db,
        name="Qwen Image 2.0 Pro",
        model_type="image",
        provider="qwen-image",
        base_url="https://dashscope.aliyuncs.com/api/v1",
        model_name="qwen-image-2.0-pro",
        api_key=secondary,
        sort_order=10,
        config_json={
            "scene_key": "image_generation",
            "scene_keys": ["image_generation", "image_editing"],
            "default_size": "1536*2688",
            "default_quality": "standard",
            "protocol": "dashscope_multimodal_generation",
            "task_path": "/services/aigc/multimodal-generation/generation",
            "capabilities": {"text_to_image": True, "text_to_image_set": True},
            "estimated_cost": 0.1,
            "real_paid_allowed": True,
            "supports_external_task_id": True,
            "supports_task_query": True,
            "returns_asset_url": True,
            "returns_usage": True,
            "supports_text_to_image": True,
            "settle_missing_usage_with_estimated_cost": True,
            "max_concurrent_tasks": 1,
        },
    )
    upsert_model(
        db,
        name="Wan 2.7",
        model_type="video",
        provider="wan",
        base_url="https://dashscope.aliyuncs.com/api/v1",
        model_name="wan2.7-i2v",
        api_key=secondary,
        sort_order=10,
        config_json={
            "scene_key": "video_rendering",
            "default_resolution": "720P",
            "default_duration": 5,
            "default_aspect_ratio": "9:16",
            "min_duration_seconds": 2,
            "max_duration_seconds": 15,
            "protocol": "dashscope_async",
            "task_submit_path": "/services/aigc/video-generation/video-synthesis",
            "task_query_path": "/tasks/{task_id}",
            "capabilities": {"image_to_video": True, "first_frame": True, "last_frame": True},
            "estimated_cost": 0.35,
            "real_paid_allowed": True,
            "supports_external_task_id": True,
            "supports_task_query": True,
            "returns_asset_url": True,
            "returns_usage": True,
            "supports_image_to_video": True,
            "settle_missing_usage_with_estimated_cost": True,
            "max_concurrent_tasks": 1,
        },
    )

    db.query(AIModel).filter(AIModel.name.in_(["DeepSeek V3", "GPT-4o", "GPT-4o Audit", "Gemini Audit"])).update(
        {"sort_order": 100},
        synchronize_session=False,
    )
    db.commit()
finally:
    db.close()

print("CONFIG_APPLIED")
'@ | .\.venv\Scripts\python.exe -
```

Expected: prints only `CONFIG_APPLIED`; it must not print secrets.

- [ ] **Step 4: Verify secret hygiene and configured model summary**

Run:

```powershell
cd D:\codex\dy_auto_new
git status --short
cd server
@'
from app.database import SessionLocal
from app.db_models import AIModel, SystemSetting

db = SessionLocal()
try:
    keys = ["llm_api_key", "pixelle_api_key"]
    for key in keys:
        row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        print(key, "SET" if row and row.value else "MISSING")
    for row in db.query(AIModel).filter(AIModel.name.in_([
        "Bailian Qwen 3.7 Plus",
        "Bailian Qwen 3.7 Quality Audit",
        "Qwen Image 2.0 Pro",
        "Wan 2.7",
    ])).order_by(AIModel.model_type, AIModel.name).all():
        print(row.name, row.model_type, row.provider, row.model_name, "KEY" if row.api_key else "NO_KEY", row.sort_order)
finally:
    db.close()
'@ | .\.venv\Scripts\python.exe -
```

Expected:

- `git status --short` does not show `server/.env` or `server/app/data/dy_auto.db`.
- The summary prints `SET`/`KEY` markers but no raw key values.

---

### Task 4: Restart Services and Verify Bridge Health

**Files:**
- No tracked source edits.
- Runtime processes only.

- [ ] **Step 1: Stop existing dy_auto backend/frontend processes for this project**

Run:

```powershell
$ports = 8001,3000
foreach ($port in $ports) {
  $conn = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($conn) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $($conn.OwningProcess)"
    if ($proc.CommandLine -like '*D:\codex\dy_auto_new*') {
      Stop-Process -Id $conn.OwningProcess -Force
    }
  }
}
```

Expected: no output on success.

- [ ] **Step 2: Start Pixelle API with the bridge key**

Run:

```powershell
cd D:\codex\dy_auto_new\server
$bridge = (Select-String -Path .\.env -Pattern '^PIXELLE_API_KEY=').Line.Split('=',2)[1]
$pixelleLog = Join-Path $env:TEMP 'pixelle_video_dy_8500.log'
$pixelleErr = Join-Path $env:TEMP 'pixelle_video_dy_8500.err.log'
Start-Process -FilePath 'cmd.exe' -ArgumentList @('/d','/c',"set PIXELLE_API_KEY=$bridge&&.venv\Scripts\python.exe api\app.py --host 0.0.0.0 --port 8500") -WorkingDirectory 'D:\codex\Pixelle-Video-dy' -RedirectStandardOutput $pixelleLog -RedirectStandardError $pixelleErr -PassThru -WindowStyle Hidden
```

Expected: process starts and `http://localhost:8500/health` returns healthy.

- [ ] **Step 3: Start dy_auto backend and frontend with configured env**

Run:

```powershell
cd D:\codex\dy_auto_new\server
$backendLog = Join-Path $env:TEMP 'dy_auto_backend_8001.log'
$backendErr = Join-Path $env:TEMP 'dy_auto_backend_8001.err.log'
Start-Process -FilePath '.\.venv\Scripts\python.exe' -ArgumentList @('-m','uvicorn','app.main:app','--host','0.0.0.0','--port','8001') -WorkingDirectory 'D:\codex\dy_auto_new\server' -RedirectStandardOutput $backendLog -RedirectStandardError $backendErr -PassThru -WindowStyle Hidden

cd D:\codex\dy_auto_new\web
$frontendLog = Join-Path $env:TEMP 'dy_auto_frontend_3000.log'
$frontendErr = Join-Path $env:TEMP 'dy_auto_frontend_3000.err.log'
Start-Process -FilePath 'cmd.exe' -ArgumentList @('/d','/c','set VITE_API_PROXY_TARGET=http://localhost:8001&&npm run dev -- --host 0.0.0.0') -WorkingDirectory 'D:\codex\dy_auto_new\web' -RedirectStandardOutput $frontendLog -RedirectStandardError $frontendErr -PassThru -WindowStyle Hidden
```

Expected: backend listens on 8001 and frontend listens on 3000.

- [ ] **Step 4: Verify dy_auto, Pixelle, and mock stage bridge**

Run:

```powershell
cd D:\codex\dy_auto_new\server
Invoke-RestMethod http://localhost:8001/health
Invoke-RestMethod http://localhost:8500/health

$login = Invoke-RestMethod -Method Post -Uri 'http://localhost:8001/api/auth/login' -ContentType 'application/json' -Body (@{username='admin'; password='admin123'} | ConvertTo-Json)
$headers = @{ Authorization = "Bearer $($login.token)" }
Invoke-RestMethod -Method Get -Uri 'http://localhost:8001/api/pixelle/test-connection' -Headers $headers
Invoke-RestMethod -Method Get -Uri 'http://localhost:8001/api/system/health' -Headers $headers
```

Expected:

- dy_auto health is `ok`.
- Pixelle health is `healthy`.
- Pixelle test connection has `ok: True`.
- `/api/system/health` worker runtime is `ok`; media readiness may still be blocked if adapter smoke has not succeeded.

---

### Task 5: Bounded Paid Smoke and Completion Evidence

**Files:**
- No tracked source edits unless a provider adapter bug is found.
- Runtime DB and output assets are expected to change.

- [ ] **Step 1: Run a real LLM smoke using qwen3.7-plus**

Run:

```powershell
cd D:\codex\dy_auto_new\server
@'
import asyncio
from app.database import SessionLocal
from app.services.ai_generator import ai_generator

async def main():
    db = SessionLocal()
    try:
        text = await ai_generator.generate_custom(
            db,
            "你是短视频策划专家，只输出一句中文。",
            "为一条关于自律和长期主义的短视频写一句高质量开场白。",
            max_tokens=80,
            temperature=0.3,
            thinking_enabled=False,
        )
        print("LLM_SMOKE_OK", len(text), text[:40])
    finally:
        db.close()

asyncio.run(main())
'@ | .\.venv\Scripts\python.exe -
```

Expected: prints `LLM_SMOKE_OK` with generated Chinese text. It must not print keys.

- [ ] **Step 2: Run the paid one-sentence E2E smoke with real expert gates**

Run:

```powershell
cd D:\codex\dy_auto_new\server
$env:DY_AUTO_ALLOW_REAL_PROVIDER_E2E='1'
$env:DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT='1'
.\.venv\Scripts\python.exe scripts\smoke_bailian_one_sentence_e2e.py --prompt "长期主义如何改变一个普通人的人生轨迹" --title "百炼高质量全流程烟测" --budget 5 --duration 15 --worker-batch-size 1 --max-worker-rounds 80
```

Expected:

- No `expert_gates_bypassed` log.
- An `expert_gates_active` log appears.
- `expert_evidence.expert_involvement_visible` is true.
- Final `completed.ok` is true.
- Final asset fields include `final_asset_id`, `final_storage_path`, and checksum or size evidence.

- [ ] **Step 3: If paid smoke fails on media adapter mismatch, capture exact blocker and implement adapter fix**

When the smoke fails, inspect the final JSON `failed` event and provider error.

If the error mentions unsupported provider `qwen-image` or `wan`, do not mark the goal complete. Add a new follow-up task to implement the missing Pixelle stage adapter in `D:/codex/Pixelle-Video-dy/api/routers/stages.py` or route dy_auto media defaults back to a verified provider while retaining Bailian for LLM/expert/audit. The follow-up task must include:

```powershell
cd D:\codex\Pixelle-Video-dy
.\.venv\Scripts\python.exe -m pytest tests/test_stage_image_create.py tests/test_stage_videos_api.py -q
```

and a rerun of the paid smoke command from Step 2.

- [ ] **Step 4: Verify database evidence after a successful smoke**

Run:

```powershell
cd D:\codex\dy_auto_new\server
@'
from app.database import SessionLocal
from app.db_models import AgencyInvocation, AuditReport, GeneratedVideo, ProductionAuditEvent, VideoProductionAsset, VideoProductionRun

db = SessionLocal()
try:
    run = db.query(VideoProductionRun).order_by(VideoProductionRun.created_at.desc()).first()
    print("RUN", run.id, run.status, run.run_type)
    print("AGENCY_INVOCATIONS", db.query(AgencyInvocation).filter(AgencyInvocation.run_id == run.id).count())
    print("PRODUCTION_AUDIT_EVENTS", db.query(ProductionAuditEvent).filter(ProductionAuditEvent.run_id == run.id).count())
    print("AUDIT_REPORTS", db.query(AuditReport).filter(AuditReport.target_type.in_(["video_asset", "frame", "final_video"])).count())
    final_asset = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == run.id,
        VideoProductionAsset.asset_type == "final_video",
        VideoProductionAsset.is_latest.is_(True),
    ).first()
    print("FINAL_ASSET", bool(final_asset), final_asset.status if final_asset else "", final_asset.storage_path if final_asset else "")
    generated = db.query(GeneratedVideo).filter(GeneratedVideo.pixelle_task_id == run.id).first()
    print("GENERATED_VIDEO", bool(generated), generated.video_path if generated else "")
finally:
    db.close()
'@ | .\.venv\Scripts\python.exe -
```

Expected:

- latest run status is `completed`.
- agency invocation count or production audit event count is greater than zero.
- final asset exists and has a persisted storage path.
- generated video row exists.

- [ ] **Step 5: Run final regression checks**

Run:

```powershell
cd D:\codex\dy_auto_new\server
.\.venv\Scripts\python.exe -m pytest tests/test_runtime_model_config.py tests/test_model_schema.py tests/test_ai_config_scene_schema.py tests/test_bailian_smoke_script_contract.py -q

cd D:\codex\dy_auto_new\web
npm run build
```

Expected:

- pytest exits 0.
- frontend build exits 0.

Commit any tracked source/test changes made after Task 2:

```powershell
cd D:\codex\dy_auto_new
git status --short
git add server/app/services/runtime_model_config.py server/app/data/model_schema_data.py server/app/routers/ai_config.py server/scripts/smoke_bailian_one_sentence_e2e.py server/tests/test_runtime_model_config.py server/tests/test_model_schema.py server/tests/test_ai_config_scene_schema.py server/tests/test_bailian_smoke_script_contract.py
git commit -m "chore: verify bailian high quality pipeline smoke"
```

Do not add `server/.env`, runtime DB files, output media, logs, or provider response payloads with signed URLs.

# Image Production Strategy Control Plane Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not create git commits unless the user explicitly asks; treat commit steps as review checkpoints with `git status` and test evidence.

**Goal:** Add Phase 2 explainability and fallback advice on top of the completed Phase 1 image production strategy control plane.

**Architecture:** Keep `POST /api/image-creation/tasks` as the only image execution path. Extract model selection diagnostics into a focused service used by selection preview and task creation, then expose human-readable rejected-candidate reasons, fallback candidates, rescue actions, and task timeline state in the existing image creation and strategy center UIs.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, Vue 3, Vitest, existing dy_auto API client and Tailwind utility classes.

---

## Source Material

- Design spec: `D:\devWorkspace\jsProjects\dy_auto\docs\superpowers\specs\2026-05-28-image-production-strategy-control-plane-design.md`
- Completed Phase 1 plan: `D:\devWorkspace\jsProjects\dy_auto\docs\superpowers\plans\2026-05-28-image-production-strategy-control-plane-phase1.md`
- Current selection preview service: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_selection_preview_service.py`
- Current image creation service: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_creation_service.py`
- Current image creation UI: `D:\devWorkspace\jsProjects\dy_auto\web\src\views\ImageCreationPage.vue`
- Current strategy center UI: `D:\devWorkspace\jsProjects\dy_auto\web\src\views\ImageProductionStrategiesPage.vue`

## Current State Assumption

Phase 1 is complete and verified:

- Strategy CRUD and immutable strategy versions exist.
- Selection preview persists request hash and basic selected/rejected model explanation.
- Image task creation persists strategy snapshot and selection explanation.
- Approved image asset bridge exists.
- Image creation page has a strategy selector and trust rail.
- Strategy center MVP lists and archives strategies.

This plan does not repeat Phase 1 work.

## Scope

In scope for Phase 2:

- Shared backend model selection diagnostics service.
- Rich rejected-candidate diagnostics from `AIModel.config_json`.
- Fallback candidate suggestions based on strategy `fallback_model_ids_json`.
- Named fallback/rescue error payloads for preview and Pixelle submit failure.
- Persisted `fallback_trace_json` when generation fails after a durable task snapshot.
- Task payload timeline fields for preview, snapshot, queue, generation, review, and blocked states.
- Frontend trust rail diagnostics: selected model, rejected candidates, fallback candidates, warnings, rescue actions.
- Frontend execution timeline on the image creation page.
- Strategy center fallback/default model diagnostics and a minimal fallback editor drawer using named model selectors.

Out of scope for Phase 2:

- Hard capacity leases and queue admission control. That belongs to Phase 3.
- Actual provider cost ledger integration. That belongs to Phase 3.
- A/B group and attempt execution. That belongs to Phase 4.
- Automatic fallback execution without user confirmation.
- Automatic strategy mutation from metrics.

## File Structure

### Backend

- Create `server/app/services/image_model_selection_service.py`
  - Owns candidate diagnostics, selected model decision, fallback candidate derivation, and rescue-action payloads.
- Modify `server/app/services/image_selection_preview_service.py`
  - Reuse `image_model_selection_service.py` instead of local candidate loops.
  - Return richer explanation, fallback candidates, warnings, and rescue actions.
- Modify `server/app/services/image_creation_service.py`
  - Persist richer selection explanation.
  - Populate `fallback_trace_json` when Pixelle submission fails after task insert.
  - Include `timeline` and `fallback_trace` in `task_payload`.
- Modify `server/app/routers/image_production.py`
  - Keep the same selection preview route; only response detail changes.
- Add `server/tests/test_image_model_selection_service.py`
  - Unit coverage for selected model, rejected reasons, and fallback candidates.
- Extend `server/tests/test_image_selection_preview_service.py`
  - Preview response shape and fallback error behavior.
- Extend `server/tests/test_image_creation_strategy_snapshot.py`
  - Persisted explanation and fallback trace on Pixelle failure.

### Frontend

- Modify `web/src/views/ImageCreationPage.vue`
  - Show rejected candidate diagnostics, fallback candidates, warnings, rescue actions, and task timeline.
- Modify `web/src/views/ImageProductionStrategiesPage.vue`
  - Add default model/fallback count columns.
  - Add minimal edit drawer for default model and fallback model selections.
- Modify `web/src/api/imageProduction.js`
  - Add `getImageProductionStrategy` if the edit drawer needs fresh version data.
- Extend `web/src/__tests__/image-creation-page.test.js`
  - Trust rail rejected candidates, fallback candidates, rescue actions, and timeline.
- Extend `web/src/__tests__/image-production-strategy-page.test.js`
  - Default model/fallback count and edit drawer update payload.

## Design Review Addendum

These design requirements are binding for Tasks 4 and 5 and override any lower-level snippet that conflicts with them.

### Image Creation Trust Rail

- Use a summary-first trust rail: selected model, cost estimate, preview status, and strategy/version should be visible without expanding diagnostics.
- Show fallback-required as a single warning band with one primary action: `Use fallback model`. Do not present fallback as a passive text tag.
- Keep rejected candidates and raw selection JSON inside collapsed diagnostics. Operators should not see a wall of technical reasons before the actionable status.
- The disabled create state must explain why it is disabled when fallback confirmation is required. Use the existing error/help text area rather than relying only on button opacity.
- Use semantic status labels in UI: `可提交`, `需确认 fallback`, `预览失败`, `已生成`, `待审查`, `已阻断`. Do not expose raw backend status strings as primary text.

### Production Timeline

- Render the timeline as an ordered stepper, not a loose list. Steps: preview, snapshot, queue, generation, review gate, approval gate.
- Each step needs a stable icon/dot, a localized label, and a semantic status label. The active step should use `aria-current="step"`.
- On mobile, the timeline becomes a vertical list. On desktop, it can stay compact inside the right rail.
- Failure state should surface the next action near the failed step, especially retry with fallback when `fallback_trace.rescue_actions` exists.

### Strategy Center Fallback Editor

- Do not ask users to type raw model identifiers. Use a named default-model select and a named multi-select or checkbox list for fallback models.
- Show selected fallback models as model names with provider/model identifier secondary text.
- Preserve version conflict visibility: when save fails with a version conflict, keep the editor open and show the normalized error above the editor controls.
- On mobile, the strategy table should become stacked strategy rows with visible labels instead of keeping a fixed six-column grid.
- Minimum touch target for editor buttons and fallback actions is 44px high.

### Accessibility And Empty States

- The trust rail and task panel already use `aria-live`; new warning, fallback, and timeline state changes must stay within those live regions.
- Every icon-only or terse action needs visible text or an `aria-label`.
- Empty fallback state should say that no configured fallback model supports this request and link the operator back to model/strategy configuration.
- Color cannot be the only indicator of state; every status chip must include text.

---

### Task 1: Add Backend Model Selection Diagnostics Service

**Files:**
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_model_selection_service.py`
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_model_selection_service.py`

- [ ] **Step 1: Write failing tests for selected model and rejected reasons**

Create `server/tests/test_image_model_selection_service.py`:

```python
from app.db_models import AIModel
from app.services.crypto import encrypt
from app.services.image_model_selection_service import resolve_image_model_selection


def _model(db, *, name, model_name, scene_key, capabilities, enabled=True, sort_order=0):
    row = AIModel(
        name=name,
        provider="seedance",
        model_type="image",
        model_name=model_name,
        enabled=enabled,
        sort_order=sort_order,
        base_url="https://example.invalid",
        api_key=encrypt("secret-key"),
        config_json={
            "config_version": 1,
            "scene_key": scene_key,
            "scene_keys": [scene_key],
            "capabilities": capabilities,
            "provider_options_schema": {"watermark": {"type": "boolean"}},
        },
    )
    db.add(row)
    db.commit()
    return row


def test_selection_diagnostics_selects_first_supported_model(db):
    unsupported = _model(
        db,
        name="Text Only",
        model_name="text-only",
        scene_key="image_generation",
        capabilities={"text_to_image": True},
        sort_order=1,
    )
    supported = _model(
        db,
        name="Image Edit",
        model_name="image-edit",
        scene_key="image_editing",
        capabilities={"image_to_image": True},
        sort_order=2,
    )

    result = resolve_image_model_selection(
        db,
        scene_key="image_editing",
        capability_key="image_to_image",
        requested_model_id=None,
        strategy=None,
    )

    assert result["selected_model"]["model_id"] == supported.id
    assert result["selected_reason"] == "first_supported_model"
    assert result["rejected_candidates"] == [
        {
            "model_id": unsupported.id,
            "name": "Text Only",
            "provider": "seedance",
            "model_name": "text-only",
            "reason": "capability_not_supported",
            "detail": "Model does not support image_editing.image_to_image.",
            "rescue_action": "Choose another model or update model capabilities.",
        }
    ]


def test_selection_diagnostics_rejects_disabled_and_non_preferred_models(db):
    requested = _model(
        db,
        name="Requested",
        model_name="requested",
        scene_key="image_generation",
        capabilities={"text_to_image": True},
        sort_order=1,
    )
    _model(
        db,
        name="Disabled",
        model_name="disabled",
        scene_key="image_generation",
        capabilities={"text_to_image": True},
        enabled=False,
        sort_order=0,
    )
    other = _model(
        db,
        name="Other",
        model_name="other",
        scene_key="image_generation",
        capabilities={"text_to_image": True},
        sort_order=2,
    )

    result = resolve_image_model_selection(
        db,
        scene_key="image_generation",
        capability_key="text_to_image",
        requested_model_id=requested.id,
        strategy=None,
    )

    assert result["selected_model"]["model_id"] == requested.id
    assert result["selected_reason"] == "requested_model"
    assert {
        "model_id": other.id,
        "name": "Other",
        "provider": "seedance",
        "model_name": "other",
        "reason": "not_preferred_model",
        "detail": "A requested or strategy default model was specified.",
        "rescue_action": "Clear the manual model override to allow automatic selection.",
    } in result["rejected_candidates"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_model_selection_service.py -v
```

Expected: FAIL because `app.services.image_model_selection_service` does not exist.

- [ ] **Step 3: Implement the diagnostics service**

Create `server/app/services/image_model_selection_service.py`:

```python
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db_models import AIModel, ImageProductionStrategy
from app.services.runtime_model_config import _model_supports_capability


def _model_payload(model: AIModel, scene_key: str, capability_key: str) -> dict[str, Any]:
    config = model.config_json or {}
    return {
        "model_id": model.id,
        "name": model.name,
        "provider": model.provider,
        "model_name": model.model_name,
        "scene_key": scene_key,
        "capability_key": capability_key,
        "config_version": config.get("config_version", 1),
    }


def _reject(model: AIModel, reason: str, detail: str, rescue_action: str) -> dict[str, Any]:
    return {
        "model_id": model.id,
        "name": model.name,
        "provider": model.provider,
        "model_name": model.model_name,
        "reason": reason,
        "detail": detail,
        "rescue_action": rescue_action,
    }


def _fallback_candidate(model: AIModel, scene_key: str, capability_key: str) -> dict[str, Any]:
    return {
        **_model_payload(model, scene_key, capability_key),
        "risk_labels": ["requires_manual_confirmation"],
        "confirmation_required": True,
        "rescue_action": "Confirm fallback model before creating a new task.",
    }


def resolve_image_model_selection(
    db: Session,
    *,
    scene_key: str,
    capability_key: str,
    requested_model_id: str | None,
    strategy: ImageProductionStrategy | None,
) -> dict[str, Any]:
    models = (
        db.query(AIModel)
        .filter(AIModel.model_type == "image")
        .order_by(AIModel.sort_order.asc(), AIModel.created_at.asc())
        .all()
    )
    preferred_model_id = requested_model_id or (strategy.default_model_id if strategy else None)
    fallback_model_ids = list(strategy.fallback_model_ids_json or []) if strategy else []
    selected: AIModel | None = None
    rejected: list[dict[str, Any]] = []
    fallback_candidates: list[dict[str, Any]] = []

    support_by_model_id: dict[str, bool] = {}
    for model in models:
        supports_capability = bool(model.enabled) and _model_supports_capability(model, scene_key, capability_key)
        support_by_model_id[model.id] = supports_capability
        if model.id in fallback_model_ids and supports_capability:
            fallback_candidates.append(_fallback_candidate(model, scene_key, capability_key))

    for model in models:
        if not model.enabled:
            rejected.append(_reject(
                model,
                "model_disabled",
                "Model is disabled in the model center.",
                "Enable the model or choose another model.",
            ))
            continue

        if preferred_model_id and model.id != preferred_model_id:
            rejected.append(_reject(
                model,
                "not_preferred_model",
                "A requested or strategy default model was specified.",
                "Clear the manual model override to allow automatic selection.",
            ))
            continue

        if not support_by_model_id.get(model.id):
            rejected.append(_reject(
                model,
                "capability_not_supported",
                f"Model does not support {scene_key}.{capability_key}.",
                "Choose another model or update model capabilities.",
            ))
            continue

        selected = model
        break

    selected_reason = None
    if selected:
        selected_reason = "requested_model" if requested_model_id else "first_supported_model"
        if strategy and strategy.default_model_id == selected.id and not requested_model_id:
            selected_reason = "strategy_default_model"

    return {
        "selected_model": _model_payload(selected, scene_key, capability_key) if selected else None,
        "selected_reason": selected_reason,
        "candidate_count": len(models),
        "rejected_candidates": rejected,
        "fallback_candidates": fallback_candidates,
        "warnings": [],
        "rescue_actions": [],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_model_selection_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Review checkpoint**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git status --short server/app/services/image_model_selection_service.py server/tests/test_image_model_selection_service.py
```

Expected: only the new service and test file are shown for this task.

---

### Task 2: Use Diagnostics In Selection Preview And Add Fallback Error Payloads

**Files:**
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_selection_preview_service.py`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_selection_preview_service.py`

- [ ] **Step 1: Add failing preview tests for fallback candidates**

Append to `server/tests/test_image_selection_preview_service.py`:

```python
def test_selection_preview_returns_fallback_candidates_from_strategy(db):
    primary = _seed_image_model(
        db,
        name="Primary Text",
        scene_key="image_generation",
        capabilities={"text_to_image": True},
    )
    fallback = _seed_image_model(
        db,
        name="Fallback Edit",
        scene_key="image_editing",
        capabilities={"image_to_image": True},
    )
    strategy = _strategy(
        db,
        default_model_id=primary.id,
        fallback_model_ids=[fallback.id],
        supported_modes=["image_to_image"],
    )

    result = create_selection_preview(
        db,
        {
            "mode": "image_to_image",
            "destination_role": "image_to_video_input",
            "strategy_id": strategy.id,
            "strategy_version": strategy.version,
            "source": {"url": "https://cdn.example/source.png"},
            "provider_options": {},
            "count": 1,
        },
    )

    assert result["selected_model"] is None
    assert result["error_code"] == "IMAGE_FALLBACK_REQUIRES_CONFIRMATION"
    assert result["preview_blocked"] is True
    assert result["confirmation_required"] is True
    assert result["fallback_candidates"][0]["model_id"] == fallback.id
    assert result["rescue_actions"] == [
        {
            "type": "confirm_fallback_model",
            "label": "Use fallback model",
            "model_id": fallback.id,
        }
    ]
```

- [ ] **Step 2: Run the new test to verify it fails**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_selection_preview_service.py::test_selection_preview_returns_fallback_candidates_from_strategy -v
```

Expected: FAIL because preview does not yet return fallback candidates or fallback confirmation payloads.

- [ ] **Step 3: Replace local model loop with diagnostics service**

Modify `server/app/services/image_selection_preview_service.py`:

```python
from app.services.image_model_selection_service import resolve_image_model_selection
```

Inside `create_selection_preview`, replace the local `models`, `preferred_model_id`, `selected`, and `rejected` loop with:

```python
    selection = resolve_image_model_selection(
        db,
        scene_key=scene_key,
        capability_key=capability_key,
        requested_model_id=payload.get("model_id"),
        strategy=strategy,
    )
    selected_model = selection["selected_model"]
    fallback_candidates = selection["fallback_candidates"]

    if not selected_model and fallback_candidates:
        response = {
            "ok": False,
            "preview_blocked": True,
            "confirmation_required": True,
            "error_code": "IMAGE_FALLBACK_REQUIRES_CONFIRMATION",
            "message": "Primary model cannot satisfy this request, but fallback models are available.",
            "selected_model": None,
            "strategy": strategy_payload(strategy) if strategy else None,
            "selection_explanation": {
                "requested_mode": mode,
                "destination_role": payload.get("destination_role"),
                "strategy_id": strategy.id if strategy else None,
                "strategy_version": strategy.version if strategy else None,
                "candidate_count": selection["candidate_count"],
                "rejected_candidates": selection["rejected_candidates"],
                "selected_model_id": None,
                "selected_reason": None,
            },
            "cost_estimate": _cost_estimate(payload),
            "request_hash": None,
            "selection_preview_id": None,
            "expires_at": None,
            "warnings": ["fallback_requires_confirmation"],
            "fallback_candidates": fallback_candidates,
            "rescue_actions": [
                {
                    "type": "confirm_fallback_model",
                    "label": "Use fallback model",
                    "model_id": fallback_candidates[0]["model_id"],
                }
            ],
        }
        return response

    if not selected_model:
        raise image_error(
            422,
            "IMAGE_MODEL_SELECTION_EMPTY",
            "No enabled model supports this image request.",
            "Configure a compatible image model.",
            "/ai-config",
            retryable=False,
        )
```

Then convert the selected payload to an `AIModel` row for provider option validation:

```python
    selected = db.query(AIModel).filter(AIModel.id == selected_model["model_id"]).first()
```

Build explanation from `selection`:

```python
    explanation = {
        "requested_mode": mode,
        "destination_role": payload.get("destination_role"),
        "strategy_id": strategy.id if strategy else None,
        "strategy_version": strategy.version if strategy else None,
        "candidate_count": selection["candidate_count"],
        "rejected_candidates": selection["rejected_candidates"],
        "selected_model_id": selected.id,
        "selected_reason": selection["selected_reason"],
        "fallback_candidates": selection["fallback_candidates"],
    }
```

Add these top-level fields to the normal response:

```python
        "preview_blocked": False,
        "confirmation_required": False,
        "fallback_candidates": selection["fallback_candidates"],
        "rescue_actions": [],
```

Do not persist an `ImageSelectionPreview` row for the blocked fallback response because there is no selected model or request hash yet. The user must explicitly choose a fallback model, rerun preview, and then create the task with a normal persisted preview.

- [ ] **Step 4: Run preview tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_model_selection_service.py tests/test_image_selection_preview_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Review checkpoint**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git status --short server/app/services/image_selection_preview_service.py server/app/services/image_model_selection_service.py server/tests/test_image_selection_preview_service.py server/tests/test_image_model_selection_service.py
```

Expected: only Phase 2 backend diagnostics files are shown for this checkpoint.

---

### Task 3: Persist Fallback Trace On Pixelle Submit Failure And Add Task Timeline

**Files:**
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_creation_service.py`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_creation_strategy_snapshot.py`

- [ ] **Step 1: Add failing test for Pixelle submit failure fallback trace**

Append to `server/tests/test_image_creation_strategy_snapshot.py`:

```python
def test_create_image_task_records_fallback_trace_when_pixelle_submit_fails(db, monkeypatch):
    model = _seed_model(db)
    fallback = _seed_model(db, name_prefix="fallback-model")
    strategy = _strategy(db, model)
    strategy.fallback_model_ids_json = [fallback.id]
    db.commit()

    async def fail_submit(**kwargs):
        assert kwargs["model_config"]["model_id"] == model.id
        raise RuntimeError("Authorization: Bearer ark-123 api_key=secret pixelle unavailable")

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fail_submit)

    resp = client.post(
        "/api/image-creation/tasks",
        json={
            "mode": "text_to_image",
            "prompt": "fallback trace",
            "strategy_id": strategy.id,
            "strategy_version": strategy.version,
            "provider_options": {"watermark": True},
            "cost_confirmation": True,
            "idempotency_key": "fallback-trace-1",
        },
    )

    assert resp.status_code == 502
    assert resp.json()["detail"]["error_code"] == "PIXELLE_IMAGE_SUBMIT_FAILED"
    task = db.query(ImageCreationTask).filter_by(idempotency_key="fallback-trace-1").one()
    assert task.status == "failed"
    assert task.fallback_trace_json["error_code"] == "PIXELLE_IMAGE_SUBMIT_FAILED"
    assert task.fallback_trace_json["fallback_candidates"][0]["model_id"] == fallback.id
    assert task.fallback_trace_json["rescue_actions"][0]["type"] == "retry_with_fallback_model"
    trace_text = str(task.fallback_trace_json)
    assert "ark-123" not in trace_text
    assert "Authorization" not in trace_text
    assert "api_key" not in trace_text
```

- [ ] **Step 2: Add failing test for task timeline payload**

Append to `server/tests/test_image_creation_strategy_snapshot.py`:

```python
def test_task_payload_includes_production_timeline(db, monkeypatch):
    model = _seed_model(db)
    strategy = _strategy(db, model)

    async def fake_submit(**kwargs):
        assert kwargs["model_config"]["model_id"] == model.id
        return {"ok": True, "stage_task_id": "timeline-stage-task"}

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post(
        "/api/image-creation/tasks",
        json={
            "mode": "text_to_image",
            "prompt": "timeline",
            "strategy_id": strategy.id,
            "strategy_version": strategy.version,
            "provider_options": {"watermark": True},
            "cost_confirmation": True,
            "idempotency_key": "timeline-1",
        },
    )

    assert resp.status_code == 200
    timeline = resp.json()["task"]["timeline"]
    assert [step["key"] for step in timeline] == ["preview", "snapshot", "queue", "generation", "review", "approval"]
    assert timeline[1]["status"] == "completed"
    assert timeline[3]["status"] in {"queued", "running"}
```

- [ ] **Step 3: Run the new tests to verify they fail**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_creation_strategy_snapshot.py::test_create_image_task_records_fallback_trace_when_pixelle_submit_fails tests/test_image_creation_strategy_snapshot.py::test_task_payload_includes_production_timeline -v
```

Expected: FAIL because fallback trace and timeline are not implemented.

- [ ] **Step 4: Implement fallback trace helper**

Modify `server/app/services/image_creation_service.py`. Add imports:

```python
import re

from app.services.image_model_selection_service import resolve_image_model_selection
```

Add helpers near `_estimate_cost`:

```python
_SECRET_ERROR_PATTERNS = [
    re.compile(r"ark-[0-9A-Za-z-]+"),
    re.compile(r"Authorization\s*:\s*Bearer\s+\S+", re.IGNORECASE),
    re.compile(r"(api[_-]?key\s*[=:]\s*)\S+", re.IGNORECASE),
]


def _redact_provider_error(value: object) -> str:
    message = str(value or "Provider request failed.")
    for pattern in _SECRET_ERROR_PATTERNS:
        message = pattern.sub(lambda match: f"{match.group(1)}[redacted]" if match.lastindex else "[redacted]", message)
    return message[:500]


def _fallback_trace(
    db: Session,
    *,
    strategy: ImageProductionStrategy | None,
    scene_key: str,
    capability_key: str,
    error_code: str,
    message: str,
) -> dict[str, Any]:
    safe_message = _redact_provider_error(message)
    if not strategy:
        return {
            "error_code": error_code,
            "message": safe_message,
            "fallback_candidates": [],
            "rescue_actions": [],
        }
    selection = resolve_image_model_selection(
        db,
        scene_key=scene_key,
        capability_key=capability_key,
        requested_model_id=None,
        strategy=strategy,
    )
    fallback_candidates = selection.get("fallback_candidates") or []
    return {
        "error_code": error_code,
        "message": safe_message,
        "fallback_candidates": fallback_candidates,
        "rescue_actions": [
            {
                "type": "retry_with_fallback_model",
                "label": "Retry with fallback model",
                "model_id": fallback_candidates[0]["model_id"],
            }
        ] if fallback_candidates else [],
    }
```

- [ ] **Step 5: Wrap the existing Pixelle submit branch after the durable task commit**

Keep the existing `db.commit()` before Pixelle submission. In the existing `submit_image_create` `try/except` block, preserve the current call signature and replace only the failure handling:

```python
    try:
        result = await submit_image_create(db=db, model_config=model_config, **pixelle_payload)
    except Exception as exc:
        safe_message = _redact_provider_error(exc)
        task.status = "failed"
        task.error_code = "PIXELLE_IMAGE_SUBMIT_FAILED"
        task.error_message = safe_message
        task.repair_action = "Open the task and retry with the suggested fallback model."
        task.fallback_trace_json = _fallback_trace(
            db,
            strategy=strategy,
            scene_key=scene_key,
            capability_key=capability_key,
            error_code="PIXELLE_IMAGE_SUBMIT_FAILED",
            message=safe_message,
        )
        db.commit()
        raise image_error(
            502,
            "PIXELLE_IMAGE_SUBMIT_FAILED",
            "Pixelle image submission failed after the task snapshot was saved.",
            "Open the task and retry with the suggested fallback model.",
            retryable=True,
            affected_ids=[task.id],
        ) from exc
```

Keep the existing successful submit update logic after this block.

- [ ] **Step 6: Add timeline helper and payload fields**

Add helper near `task_payload`:

```python
def _task_timeline(task: ImageCreationTask) -> list[dict[str, Any]]:
    has_preview = bool(task.selection_preview_id)
    has_snapshot = bool(task.strategy_snapshot_json or task.request_json)
    status = task.status or "queued"
    generation_status = "failed" if status == "failed" else ("completed" if status == "completed" else status)
    review_status = "blocked" if status in {"failed", "rejected", "blocked"} else "pending"
    approval_status = "blocked" if status in {"failed", "rejected", "blocked"} else "pending"
    return [
        {"key": "preview", "label": "Selection preview", "status": "completed" if has_preview else "skipped"},
        {"key": "snapshot", "label": "Task snapshot", "status": "completed" if has_snapshot else "pending"},
        {"key": "queue", "label": "Queue", "status": "completed" if task.external_task_id else "pending"},
        {"key": "generation", "label": "Generation", "status": generation_status},
        {"key": "review", "label": "Review gate", "status": review_status},
        {"key": "approval", "label": "Approval gate", "status": approval_status},
    ]
```

In `task_payload`, add:

```python
        "fallback_trace": task.fallback_trace_json or {},
        "timeline": _task_timeline(task),
```

Phase 2 timeline is task-level only. Do not infer asset-level review completion here; asset review and approval accuracy belongs to the later review backlog work.

- [ ] **Step 7: Run backend snapshot tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_creation_strategy_snapshot.py -v
```

Expected: PASS.

- [ ] **Step 8: Run related backend tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_model_selection_service.py tests/test_image_selection_preview_service.py tests/test_image_creation_strategy_snapshot.py tests/test_image_creation_mocked_e2e.py -v
```

Expected: PASS.

---

### Task 4: Show Trust Rail Diagnostics And Timeline In Image Creation Page

**Files:**
- Modify: `D:\devWorkspace\jsProjects\dy_auto\web\src\views\ImageCreationPage.vue`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\web\src\__tests__\image-creation-page.test.js`

- [ ] **Step 1: Add failing frontend test for diagnostics and fallback candidates**

Append to `web/src/__tests__/image-creation-page.test.js`:

```javascript
it('shows rejected candidates, blocks submit, and confirms a fallback model', async () => {
  mocks.listModels.mockResolvedValue({
    data: {
      models: [
        { id: 'model-primary', name: 'Primary Model', model_type: 'image' },
        { id: 'model-fallback', name: 'Fallback Model', model_type: 'image' },
      ],
    },
  })
  mocks.previewImageSelection.mockResolvedValueOnce({
    data: {
      ok: false,
      preview_blocked: true,
      confirmation_required: true,
      error_code: 'IMAGE_FALLBACK_REQUIRES_CONFIRMATION',
      selected_model: null,
      selection_explanation: {
        selected_reason: null,
        rejected_candidates: [{
          model_id: 'model-primary',
          name: 'Primary Model',
          reason: 'capability_not_supported',
          detail: 'Model does not support image_editing.image_to_image.',
          rescue_action: 'Choose another model or update model capabilities.',
        }],
      },
      fallback_candidates: [{
        model_id: 'model-fallback',
        name: 'Fallback Model',
        risk_labels: ['requires_manual_confirmation'],
      }],
      cost_estimate: { amount: 1, currency: 'CNY' },
      warnings: ['fallback_requires_confirmation'],
      rescue_actions: [{
        type: 'confirm_fallback_model',
        label: 'Use fallback model',
        model_id: 'model-fallback',
      }],
    },
  })
  mocks.previewImageSelection.mockResolvedValueOnce({
    data: {
      ok: true,
      preview_blocked: false,
      confirmation_required: false,
      selected_model: { model_id: 'model-fallback', name: 'Fallback Model' },
      selection_explanation: { selected_reason: 'requested_model', rejected_candidates: [] },
      cost_estimate: { amount: 1, currency: 'CNY' },
      selection_preview_id: 'preview-fallback',
      request_hash: 'hash-fallback',
      fallback_candidates: [],
      rescue_actions: [],
    },
  })
  const wrapper = await mountPage()

  await wrapper.get('[data-testid="image-prompt"]').setValue('需要 fallback 的画面')
  await wrapper.get('[data-testid="selection-preview-button"]').trigger('click')
  await flushPromises()

  expect(wrapper.get('[data-testid="image-trust-rail"]').text()).toContain('Primary Model')
  expect(wrapper.get('[data-testid="image-trust-rail"]').text()).toContain('capability_not_supported')
  expect(wrapper.get('[data-testid="image-trust-rail"]').text()).toContain('Fallback Model')
  expect(wrapper.get('[data-testid="image-trust-rail"]').text()).toContain('Use fallback model')
  expect(wrapper.get('[data-testid="image-create-submit"]').attributes('disabled')).toBeDefined()
  expect(wrapper.get('[data-testid="image-create-disabled-reason"]').text()).toContain('fallback')

  await wrapper.get('[data-testid="confirm-fallback-model-model-fallback"]').trigger('click')
  await flushPromises()

  expect(mocks.previewImageSelection).toHaveBeenLastCalledWith(expect.objectContaining({
    model_id: 'model-fallback',
  }))
  expect(wrapper.get('[data-testid="image-create-submit"]').attributes('disabled')).toBeUndefined()
})
```

- [ ] **Step 2: Add failing frontend test for task timeline**

Append to `web/src/__tests__/image-creation-page.test.js`:

```javascript
it('renders the production timeline returned by the task payload', async () => {
  mocks.createImageTask.mockResolvedValue({
    data: {
      task: {
        id: 'task-timeline',
        status: 'queued',
        timeline: [
          { key: 'preview', label: 'Selection preview', status: 'completed' },
          { key: 'snapshot', label: 'Task snapshot', status: 'completed' },
          { key: 'queue', label: 'Queue', status: 'queued' },
          { key: 'generation', label: 'Generation', status: 'queued' },
          { key: 'review', label: 'Review gate', status: 'pending' },
          { key: 'approval', label: 'Approval gate', status: 'pending' },
        ],
      },
      assets: [],
    },
  })
  const wrapper = await mountPage()

  await wrapper.get('[data-testid="image-prompt"]').setValue('时间线画面')
  await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
  await flushPromises()

  expect(wrapper.get('[data-testid="image-production-timeline"]').text()).toContain('Selection preview')
  expect(wrapper.get('[data-testid="image-production-timeline"]').text()).toContain('Task snapshot')
  expect(wrapper.get('[data-testid="image-production-timeline"]').text()).toContain('Approval gate')
  expect(wrapper.get('[data-testid="image-production-timeline"]').text()).toContain('排队中')
  expect(wrapper.get('[data-testid="image-production-timeline-step-queue"]').attributes('aria-current')).toBe('step')
})
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm exec vitest -- --run src/__tests__/image-creation-page.test.js
```

Expected: FAIL because rejected diagnostics, fallback candidates, rescue actions, and timeline markup are not rendered.

- [ ] **Step 4: Add trust rail diagnostic markup**

Modify `web/src/views/ImageCreationPage.vue` inside `image-trust-rail`, after the selected model block:

```html
<div v-if="selectionPreview?.selection_explanation?.rejected_candidates?.length">
  <p class="text-slate-400">被排除模型</p>
  <div class="mt-2 space-y-2">
    <div
      v-for="candidate in selectionPreview.selection_explanation.rejected_candidates"
      :key="candidate.model_id"
      class="border border-slate-800 bg-slate-900/60 p-2"
    >
      <p class="text-slate-100">{{ candidate.name || candidate.model_id }}</p>
      <p class="mt-1 font-mono text-xs text-amber-300">{{ candidate.reason }}</p>
      <p class="mt-1 text-xs text-slate-400">{{ candidate.detail }}</p>
      <p class="mt-1 text-xs text-sky-300">{{ candidate.rescue_action }}</p>
    </div>
  </div>
</div>

<div v-if="selectionPreview?.fallback_candidates?.length">
  <p class="text-slate-400">可选 fallback</p>
  <div class="mt-2 space-y-2">
    <div
      v-for="candidate in selectionPreview.fallback_candidates"
      :key="candidate.model_id"
      class="border border-amber-500/30 bg-amber-950/20 p-2"
    >
      <p class="text-slate-100">{{ candidate.name || candidate.model_id }}</p>
      <p class="mt-1 text-xs text-amber-300">{{ (candidate.risk_labels || []).join(' / ') }}</p>
    </div>
  </div>
</div>

<div v-if="selectionPreview?.rescue_actions?.length">
  <p class="text-slate-400">补救动作</p>
  <div class="mt-2 flex flex-wrap gap-2">
    <button
      v-for="action in selectionPreview.rescue_actions"
      :key="`${action.type}-${action.model_id || action.label}`"
      type="button"
      :data-testid="action.type === 'confirm_fallback_model' ? `confirm-fallback-model-${action.model_id}` : `rescue-action-${action.type}`"
      class="border border-sky-500/40 px-2 py-1 text-xs text-sky-200 hover:bg-sky-950/40"
      @click="handleRescueAction(action)"
    >
      {{ action.label }}
    </button>
  </div>
</div>
```

- [ ] **Step 5: Block task creation until fallback is confirmed**

Update `canSubmit` and add rescue helpers in the script section:

```javascript
const previewBlocked = computed(() => Boolean(
  selectionPreview.value?.preview_blocked
    || selectionPreview.value?.error_code === 'IMAGE_FALLBACK_REQUIRES_CONFIRMATION',
))

const canSubmit = computed(() => Boolean(form.prompt.trim())
  && !sourceError.value
  && !referenceError.value
  && !countError.value
  && !previewBlocked.value)

const createDisabledReason = computed(() => {
  if (!form.prompt.trim()) return '请先填写提示词。'
  if (sourceError.value) return sourceError.value
  if (referenceError.value) return referenceError.value
  if (countError.value) return countError.value
  if (previewBlocked.value) return '当前预览需要先确认 fallback 模型后才能创建任务。'
  return ''
})

async function handleRescueAction(action) {
  if (action.type !== 'confirm_fallback_model' || !action.model_id) return
  form.modelId = action.model_id
  resetSelectionPreview()
  await runSelectionPreview()
}
```

Render `createDisabledReason` near the create button or trust rail when it is non-empty, so the operator knows why creation is blocked:

```html
<p
  v-if="createDisabledReason"
  data-testid="image-create-disabled-reason"
  class="mt-2 text-xs text-amber-300"
>
  {{ createDisabledReason }}
</p>
```

- [ ] **Step 6: Add timeline markup**

Inside the task panel, after the current task status block, add:

```html
<div
  v-if="task?.timeline?.length"
  data-testid="image-production-timeline"
  class="border border-slate-800 bg-slate-900/60 p-3"
  role="list"
  aria-label="生产步骤"
>
  <div class="text-xs text-slate-500">生产步骤</div>
  <div class="mt-3 space-y-2 md:space-y-1">
    <div
      v-for="(step, index) in task.timeline"
      :key="step.key"
      :data-testid="`image-production-timeline-step-${step.key}`"
      class="flex min-h-11 items-center justify-between gap-3 text-sm"
      role="listitem"
      :aria-current="isCurrentTimelineStep(step, index) ? 'step' : null"
    >
      <span class="flex items-center gap-2 text-slate-200">
        <span class="h-2 w-2 rounded-full border border-slate-500" :class="timelineDotClass(step.status)" aria-hidden="true"></span>
        {{ step.label }}
      </span>
      <span class="border px-2 py-1 text-xs" :class="timelineStatusClass(step.status)">
        {{ timelineStatusLabel(step.status) }}
      </span>
    </div>
  </div>
</div>
```

Add script helper:

```javascript
const timelineStatusLabels = {
  completed: '已完成',
  failed: '失败',
  blocked: '已阻断',
  queued: '排队中',
  running: '生成中',
  pending: '待处理',
  skipped: '已跳过',
}

function timelineStatusLabel(status) {
  return timelineStatusLabels[status] || status || '未知'
}

function isCurrentTimelineStep(step, index) {
  const activeIndex = (task.value?.timeline || []).findIndex(item =>
    ['queued', 'running', 'blocked', 'failed'].includes(item.status))
  return activeIndex === index && ['queued', 'running', 'blocked', 'failed'].includes(step.status)
}

function timelineStatusClass(status) {
  if (status === 'completed') return 'border-emerald-500/40 text-emerald-300'
  if (status === 'failed' || status === 'blocked') return 'border-rose-500/40 text-rose-300'
  if (status === 'queued' || status === 'running') return 'border-sky-500/40 text-sky-300'
  return 'border-slate-700 text-slate-400'
}

function timelineDotClass(status) {
  if (status === 'completed') return 'bg-emerald-400 border-emerald-400'
  if (status === 'failed' || status === 'blocked') return 'bg-rose-400 border-rose-400'
  if (status === 'queued' || status === 'running') return 'bg-sky-400 border-sky-400'
  return 'bg-slate-700'
}
```

- [ ] **Step 7: Run frontend tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm exec vitest -- --run src/__tests__/image-creation-page.test.js src/__tests__/image-creation-a11y.test.js
```

Expected: PASS.

---

### Task 5: Add Strategy Center Fallback Configuration MVP

**Files:**
- Modify: `D:\devWorkspace\jsProjects\dy_auto\web\src\api\imageProduction.js`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\web\src\views\ImageProductionStrategiesPage.vue`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\web\src\__tests__\image-production-strategy-page.test.js`

- [ ] **Step 1: Add failing API wrapper test through page behavior**

Replace `web/src/__tests__/image-production-strategy-page.test.js` with this structure; do not append a second `vi.mock('../api/imageProduction.js')` block below the current one.

```javascript
import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const pageMocks = vi.hoisted(() => ({
  listImageProductionStrategies: vi.fn(),
  archiveImageProductionStrategy: vi.fn(),
  updateImageProductionStrategy: vi.fn(),
  listModels: vi.fn(),
}))

vi.mock('../api/imageProduction.js', () => ({
  listImageProductionStrategies: pageMocks.listImageProductionStrategies,
  archiveImageProductionStrategy: pageMocks.archiveImageProductionStrategy,
  updateImageProductionStrategy: pageMocks.updateImageProductionStrategy,
}))

vi.mock('../api/aiConfig.js', () => ({
  listModels: pageMocks.listModels,
}))

import Page from '../views/ImageProductionStrategiesPage.vue'

describe('ImageProductionStrategiesPage', () => {
beforeEach(() => {
  vi.clearAllMocks()
  pageMocks.listImageProductionStrategies.mockResolvedValue({
    data: {
      strategies: [{
        id: 'strategy-1',
        name: 'Default Image To Video Input',
        destination_role: 'image_to_video_input',
        status: 'active',
        version: 1,
        default_model_id: null,
        fallback_model_ids: [],
      }],
    },
  })
  pageMocks.archiveImageProductionStrategy.mockResolvedValue({ data: { ok: true } })
  pageMocks.updateImageProductionStrategy.mockResolvedValue({ data: { ok: true } })
  pageMocks.listModels.mockResolvedValue({ data: { models: [] } })
})

it('renders strategy table and archive action', async () => {
  const wrapper = mount(Page)
  await flushPromises()

  expect(pageMocks.listImageProductionStrategies).toHaveBeenCalledWith({})
  expect(wrapper.text()).toContain('鍥惧儚绛栫暐涓績')
  expect(wrapper.text()).toContain('Default Image To Video Input')

  await wrapper.get('[data-testid="archive-strategy-strategy-1"]').trigger('click')
  await flushPromises()

  expect(pageMocks.archiveImageProductionStrategy).toHaveBeenCalledWith('strategy-1')
  expect(pageMocks.listImageProductionStrategies).toHaveBeenCalledTimes(2)
})

it('edits default and fallback model configuration with current strategy version', async () => {
  const strategy = {
    id: 'strategy-1',
    slug: 'strategy-one',
    name: '默认图生视频输入图',
    description: 'desc',
    destination_role: 'image_to_video_input',
    supported_modes: ['image_to_image'],
    status: 'active',
    version: 2,
    default_model_id: 'model-primary',
    fallback_model_ids: ['model-fallback-old'],
    common_parameters: { count: 1 },
    provider_options: {},
  }
  pageMocks.listImageProductionStrategies.mockResolvedValue({ data: { strategies: [strategy] } })
  pageMocks.updateImageProductionStrategy.mockResolvedValue({ data: { ok: true, strategy } })
  pageMocks.listModels.mockResolvedValue({
    data: {
      models: [
        { id: 'model-primary', name: 'Primary Model', model_type: 'image' },
        { id: 'model-fallback-new', name: 'Fallback New', model_type: 'image' },
      ],
    },
  })

  const wrapper = mount(Page)
  await flushPromises()

  await wrapper.get('[data-testid="edit-strategy-strategy-1"]').trigger('click')
  await flushPromises()
  await wrapper.get('[data-testid="strategy-default-model"]').setValue('model-primary')
  await wrapper.get('[data-testid="strategy-fallback-models"]').setValue(['model-fallback-new'])
  await wrapper.get('[data-testid="save-strategy-editor"]').trigger('click')
  await flushPromises()

  expect(pageMocks.updateImageProductionStrategy).toHaveBeenCalledWith('strategy-1', expect.objectContaining({
    name: '默认图生视频输入图',
    destination_role: 'image_to_video_input',
    supported_modes: ['image_to_image'],
    default_model_id: 'model-primary',
    fallback_model_ids: ['model-fallback-new'],
    version: 2,
  }))
})
})
```

- [ ] **Step 2: Run the page test to verify it fails**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm exec vitest -- --run src/__tests__/image-production-strategy-page.test.js
```

Expected: FAIL because edit controls do not exist.

- [ ] **Step 3: Add API imports and image model loading**

Modify `web/src/views/ImageProductionStrategiesPage.vue` script:

```javascript
import { onMounted, reactive, ref } from 'vue'
import { listModels } from '../api/aiConfig.js'
import {
  archiveImageProductionStrategy,
  listImageProductionStrategies,
  updateImageProductionStrategy,
} from '../api/imageProduction.js'

const imageModels = ref([])
const editing = ref(null)
const editor = reactive({
  default_model_id: '',
  fallback_model_ids: [],
})

async function loadImageModels() {
  try {
    const response = await listModels({ model_type: 'image', enabled: true })
    const data = response?.data?.data || response?.data || response || {}
    imageModels.value = Array.isArray(data.models) ? data.models : []
  } catch (e) {
    error.value = normalizeError(e)
  }
}
```

Ensure `onMounted` calls both:

```javascript
onMounted(() => {
  loadStrategies()
  loadImageModels()
})
```

- [ ] **Step 4: Add edit/save methods**

Add:

```javascript
function openEditor(strategy) {
  editing.value = strategy
  editor.default_model_id = strategy.default_model_id || ''
  editor.fallback_model_ids = [...(strategy.fallback_model_ids || [])]
}

function closeEditor() {
  editing.value = null
  editor.default_model_id = ''
  editor.fallback_model_ids = []
}

async function saveEditor() {
  if (!editing.value) return
  error.value = ''
  try {
    await updateImageProductionStrategy(editing.value.id, {
      slug: editing.value.slug,
      name: editing.value.name,
      description: editing.value.description || '',
      destination_role: editing.value.destination_role,
      supported_modes: editing.value.supported_modes || [],
      default_model_id: editor.default_model_id || null,
      fallback_model_ids: editor.fallback_model_ids,
      common_parameters: editing.value.common_parameters || {},
      provider_options: editing.value.provider_options || {},
      review_policy_version_id: editing.value.review_policy_version_id || null,
      cost_policy_version_id: editing.value.cost_policy_version_id || null,
      capacity_policy_version_id: editing.value.capacity_policy_version_id || null,
      ab_test_policy_version_id: editing.value.ab_test_policy_version_id || null,
      version: editing.value.version,
    })
    closeEditor()
    await loadStrategies()
  } catch (e) {
    error.value = normalizeError(e)
  }
}
```

- [ ] **Step 5: Add table columns and editor markup**

Change the desktop table grid columns to include default model and fallback count. Keep this header hidden on mobile and render stacked strategy rows there:

```html
<div class="hidden grid-cols-[minmax(220px,1fr)_150px_150px_120px_90px_180px] border-b border-slate-800 px-4 py-3 text-xs font-semibold text-slate-400 md:grid">
  <span>策略</span>
  <span>用途</span>
  <span>默认模型</span>
  <span>fallback</span>
  <span>版本</span>
  <span>操作</span>
</div>
```

For each row add:

```html
<div class="md:hidden space-y-3 border-b border-slate-800 px-4 py-4">
  <div>
    <p class="text-sm font-medium text-slate-100">{{ strategy.name }}</p>
    <p class="mt-1 text-xs text-slate-500">{{ strategy.slug }}</p>
  </div>
  <dl class="grid grid-cols-2 gap-3 text-sm">
    <div>
      <dt class="text-xs text-slate-500">用途</dt>
      <dd class="mt-1 text-slate-300">{{ strategy.destination_role }}</dd>
    </div>
    <div>
      <dt class="text-xs text-slate-500">默认模型</dt>
      <dd class="mt-1 text-slate-300">{{ modelName(strategy.default_model_id) }}</dd>
    </div>
    <div>
      <dt class="text-xs text-slate-500">fallback</dt>
      <dd class="mt-1 text-slate-300">{{ (strategy.fallback_model_ids || []).length }}</dd>
    </div>
    <div>
      <dt class="text-xs text-slate-500">版本</dt>
      <dd class="mt-1 text-slate-300">v{{ strategy.version }}</dd>
    </div>
  </dl>
  <div class="flex gap-2">
    <button
      type="button"
      :data-testid="`edit-strategy-${strategy.id}`"
      class="min-h-11 border border-sky-500/40 px-3 py-2 text-xs text-sky-200 hover:bg-sky-950/40"
      @click="openEditor(strategy)"
    >
      编辑
    </button>
    <button
      type="button"
      :data-testid="`archive-strategy-${strategy.id}`"
      class="min-h-11 border border-amber-500/40 px-3 py-2 text-xs text-amber-200 hover:bg-amber-950/40 disabled:cursor-not-allowed disabled:opacity-50"
      :disabled="strategy.status === 'archived'"
      @click="archive(strategy.id)"
    >
      归档
    </button>
  </div>
</div>

<span class="text-slate-300">{{ modelName(strategy.default_model_id) }}</span>
<span class="text-slate-300">{{ (strategy.fallback_model_ids || []).length }}</span>
<div class="flex gap-2">
  <button
    type="button"
    :data-testid="`edit-strategy-${strategy.id}`"
    class="min-h-11 border border-sky-500/40 px-3 py-2 text-xs text-sky-200 hover:bg-sky-950/40"
    @click="openEditor(strategy)"
  >
    编辑
  </button>
  <button
    type="button"
    :data-testid="`archive-strategy-${strategy.id}`"
    class="min-h-11 border border-amber-500/40 px-3 py-2 text-xs text-amber-200 hover:bg-amber-950/40 disabled:cursor-not-allowed disabled:opacity-50"
    :disabled="strategy.status === 'archived'"
    @click="archive(strategy.id)"
  >
    归档
  </button>
</div>
```

Add helper:

```javascript
function modelName(modelId) {
  if (!modelId) return '自动'
  return imageModels.value.find(model => model.id === modelId)?.name || modelId
}
```

Add editor panel under the table:

```html
<section v-if="editing" class="mt-5 border border-slate-800 bg-slate-950/70 p-5">
  <div class="mb-4 flex items-center justify-between gap-3">
    <h2 class="text-base font-semibold">fallback 配置</h2>
    <button type="button" class="min-h-11 px-2 text-sm text-slate-400 hover:text-slate-100" @click="closeEditor">关闭</button>
  </div>
  <div class="grid gap-4 md:grid-cols-2">
    <div>
      <label class="mb-2 block text-sm font-medium text-slate-300" for="strategy-default-model">默认模型</label>
      <select
        id="strategy-default-model"
        v-model="editor.default_model_id"
        data-testid="strategy-default-model"
        class="w-full border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
      >
        <option value="">自动选择</option>
        <option v-for="model in imageModels" :key="model.id" :value="model.id">{{ model.name }}</option>
      </select>
    </div>
    <div>
      <label class="mb-2 block text-sm font-medium text-slate-300" for="strategy-fallback-models">fallback 模型</label>
      <select
        id="strategy-fallback-models"
        v-model="editor.fallback_model_ids"
        data-testid="strategy-fallback-models"
        multiple
        class="min-h-32 w-full border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
      >
        <option v-for="model in imageModels" :key="model.id" :value="model.id">
          {{ model.name }} · {{ model.provider || model.model_name || model.id }}
        </option>
      </select>
      <p class="mt-2 text-xs text-slate-500">按住 Ctrl/Command 可选择多个 fallback 模型。</p>
    </div>
  </div>
  <button
    type="button"
    data-testid="save-strategy-editor"
    class="mt-4 min-h-11 border border-emerald-500/40 bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
    @click="saveEditor"
  >
    保存
  </button>
</section>
```

- [ ] **Step 6: Run strategy page tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm exec vitest -- --run src/__tests__/image-production-strategy-page.test.js
```

Expected: PASS.

---

### Task 6: Focused Regression And Build

**Files:**
- No source files should be modified in this task unless a test exposes a Phase 2 bug.

- [ ] **Step 1: Run backend Phase 2 tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_model_selection_service.py tests/test_image_selection_preview_service.py tests/test_image_creation_strategy_snapshot.py tests/test_image_creation_mocked_e2e.py -v
```

Expected: PASS.

- [ ] **Step 2: Run backend image regression**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_creation_api.py tests/test_image_creation_models.py tests/test_image_creation_model_resolution.py tests/test_image_creation_pixelle_client.py -v
```

Expected: PASS.

- [ ] **Step 3: Run frontend Phase 2 tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm exec vitest -- --run src/__tests__/image-creation-page.test.js src/__tests__/image-creation-a11y.test.js src/__tests__/image-production-strategy-page.test.js src/__tests__/navigation.test.js
```

Expected: PASS.

- [ ] **Step 4: Run frontend build**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm run build
```

Expected: PASS. Existing large chunk warnings are acceptable if there are no errors.

- [ ] **Step 5: Scan for leaked secrets**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
rg -n "ark-[0-9a-f-]+|secret-key|api_key.+selection|api_key.+snapshot|api_key.+fallback" server/app server/tests web/src
```

Expected: production code has no real Ark keys or decrypted API keys. Test fixture strings are acceptable.

- [ ] **Step 6: Final review checkpoint**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git status --short server/app/services/image_model_selection_service.py server/app/services/image_selection_preview_service.py server/app/services/image_creation_service.py server/tests/test_image_model_selection_service.py server/tests/test_image_selection_preview_service.py server/tests/test_image_creation_strategy_snapshot.py web/src/views/ImageCreationPage.vue web/src/views/ImageProductionStrategiesPage.vue web/src/__tests__/image-creation-page.test.js web/src/__tests__/image-production-strategy-page.test.js
```

Expected: only Phase 2 files are listed from this plan, plus any pre-existing unrelated worktree changes outside this file set.

---

## Phase 2 Completion Criteria

- Selection preview returns detailed rejected-candidate reasons.
- Selection preview returns fallback candidates and rescue actions when the primary/default/requested model cannot satisfy the request but strategy fallback models can.
- Task creation stores richer selection explanation.
- Pixelle submit failure after durable task insert leaves a visible failed task with `fallback_trace_json`.
- Task payload includes a production timeline.
- Image creation trust rail shows rejected candidates, fallback candidates, warnings, and rescue actions.
- Image creation page shows production timeline after task creation/sync.
- Strategy center shows default model and fallback count.
- Strategy center has a minimal fallback/default model editor using optimistic strategy version update payload.
- Focused backend tests pass.
- Focused frontend tests pass.
- Frontend build passes.
- Secret scan finds no production credential leaks.

## Deferred To Later Phases

Phase 3:

- Cost estimate preview beyond local count estimate.
- High-cost confirmation.
- Capacity policy using queue/lease semantics.
- Queue depth and time estimate display.
- Review gate backlog and blocked asset rescue UI.

Phase 4:

- A/B strategy groups.
- A/B attempts with shared prompt/input hash.
- Cost multiplication confirmation.
- Winner adoption flow.
- Strategy quality/cost/latency metrics and feedback loop.

## Self-Review

Spec coverage:

- Phase 2 "Explainable Selection And Fallback Advice" is covered by Tasks 1 through 5.
- Rejected candidate diagnostics are covered by Tasks 1, 2, and 4.
- Fallback model configuration is covered by Task 5.
- Named fallback errors and repair suggestions are covered by Tasks 2, 3, and 4.
- Task timeline states are covered by Tasks 3 and 4.
- Phase 3/4 items are explicitly deferred and not mixed into this plan.

Placeholder scan:

- No step uses unresolved placeholder language.
- Every new behavior has a named test file and exact command.
- Every new backend function name is introduced before later tasks reference it.
- Every new frontend test id is introduced in the same task that adds markup.

Type consistency:

- Backend fallback payloads consistently use `fallback_candidates`, `rescue_actions`, `error_code`, and `fallback_trace_json`.
- Frontend uses the same `fallback_candidates` and `rescue_actions` response fields.
- Strategy fallback editor sends existing backend field names: `default_model_id`, `fallback_model_ids`, `supported_modes`, and `version`.

## Execution Handoff

Implementation plan saved to `docs/superpowers/plans/2026-05-28-image-production-strategy-control-plane-phase2.md`; see the engineering and design review resolutions below before implementation.

Two execution options:

1. **Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - execute tasks in this session using executing-plans, batch execution with checkpoints.

Do not create git commits while executing this plan unless the user explicitly asks. At the end of each task, collect the relevant test output and `git status --short` as the review checkpoint.

## Plan Eng Review Resolution

**Verdict:** Cleared after revision. The engineering review found 11 issues and the plan now incorporates fixes for model capability fixtures, current `AIModel` field names, fallback candidate discovery order, Pixelle submit signature, fallback confirmation UX, fallback trace redaction, frontend test mocks, strategy model-list error handling, coarse timeline wording, and split fallback tests.

### NOT In Scope

- Phase 3 cost ledger, capacity leases, high-cost confirmation, and review backlog remain deferred because this phase is only explainability and fallback advice.
- Phase 4 A/B attempts, winner adoption, and metrics feedback remain deferred because no strategy feedback loop is required for the Phase 2 vertical slice.
- Automatic fallback execution remains deferred because fallback must be explicitly confirmed by a human before creating a new task.
- Provider-side Pixelle/Seedream E2E remains deferred; this plan should keep focused mocked integration tests.

### What Already Exists

- `image_selection_preview_service.py` already validates strategy version, provider options, stores `ImageSelectionPreview`, and computes drift-safe request hashes; Phase 2 should reuse this instead of changing the preview lifecycle.
- `runtime_model_config.py` already defines the image capability contract through `scene_key`/`scene_keys`, flat `capabilities`, or `capabilities_by_scene`; the new diagnostics service must match that contract.
- `image_creation_service.py` already commits the durable task snapshot before calling `submit_image_create`; Phase 2 should only augment the submit failure branch with `fallback_trace_json`.
- `ImageCreationTask` already has `fallback_trace_json` and `error_message` columns; no migration is needed for those fields.
- Strategy update APIs already support `default_model_id`, `fallback_model_ids`, and optimistic `version`; the frontend editor can use existing endpoints.

### Resolved Issues

1. **Resolved - diagnostics tests and examples use the current model capability shape.**
   Task 1 and Task 2 fixtures now include `scene_key`, `scene_keys`, and flat `capabilities`, matching `runtime_model_config.py`.

2. **Resolved - Task 3 preserves the existing Pixelle submit call signature.**
   The plan now keeps `await submit_image_create(db=db, model_config=model_config, **pixelle_payload)` and only changes the failure branch after the durable task commit.

3. **Resolved - fallback confirmation is now a complete user path.**
   Blocked preview responses now carry `preview_blocked` and `confirmation_required`; the frontend disables create and adds a real confirm-fallback action that sets `form.modelId` and reruns preview.

4. **Resolved - fallback trace uses redacted provider error text.**
   The plan now adds `_redact_provider_error` and tests that Ark-style keys, `Authorization`, and `api_key` strings do not persist in fallback traces.

5. **Resolved - the strategy page test mock plan replaces the existing mock header.**
   Task 5 now explicitly says to replace the current import/mock header and avoid a duplicate `vi.mock('../api/imageProduction.js')`.

6. **Resolved - timeline states are labeled as task-level only.**
   The plan now keeps review and approval pending/blocked at task level and explicitly defers asset-level review accuracy to the later review backlog work.

7. **Resolved - fallback tests cover both failure classes.**
   Task 2 covers capability fallback, and Task 3 covers provider submit failure after durable snapshot.

8. **Resolved - new `AIModel` test fixtures use real column names.**
   Task 1 now uses `base_url` and encrypted `api_key` instead of the old field names that are not present on the SQLAlchemy model.

9. **Resolved - preview service tests use the existing helper.**
   Task 2 now uses `_seed_image_model`, matching the current `test_image_selection_preview_service.py` helper API.

10. **Resolved - fallback candidates are collected before primary selection can break the loop.**
    `resolve_image_model_selection` now precomputes fallback candidates in a first pass so provider submit failures can still surface configured fallback models even when the primary model supports the capability.

11. **Resolved - strategy center model loading handles API failure.**
    `loadImageModels` now uses the existing `normalizeError` path instead of leaving an unhandled rejected promise.

### Failure Modes

| Codepath | Production failure | Revised planned coverage | User impact |
|----------|--------------------|--------------------------|-------------|
| Model diagnostics | No models selected because fixtures/config use unsupported capability shape | Fixtures now use current `scene_key`/flat `capabilities` contract | Preview selects configured models correctly |
| Fallback preview | User receives advice but submit button still creates with old/default model | UI test now requires blocked submit plus explicit fallback confirmation | User cannot create until fallback is confirmed and preview reruns |
| Pixelle submit failure | Wrong wrapper call raises local TypeError instead of capturing provider failure | Plan preserves existing `submit_image_create(db=db, model_config=model_config, **pixelle_payload)` call | Failed task trace is reliable |
| Fallback trace | Raw exception persists provider secrets | Redaction helper and secret assertion added | Provider credentials stay out of task payloads |
| Timeline | Review shown as done while assets still need approval | Timeline is explicitly task-level and keeps review/approval pending or blocked | User sees production progress without false approval state |
| Provider-failure fallback | Primary model supports the capability, selected early, and hides configured fallbacks | Fallback candidates are precomputed before model selection breaks | Failed task can show retry-with-fallback action |
| Strategy model list | Model center API fails while strategy page loads | `loadImageModels` catches and displays the normalized error | Page stays mounted with a visible error |

Critical gaps resolved in plan: model capability contract mismatch, wrong Pixelle submit signature, and incomplete fallback confirmation path.

### Parallelization Strategy

| Step | Modules touched | Depends on |
|------|-----------------|------------|
| Backend diagnostics and preview | `server/app/services`, `server/tests` | None, after fixing capability contract |
| Backend task trace and timeline | `server/app/services`, `server/tests` | Diagnostics service |
| Image creation trust rail | `web/src/views`, `web/src/__tests__` | Preview response contract |
| Strategy center fallback editor | `web/src/views`, `web/src/api`, `web/src/__tests__` | Existing strategy API only |

Lane A: backend diagnostics -> preview -> task trace/timeline, sequential because they share service contracts.

Lane B: strategy center fallback editor, can run in parallel after agreeing API field names because it uses existing strategy endpoints.

Lane C: image creation trust rail, starts after Lane A fixes the preview/fallback response contract.

Conflict flags: Lane A and Lane C both depend on the exact fallback payload shape; do not implement C before A's response contract is final.

### Completion Summary

- Step 0: Scope Challenge - scope accepted as Phase 2 only.
- Architecture Review: 3 issues found, all resolved.
- Code Quality Review: 3 issues found, all resolved.
- Test Review: failure-mode table produced, 7 gaps identified and resolved in plan.
- Performance Review: 0 blocking issues found; current all-image-model query is acceptable for Phase 2 scale.
- NOT in scope: written.
- What already exists: written.
- Deferred-tracking updates: skipped; these are blocking plan fixes, not deferred work items.
- Failure modes: 0 unresolved critical gaps after revision.
- Outside voice: skipped; no subagent delegation was requested for this review.
- Parallelization: 3 lanes, 1 backend sequential lane plus 1 parallel UI lane.
- Lake Score: 8/10; Phase 3/4 items remain intentionally deferred.

## Plan Design Review Resolution

**Verdict:** Cleared after revision. Initial design completeness was 6/10; revised plan is 8.5/10 for this Phase 2 scope.

### NOT In Scope

- A full visual redesign of the image creation workbench is not part of Phase 2; this phase improves trust, fallback confirmation, and strategy configuration without changing navigation.
- Cost dashboards, queue-depth forecasts, and asset-level review backlog remain Phase 3 concerns.
- Generated high-fidelity mockups are not required for this execution plan because the plan updates existing pages and now defines the missing UI states, hierarchy, and accessibility rules directly.

### What Already Exists

- `ImageCreationPage.vue` already has a two-column workbench, trust rail, create controls, and task panel; Phase 2 should enhance those surfaces instead of adding a new page.
- `ImageProductionStrategiesPage.vue` already uses a restrained operational table style; the fallback editor should stay consistent with that utilitarian layout.
- Existing tests already use stable `data-testid` hooks and `aria-live` patterns; new timeline, fallback warning, and disabled reason elements should follow the same pattern.
- Existing `normalizeError` handling is available on the strategy page and should remain the version-conflict/error display path.

### Design Decisions Added

1. Trust rail is summary-first: selected model, preview state, strategy/version, and cost are visible before diagnostics.
2. Fallback-required state is a warning band with one primary action and a visible disabled-create reason.
3. Rejected candidates and raw technical diagnostics are collapsed behind the actionable status.
4. Production timeline is an ordered stepper with localized status labels, stable dots, and `aria-current="step"` on the active step.
5. Strategy fallback editing uses named model selectors, not raw model ID text entry.
6. Mobile strategy rows become stacked labeled blocks instead of squeezing a six-column grid.
7. Empty fallback state must point the operator back to model/strategy configuration.
8. All new controls require text state, 44px minimum touch targets, keyboard focus, and no color-only status signaling.

### Completion Summary

- Pre-review audit: no project `DESIGN.md` found; current app pattern is dark, dense, operational tooling.
- Pass 1, information architecture: 6/10 to 8.5/10 after adding summary-first trust rail and stepper hierarchy.
- Pass 2, interaction states: 6/10 to 8.5/10 after adding fallback warning, disabled reason, version-conflict behavior, and empty fallback state.
- Pass 3, user journey: 6.5/10 to 8.5/10 after turning fallback from passive advice into a clear confirm-and-rerun path.
- Pass 4, AI slop risk: 7/10 to 8.5/10 after replacing generic "show diagnostics" wording with specific UI structures.
- Pass 5, design system alignment: 7/10 to 8.5/10 by preserving existing dark operational page patterns and test hooks.
- Pass 6, responsive and accessibility: 5/10 to 8/10 after adding mobile stacked rows, ARIA stepper behavior, and touch-target requirements.
- Pass 7, unresolved decisions: 8 decisions resolved, 0 deferred within Phase 2 scope.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | not_run | Not part of this invocation |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | not_run | Not run |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 2 | clean | 11 issues found and resolved in plan, 0 unresolved critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | clean | Score 6/10 to 8.5/10, 8 design decisions resolved |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | not_run | Not run |

- **UNRESOLVED:** 0
- **VERDICT:** ENG + DESIGN CLEARED - ready to implement Phase 2 from this revised plan.

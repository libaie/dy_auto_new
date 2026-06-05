# Image Creation Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a provider-neutral image creation workbench where dy_auto can create, edit, review, approve, and reuse visual assets before image-to-video production.

**Architecture:** dy_auto owns orchestration, task records, asset records, review state, model resolution, and the frontend workbench. Pixelle-Video owns execution through a new standalone `/api/stages/images/create` endpoint and maps normalized image creation requests to provider-specific payloads. The first provider is Ark Plan V3 Seedream, while dy_auto keeps the workflow capability-driven so future image providers can plug in without rewriting the workbench.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest, httpx, Vue 3, Vitest, Vue Test Utils, Tailwind utility classes, existing dy_auto AI model center, existing Pixelle stage client, Pixelle-Video FastAPI stage router.

---

## Source Inputs

- Spec: `D:\devWorkspace\jsProjects\dy_auto\docs\superpowers\specs\2026-05-27-image-creation-workbench-design.md`
- dy_auto model schema: `D:\devWorkspace\jsProjects\dy_auto\server\app\data\model_schema_data.py`
- dy_auto runtime model resolver: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\runtime_model_config.py`
- dy_auto Pixelle stage client: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\pixelle_stage_client.py`
- dy_auto production asset/review models: `D:\devWorkspace\jsProjects\dy_auto\server\app\db_models.py`
- dy_auto frontend model center pattern: `D:\devWorkspace\jsProjects\dy_auto\web\src\views\AIConfigPage.vue`
- dy_auto frontend review pattern: `D:\devWorkspace\jsProjects\dy_auto\web\src\views\AIVideoReviewPage.vue`
- Pixelle stage schemas: `D:\devWorkspace\Pixelle-Video\api\schemas\stages.py`
- Pixelle stage router: `D:\devWorkspace\Pixelle-Video\api\routers\stages.py`
- Pixelle Ark Plan V3 helper: `D:\devWorkspace\Pixelle-Video\api\services\ark_plan_v3.py`

## Out Of Scope

- Mask editor or brush-based image editing.
- Full generic media asset platform.
- Bulk campaign generation outside video-production needs.
- A second Pixelle model configuration UI.
- Douyin publishing.
- Paid-provider E2E as a merge gate.

## File Map

### dy_auto Backend

| File | Action | Responsibility |
|---|---|---|
| `server/app/data/model_schema_data.py` | Modify | Add `image_editing` scene and provider-neutral image capabilities. |
| `server/app/routers/ai_config.py` | Modify | Seed Seedream image editing model without duplicating secrets. |
| `server/app/services/runtime_model_config.py` | Modify | Add capability-aware image model resolver and keep existing resolver stable. |
| `server/app/db_models.py` | Modify | Add `ImageCreationTask`, `ImageCreationAsset`, `ImageCreationReviewRecord`. |
| `server/alembic/versions/f6a7b8c9d0e1_image_creation_workbench.py` | Create | Add image creation tables, constraints, and indexes. |
| `server/app/services/image_creation_errors.py` | Create | Named image creation error helpers. |
| `server/app/services/image_creation_storage.py` | Create | Upload validation, Pixelle reachability, persistence, checksum, and cleanup helpers. |
| `server/app/services/image_creation_service.py` | Create | Task validation, creation, sync, upsert, review, and edit-again orchestration. |
| `server/app/routers/image_creation.py` | Create | REST API for uploads, tasks, sync, assets, review, and edit-again. |
| `server/app/services/pixelle_stage_client.py` | Modify | Add `submit_image_create`. |
| `server/app/main.py` | Modify | Register the image creation router. |

### dy_auto Frontend

| File | Action | Responsibility |
|---|---|---|
| `web/src/api/imageCreation.js` | Create | Axios client for image creation endpoints. |
| `web/src/router/index.js` | Modify | Add `/image-creation` route and admin guard path. |
| `web/src/constants/navigation.js` | Modify | Add `图像创作` under `AI 视频`. |
| `web/src/views/ImageCreationPage.vue` | Create | Workbench page with modes, sources, references, task state, results, review actions. |

### Pixelle-Video

| File | Action | Responsibility |
|---|---|---|
| `D:\devWorkspace\Pixelle-Video\api\schemas\stages.py` | Modify | Add standalone image creation request schema. |
| `D:\devWorkspace\Pixelle-Video\api\routers\stages.py` | Modify | Add `/stages/images/create` and task runner. |
| `D:\devWorkspace\Pixelle-Video\api\services\ark_plan_v3.py` | Modify | Add Seedream image create mapping for text, image, multi-reference, and image-set modes. |

### Tests

| File | Action |
|---|---|
| `server/tests/test_image_creation_models.py` | Create |
| `server/tests/test_image_creation_model_resolution.py` | Create |
| `server/tests/test_image_creation_pixelle_client.py` | Create |
| `server/tests/test_image_creation_api.py` | Create |
| `server/tests/test_image_creation_mocked_e2e.py` | Create |
| `server/tests/test_model_schema.py` | Modify |
| `server/tests/test_pixelle_stage_client.py` | Modify |
| `web/src/__tests__/image-creation-api.test.js` | Create |
| `web/src/__tests__/image-creation-page.test.js` | Create |
| `web/src/__tests__/image-creation-responsive.test.js` | Create |
| `web/src/__tests__/navigation.test.js` | Modify |
| `D:\devWorkspace\Pixelle-Video\tests\test_stage_image_create.py` | Create |

---

## Data Contracts

### Image Creation Task Response

```json
{
  "ok": true,
  "task": {
    "id": "task-id",
    "mode": "image_to_image",
    "capability_key": "image_to_image",
    "output_mode": "single",
    "status": "running",
    "model_scene_key": "image_editing",
    "cost_status": "confirmed",
    "estimated_cost": { "amount": 0.08, "currency": "CNY" },
    "pixelle_task_id": "pixelle-task-id"
  },
  "assets": [],
  "reviews": []
}
```

### Named Error Response

```json
{
  "ok": false,
  "error_code": "IMAGE_CAPABILITY_UNSUPPORTED",
  "message": "Selected image model does not support multi_reference_to_image_set.",
  "repair_action": "Choose a compatible image model or change mode.",
  "repair_route": "/ai-config",
  "retryable": true,
  "affected_ids": ["model-id"]
}
```

### Pixelle Standalone Image Create Request

```json
{
  "external_task_id": "dy-auto-task-id",
  "mode": "multi_reference_to_image_set",
  "capability_key": "multi_reference_to_image_set",
  "output_mode": "image_set",
  "prompt": "Generate six consistent storyboard frames.",
  "negative_prompt": "",
  "reference_images": [
    { "url": "http://127.0.0.1:8000/static/image-creation/uploads/a.png", "role": "character", "asset_id": "a" }
  ],
  "source_image_url": "",
  "count": 6,
  "size": "3K",
  "output_format": "png",
  "response_format": "url",
  "provider_options": {
    "sequential_image_generation": "auto",
    "max_images": 6,
    "watermark": false
  },
  "model_config": {
    "scene_key": "image_editing",
    "provider": "seedance",
    "base_url": "https://ark.cn-beijing.volces.com/api/plan/v3",
    "api_key": "runtime-only",
    "model": "doubao-seedream-5.0-lite",
    "config": {}
  },
  "context": { "series_id": "series-id", "episode_id": "episode-id" }
}
```

---

### Task 1: Model Schema And Capability Resolver

**Files:**
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\data\model_schema_data.py`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\routers\ai_config.py`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\runtime_model_config.py`
- Test: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_model_schema.py`
- Test: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_creation_model_resolution.py`

- [ ] **Step 1: Write failing schema tests**

Add these tests to `server/tests/test_model_schema.py`:

```python
def test_schema_contains_image_editing_scene(client):
    resp = client.get("/api/ai-models/schema")
    data = resp.json()

    scene = next(item for item in data["scenes"] if item["key"] == "image_editing")

    assert scene["label"] == "Image · 以图改图"
    assert scene["model_type"] == "image"
    assert "seedance" in scene["providers"]
    field_keys = {field["key"] for field in scene["fields"]}
    assert {"max_reference_images", "max_output_images", "supports_image_set"} <= field_keys


def test_scene_key_mapping_supports_image_editing(client):
    from app.data.model_schema_data import scene_key_to_model_type

    assert scene_key_to_model_type("image_editing") == "image"
```

- [ ] **Step 2: Run schema tests and confirm failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_model_schema.py::test_schema_contains_image_editing_scene tests/test_model_schema.py::test_scene_key_mapping_supports_image_editing -q
```

Expected: failure because `image_editing` is not in `SCENES`.

- [ ] **Step 3: Add `image_editing` scene**

In `server/app/data/model_schema_data.py`, insert after the existing `image_generation` scene:

```python
    {
        "key": "image_editing",
        "label": "Image · 以图改图",
        "model_type": "image",
        "description": "用于以图改图、多图参考、组图生成和图像修复",
        "providers": ["seedance", "openai", "comfyui", "pixelle", "custom"],
        "fields": [
            {"key": "default_size", "label": "Default Size", "type": "select", "default": "3K", "options": ["2K", "3K", "4K", "2048x2048", "1600x2848", "2304x4096"]},
            {"key": "default_quality", "label": "Quality", "type": "select", "default": "hd", "options": ["standard", "hd"]},
            {"key": "edit_strength", "label": "Edit Strength", "type": "number", "default": 0.65, "min": 0, "max": 1, "step": 0.05},
            {"key": "preserve_subject", "label": "Preserve Subject", "type": "boolean", "default": True},
            {"key": "supports_stream", "label": "Supports Stream", "type": "boolean", "default": False},
            {"key": "supports_image_set", "label": "Supports Image Set", "type": "boolean", "default": True},
            {"key": "max_reference_images", "label": "Max Reference Images", "type": "number", "default": 14, "min": 1, "max": 14},
            {"key": "max_output_images", "label": "Max Output Images", "type": "number", "default": 15, "min": 1, "max": 15},
            {"key": "supported_output_formats", "label": "Output Formats", "type": "string", "default": "jpeg,png"},
            {"key": "supports_watermark_toggle", "label": "Watermark Toggle", "type": "boolean", "default": True},
        ],
    },
```

Update the existing `test_schema_returns_scenes_providers_protocols` assertion from `7` to `8`.

- [ ] **Step 4: Write failing resolver tests**

Create `server/tests/test_image_creation_model_resolution.py`:

```python
import pytest

from app.db_models import AIModel
from app.services.crypto import encrypt
from app.services.runtime_model_config import (
    RuntimeModelConfigError,
    resolve_image_model_for_capability,
)


def _model(db, *, scene_key, capabilities, enabled=True, sort_order=0, model_name=None, scene_keys=None):
    model = AIModel(
        name=f"{scene_key}-{sort_order}",
        model_type="image",
        provider="seedance",
        base_url="https://ark.cn-beijing.volces.com/api/plan/v3",
        api_key=encrypt("secret-key"),
        model_name=model_name or f"doubao-seedream-5.0-lite-{sort_order}",
        enabled=enabled,
        sort_order=sort_order,
        config_json={
            "scene_key": scene_key,
            "scene_keys": scene_keys or [scene_key],
            "capabilities": capabilities,
            "config_version": 1,
        },
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


def test_resolve_image_model_for_capability_selects_supported_model(db_session):
    unsupported = _model(db_session, scene_key="image_editing", capabilities={"image_to_image": False}, sort_order=0)
    supported = _model(db_session, scene_key="image_editing", capabilities={"image_to_image": True}, sort_order=1)

    config = resolve_image_model_for_capability(db_session, "image_editing", "image_to_image")

    assert config["model_id"] == supported.id
    assert config["scene_key"] == "image_editing"
    assert config["capability_key"] == "image_to_image"
    assert config["api_key"] == "secret-key"
    assert unsupported.id != config["model_id"]


def test_resolve_image_model_rejects_explicit_unsupported_model(db_session):
    model = _model(db_session, scene_key="image_editing", capabilities={"multi_reference_to_image": False})

    with pytest.raises(RuntimeModelConfigError, match="IMAGE_CAPABILITY_UNSUPPORTED"):
        resolve_image_model_for_capability(
            db_session,
            "image_editing",
            "multi_reference_to_image",
            explicit_model_id=model.id,
        )


def test_legacy_image_generation_model_supports_text_to_image(db_session):
    model = AIModel(
        name="Legacy Seedream",
        model_type="image",
        provider="seedance",
        base_url="https://ark.cn-beijing.volces.com/api/plan/v3",
        api_key=encrypt("secret-key"),
        model_name="doubao-seedream-5.0-lite",
        enabled=True,
        config_json={"scene_key": "image_generation"},
    )
    db_session.add(model)
    db_session.commit()

    config = resolve_image_model_for_capability(db_session, "image_generation", "text_to_image")

    assert config["model_id"] == model.id
    assert config["capability_key"] == "text_to_image"


def test_single_seedream_model_can_support_generation_and_editing_scenes(db_session):
    model = _model(
        db_session,
        scene_key="image_generation",
        scene_keys=["image_generation", "image_editing"],
        capabilities={
            "text_to_image": True,
            "image_to_image": True,
            "multi_reference_to_image_set": True,
        },
        model_name="doubao-seedream-5.0-lite",
    )

    config = resolve_image_model_for_capability(db_session, "image_editing", "image_to_image")

    assert config["model_id"] == model.id
    assert config["scene_key"] == "image_editing"
```

- [ ] **Step 5: Run resolver tests and confirm failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_image_creation_model_resolution.py -q
```

Expected: import failure for `resolve_image_model_for_capability`.

- [ ] **Step 6: Implement capability resolver**

Append to `server/app/services/runtime_model_config.py`:

```python
def _model_supports_capability(model: AIModel, scene_key: str, capability_key: str) -> bool:
    config = model.config_json or {}
    scene_keys = config.get("scene_keys") or [config.get("scene_key")]
    if scene_key not in scene_keys:
        return False
    by_scene = config.get("capabilities_by_scene")
    if isinstance(by_scene, dict) and isinstance(by_scene.get(scene_key), dict):
        return bool(by_scene[scene_key].get(capability_key))
    capabilities = config.get("capabilities")
    if isinstance(capabilities, dict):
        return bool(capabilities.get(capability_key))
    return scene_key == "image_generation" and capability_key == "text_to_image"


def resolve_image_model_for_capability(
    db: Session,
    scene_key: str,
    capability_key: str,
    explicit_model_id: str | None = None,
) -> dict:
    query = db.query(AIModel).filter(AIModel.enabled == True, AIModel.model_type == "image")
    if explicit_model_id:
        query = query.filter(AIModel.id == explicit_model_id)

    models = query.order_by(AIModel.sort_order.asc(), AIModel.created_at.asc()).all()
    for model in models:
        if _model_supports_capability(model, scene_key, capability_key):
            config = resolve_runtime_model_config(db, scene_key, explicit_model_id=model.id)
            config["capability_key"] = capability_key
            return config

    raise RuntimeModelConfigError(
        f"IMAGE_CAPABILITY_UNSUPPORTED: no enabled image model supports {scene_key}/{capability_key}"
    )
```

- [ ] **Step 7: Expand the existing Seedream default model**

Do not add a second `image`/`seedance`/`doubao-seedream-5.0-lite` row. `AIModel` currently has a unique constraint on `(model_type, provider, model_name)`, so a duplicate editing row will fail. Instead, update the existing Seedream default image model config to declare both generation and editing scenes:

```python
{
    "name": "Seedream 5.0 Lite",
    "model_type": "image",
    "provider": "seedance",
    "base_url": SEEDANCE_ARK_BASE_URL,
    "model_name": SEEDREAM_IMAGE_MODEL,
    "config_json": {
        "scene_key": "image_generation",
        "scene_keys": ["image_generation", "image_editing"],
        "default_size": "3K",
        "default_quality": "hd",
        "capabilities": {
            "text_to_image": True,
            "image_to_image": True,
            "multi_reference_to_image": True,
            "text_to_image_set": True,
            "image_to_image_set": True,
            "multi_reference_to_image_set": True,
        },
        "limits": {
            "min_reference_images": 1,
            "max_reference_images": 14,
            "max_output_images": 15,
            "max_reference_plus_output_images": 15,
            "max_input_image_mb": 30,
            "max_input_pixels": 36000000,
            "aspect_ratio_range": [0.0625, 16],
        },
        "provider_options_schema": {
            "sequential_image_generation": ["disabled", "auto"],
            "max_images": {"type": "number", "min": 1, "max": 15},
            "stream": {"type": "boolean"},
            "response_format": ["url", "b64_json"],
            "output_format": ["jpeg", "png"],
            "watermark": {"type": "boolean"},
            "optimize_prompt_mode": ["standard", "fast"],
            "web_search": {"type": "boolean"},
        },
    },
}
```

Update `seed_ai_models()` so existing Seedream rows get missing `scene_keys`, `capabilities`, `limits`, and `provider_options_schema` merged into `config_json` without overwriting user-customized values.

- [ ] **Step 8: Run schema and resolver tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_model_schema.py tests/test_image_creation_model_resolution.py -q
```

Expected: all selected tests pass.

- [ ] **Step 9: Commit**

Run:

```powershell
git add server/app/data/model_schema_data.py server/app/routers/ai_config.py server/app/services/runtime_model_config.py server/tests/test_model_schema.py server/tests/test_image_creation_model_resolution.py
git commit -m "feat: add image editing model capability resolution"
```

---

### Task 2: Database Models And Migration

**Files:**
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\db_models.py`
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\alembic\versions\f6a7b8c9d0e1_image_creation_workbench.py`
- Test: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_creation_models.py`

- [ ] **Step 1: Write failing model tests**

Create `server/tests/test_image_creation_models.py`:

```python
from app.db_models import (
    Episode,
    ImageCreationAsset,
    ImageCreationReviewRecord,
    ImageCreationTask,
    Series,
)


def _series_episode(db):
    series = Series(title="Image Series", logline="visual test", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    return series, episode


def test_image_creation_task_asset_review_roundtrip(db_session):
    series, episode = _series_episode(db_session)
    task = ImageCreationTask(
        idempotency_key="idem-1",
        request_hash="hash-1",
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="running",
        series_id=series.id,
        episode_id=episode.id,
        prompt="雨夜街头",
        count=1,
        model_scene_key="image_generation",
        storage_status="pending",
        cost_status="confirmed",
    )
    db_session.add(task)
    db_session.flush()

    asset = ImageCreationAsset(
        task_id=task.id,
        series_id=series.id,
        episode_id=episode.id,
        asset_type="image",
        url="http://example.test/image.png",
        status="review_pending",
        version=1,
        group_id="group-1",
        group_index=1,
        destination_role="image_to_video_input",
        prompt_hash="prompt-hash",
        is_latest=True,
        storage_status="persisted",
    )
    db_session.add(asset)
    db_session.flush()

    review = ImageCreationReviewRecord(
        task_id=task.id,
        asset_id=asset.id,
        review_type="human",
        status="approved",
        asset_version=1,
        is_latest_asset_review=True,
    )
    db_session.add(review)
    db_session.commit()

    saved = db_session.query(ImageCreationAsset).filter_by(id=asset.id).one()
    assert saved.destination_role == "image_to_video_input"
    assert saved.task_id == task.id
    assert saved.storage_status == "persisted"


def test_image_creation_asset_unique_group_slot(db_session):
    task = ImageCreationTask(
        mode="text_to_image_set",
        output_mode="image_set",
        capability_key="text_to_image_set",
        status="running",
        prompt="组图",
        count=2,
        model_scene_key="image_generation",
        storage_status="pending",
        cost_status="confirmed",
    )
    db_session.add(task)
    db_session.flush()

    db_session.add(ImageCreationAsset(
        task_id=task.id,
        asset_type="image",
        url="http://example.test/1.png",
        status="review_pending",
        version=1,
        group_id="group-1",
        group_index=1,
        prompt_hash="hash",
        is_latest=True,
        storage_status="persisted",
    ))
    db_session.commit()

    duplicate = ImageCreationAsset(
        task_id=task.id,
        asset_type="image",
        url="http://example.test/dup.png",
        status="review_pending",
        version=1,
        group_id="group-1",
        group_index=1,
        prompt_hash="hash",
        is_latest=True,
        storage_status="persisted",
    )
    db_session.add(duplicate)

    try:
        db_session.commit()
    except Exception:
        db_session.rollback()
        raised = True
    else:
        raised = False

    assert raised is True
```

- [ ] **Step 2: Run model tests and confirm failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_image_creation_models.py -q
```

Expected: import failure for `ImageCreationTask`.

- [ ] **Step 3: Add SQLAlchemy models**

Append these classes near `VideoReviewRecord` in `server/app/db_models.py`:

```python
class ImageCreationTask(Base):
    __tablename__ = "image_creation_tasks"

    id = Column(String(36), primary_key=True, default=_uuid)
    idempotency_key = Column(String(120), nullable=True)
    request_hash = Column(String(64), nullable=True)
    mode = Column(String(40), nullable=False)
    output_mode = Column(String(20), nullable=False, default="single")
    capability_key = Column(String(60), nullable=False)
    status = Column(String(40), nullable=False, default="queued")
    series_id = Column(String(36), ForeignKey("series.id", ondelete="SET NULL"), nullable=True)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True)
    prompt = Column(Text, nullable=False)
    negative_prompt = Column(Text, nullable=True)
    source_type = Column(String(30), nullable=True)
    source_url = Column(Text, nullable=True)
    source_asset_id = Column(String(36), nullable=True)
    reference_images_json = Column(JSON, nullable=True, default=list)
    destination_role = Column(String(40), nullable=True)
    destination_context_json = Column(JSON, nullable=True, default=dict)
    size = Column(String(40), nullable=True)
    count = Column(Integer, nullable=False, default=1)
    output_format = Column(String(20), nullable=True)
    response_format = Column(String(20), nullable=True)
    watermark = Column(Boolean, nullable=True)
    provider_options_json = Column(JSON, nullable=True, default=dict)
    estimated_cost_json = Column(JSON, nullable=True, default=dict)
    cost_status = Column(String(30), nullable=False, default="not_estimated")
    requires_cost_confirmation = Column(Boolean, nullable=False, default=False)
    storage_status = Column(String(30), nullable=False, default="pending")
    model_scene_key = Column(String(60), nullable=False)
    model_trace_json = Column(JSON, nullable=True, default=dict)
    pixelle_task_id = Column(String(120), nullable=True)
    partial_results_json = Column(JSON, nullable=True, default=list)
    usage_json = Column(JSON, nullable=True, default=dict)
    error_code = Column(String(80), nullable=True)
    error_message = Column(Text, nullable=True)
    repair_action = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_image_tasks_status", "status"),
        Index("idx_image_tasks_series_episode", "series_id", "episode_id"),
        Index("idx_image_tasks_model_capability", "model_scene_key", "capability_key"),
        Index("idx_image_tasks_created", "created_at"),
        UniqueConstraint("idempotency_key", name="uq_image_task_idempotency_key"),
        UniqueConstraint("pixelle_task_id", name="uq_image_task_pixelle_task_id"),
    )


class ImageCreationAsset(Base):
    __tablename__ = "image_creation_assets"

    id = Column(String(36), primary_key=True, default=_uuid)
    task_id = Column(String(36), ForeignKey("image_creation_tasks.id", ondelete="CASCADE"), nullable=False)
    series_id = Column(String(36), ForeignKey("series.id", ondelete="SET NULL"), nullable=True)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True)
    asset_type = Column(String(30), nullable=False, default="image")
    url = Column(Text, nullable=True)
    local_path = Column(Text, nullable=True)
    thumbnail_url = Column(Text, nullable=True)
    checksum = Column(String(120), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    status = Column(String(40), nullable=False, default="review_pending")
    version = Column(Integer, nullable=False, default=1)
    source_asset_id = Column(String(36), nullable=True)
    source_url = Column(Text, nullable=True)
    reference_images_json = Column(JSON, nullable=True, default=list)
    group_id = Column(String(120), nullable=True)
    group_index = Column(Integer, nullable=True)
    destination_role = Column(String(40), nullable=True)
    destination_context_json = Column(JSON, nullable=True, default=dict)
    downstream_usage_json = Column(JSON, nullable=True, default=list)
    provider_error_json = Column(JSON, nullable=True, default=dict)
    provider_task_id = Column(String(120), nullable=True)
    pixelle_task_id = Column(String(120), nullable=True)
    prompt_hash = Column(String(64), nullable=True)
    is_latest = Column(Boolean, nullable=False, default=True)
    metadata_json = Column(JSON, nullable=True, default=dict)
    storage_status = Column(String(30), nullable=False, default="persisted")
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        Index("idx_image_assets_task", "task_id"),
        Index("idx_image_assets_status", "status"),
        Index("idx_image_assets_destination", "destination_role"),
        Index("idx_image_assets_series_episode", "series_id", "episode_id"),
        Index("idx_image_assets_group", "group_id"),
        Index("idx_image_assets_source", "source_asset_id"),
        Index("idx_image_assets_latest", "is_latest"),
        UniqueConstraint("task_id", "group_id", "group_index", "version", name="uq_image_asset_group_slot_version"),
    )


class ImageCreationReviewRecord(Base):
    __tablename__ = "image_creation_review_records"

    id = Column(String(36), primary_key=True, default=_uuid)
    asset_id = Column(String(36), ForeignKey("image_creation_assets.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(String(36), ForeignKey("image_creation_tasks.id", ondelete="CASCADE"), nullable=False)
    review_type = Column(String(20), nullable=False)
    status = Column(String(30), nullable=False)
    score = Column(Float, nullable=True)
    criteria_json = Column(JSON, nullable=True, default=list)
    issues_json = Column(JSON, nullable=True, default=list)
    reviewer_user_id = Column(String(36), nullable=True)
    model_trace_json = Column(JSON, nullable=True, default=dict)
    comment = Column(Text, nullable=True)
    asset_version = Column(Integer, nullable=True)
    is_latest_asset_review = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    __table_args__ = (
        Index("idx_image_review_asset", "asset_id"),
        Index("idx_image_review_task", "task_id"),
        Index("idx_image_review_status", "status"),
        Index("idx_image_review_latest", "asset_id", "asset_version", "is_latest_asset_review"),
    )
```

- [ ] **Step 4: Add Alembic migration**

Create `server/alembic/versions/f6a7b8c9d0e1_image_creation_workbench.py`:

```python
"""add image creation workbench tables

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa


revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image_creation_tasks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("idempotency_key", sa.String(length=120), nullable=True),
        sa.Column("request_hash", sa.String(length=64), nullable=True),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("output_mode", sa.String(length=20), nullable=False, server_default="single"),
        sa.Column("capability_key", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="queued"),
        sa.Column("series_id", sa.String(length=36), sa.ForeignKey("series.id", ondelete="SET NULL"), nullable=True),
        sa.Column("episode_id", sa.String(length=36), sa.ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("negative_prompt", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=30), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_asset_id", sa.String(length=36), nullable=True),
        sa.Column("reference_images_json", sa.JSON(), nullable=True),
        sa.Column("destination_role", sa.String(length=40), nullable=True),
        sa.Column("destination_context_json", sa.JSON(), nullable=True),
        sa.Column("size", sa.String(length=40), nullable=True),
        sa.Column("count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("output_format", sa.String(length=20), nullable=True),
        sa.Column("response_format", sa.String(length=20), nullable=True),
        sa.Column("watermark", sa.Boolean(), nullable=True),
        sa.Column("provider_options_json", sa.JSON(), nullable=True),
        sa.Column("estimated_cost_json", sa.JSON(), nullable=True),
        sa.Column("cost_status", sa.String(length=30), nullable=False, server_default="not_estimated"),
        sa.Column("requires_cost_confirmation", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("storage_status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("model_scene_key", sa.String(length=60), nullable=False),
        sa.Column("model_trace_json", sa.JSON(), nullable=True),
        sa.Column("pixelle_task_id", sa.String(length=120), nullable=True),
        sa.Column("partial_results_json", sa.JSON(), nullable=True),
        sa.Column("usage_json", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("repair_action", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("idx_image_tasks_status", "image_creation_tasks", ["status"])
    op.create_index("idx_image_tasks_series_episode", "image_creation_tasks", ["series_id", "episode_id"])
    op.create_index("idx_image_tasks_model_capability", "image_creation_tasks", ["model_scene_key", "capability_key"])
    op.create_index("idx_image_tasks_created", "image_creation_tasks", ["created_at"])
    op.create_unique_constraint("uq_image_task_idempotency_key", "image_creation_tasks", ["idempotency_key"])
    op.create_unique_constraint("uq_image_task_pixelle_task_id", "image_creation_tasks", ["pixelle_task_id"])

    op.create_table(
        "image_creation_assets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("task_id", sa.String(length=36), sa.ForeignKey("image_creation_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("series_id", sa.String(length=36), sa.ForeignKey("series.id", ondelete="SET NULL"), nullable=True),
        sa.Column("episode_id", sa.String(length=36), sa.ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("asset_type", sa.String(length=30), nullable=False, server_default="image"),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("local_path", sa.Text(), nullable=True),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("checksum", sa.String(length=120), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="review_pending"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source_asset_id", sa.String(length=36), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("reference_images_json", sa.JSON(), nullable=True),
        sa.Column("group_id", sa.String(length=120), nullable=True),
        sa.Column("group_index", sa.Integer(), nullable=True),
        sa.Column("destination_role", sa.String(length=40), nullable=True),
        sa.Column("destination_context_json", sa.JSON(), nullable=True),
        sa.Column("downstream_usage_json", sa.JSON(), nullable=True),
        sa.Column("provider_error_json", sa.JSON(), nullable=True),
        sa.Column("provider_task_id", sa.String(length=120), nullable=True),
        sa.Column("pixelle_task_id", sa.String(length=120), nullable=True),
        sa.Column("prompt_hash", sa.String(length=64), nullable=True),
        sa.Column("is_latest", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("storage_status", sa.String(length=30), nullable=False, server_default="persisted"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_image_assets_task", "image_creation_assets", ["task_id"])
    op.create_index("idx_image_assets_status", "image_creation_assets", ["status"])
    op.create_index("idx_image_assets_destination", "image_creation_assets", ["destination_role"])
    op.create_index("idx_image_assets_series_episode", "image_creation_assets", ["series_id", "episode_id"])
    op.create_index("idx_image_assets_group", "image_creation_assets", ["group_id"])
    op.create_index("idx_image_assets_source", "image_creation_assets", ["source_asset_id"])
    op.create_index("idx_image_assets_latest", "image_creation_assets", ["is_latest"])
    op.create_unique_constraint("uq_image_asset_group_slot_version", "image_creation_assets", ["task_id", "group_id", "group_index", "version"])

    op.create_table(
        "image_creation_review_records",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("asset_id", sa.String(length=36), sa.ForeignKey("image_creation_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.String(length=36), sa.ForeignKey("image_creation_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("review_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("criteria_json", sa.JSON(), nullable=True),
        sa.Column("issues_json", sa.JSON(), nullable=True),
        sa.Column("reviewer_user_id", sa.String(length=36), nullable=True),
        sa.Column("model_trace_json", sa.JSON(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("asset_version", sa.Integer(), nullable=True),
        sa.Column("is_latest_asset_review", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_image_review_asset", "image_creation_review_records", ["asset_id"])
    op.create_index("idx_image_review_task", "image_creation_review_records", ["task_id"])
    op.create_index("idx_image_review_status", "image_creation_review_records", ["status"])
    op.create_index("idx_image_review_latest", "image_creation_review_records", ["asset_id", "asset_version", "is_latest_asset_review"])


def downgrade() -> None:
    op.drop_table("image_creation_review_records")
    op.drop_table("image_creation_assets")
    op.drop_table("image_creation_tasks")
```

Current repository head is `e5f6a7b8c9d0_add_agency_expert_invocations.py`; keep `down_revision = "e5f6a7b8c9d0"` unless another migration lands before implementation starts.

- [ ] **Step 5: Run model tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_image_creation_models.py -q
```

Expected: both tests pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add server/app/db_models.py server/alembic/versions/f6a7b8c9d0e1_image_creation_workbench.py server/tests/test_image_creation_models.py
git commit -m "feat: add image creation persistence models"
```

---

### Task 3: Pixelle Standalone Image Create Contract

**Files:**
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\pixelle_stage_client.py`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_pixelle_stage_client.py`
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_creation_pixelle_client.py`
- Modify: `D:\devWorkspace\Pixelle-Video\api\schemas\stages.py`
- Modify: `D:\devWorkspace\Pixelle-Video\api\routers\stages.py`
- Modify: `D:\devWorkspace\Pixelle-Video\api\services\ark_plan_v3.py`
- Modify: `D:\devWorkspace\Pixelle-Video\api\tasks\models.py`
- Create: `D:\devWorkspace\Pixelle-Video\tests\test_stage_image_create.py`

- [ ] **Step 1: Write dy_auto Pixelle client test**

Create `server/tests/test_image_creation_pixelle_client.py`:

```python
import pytest

from app.services.pixelle_stage_client import submit_image_create


@pytest.mark.asyncio
async def test_submit_image_create_calls_standalone_image_endpoint(monkeypatch):
    calls = []

    async def fake_request(method, path, db=None, **kwargs):
        calls.append((method, path, kwargs["json"]))
        return {"ok": True, "stage_task_id": "stage-image-create"}

    monkeypatch.setattr("app.services.pixelle_stage_client._pixelle_request", fake_request)

    result = await submit_image_create(
        db=None,
        external_task_id="task-1",
        mode="multi_reference_to_image_set",
        capability_key="multi_reference_to_image_set",
        output_mode="image_set",
        prompt="prompt",
        negative_prompt="",
        source_image_url="",
        reference_images=[{"url": "http://example.test/a.png", "role": "character"}],
        count=6,
        size="3K",
        output_format="png",
        response_format="url",
        provider_options={"sequential_image_generation": "auto", "max_images": 6},
        model_config={"provider": "seedance", "api_key": "secret"},
        context={"series_id": "series-1"},
    )

    assert result["stage_task_id"] == "stage-image-create"
    assert calls[0][0] == "POST"
    assert calls[0][1] == "/api/stages/images/create"
    assert calls[0][2]["external_task_id"] == "task-1"
    assert calls[0][2]["mode"] == "multi_reference_to_image_set"
```

- [ ] **Step 2: Run dy_auto Pixelle client test and confirm failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_image_creation_pixelle_client.py -q
```

Expected: import failure for `submit_image_create`.

- [ ] **Step 3: Implement `submit_image_create`**

Append to `server/app/services/pixelle_stage_client.py`:

```python
async def submit_image_create(
    db: Session | None,
    external_task_id: str,
    mode: str,
    capability_key: str,
    output_mode: str,
    prompt: str,
    negative_prompt: str = "",
    source_image_url: str = "",
    reference_images: list[dict] | None = None,
    count: int = 1,
    size: str | None = None,
    output_format: str | None = None,
    response_format: str | None = None,
    provider_options: dict | None = None,
    model_config: dict | None = None,
    context: dict | None = None,
) -> dict:
    if not model_config:
        raise ValueError("submit_image_create requires a non-empty model_config")
    payload = {
        "external_task_id": external_task_id,
        "mode": mode,
        "capability_key": capability_key,
        "output_mode": output_mode,
        "prompt": prompt,
        "negative_prompt": negative_prompt or "",
        "source_image_url": source_image_url or "",
        "reference_images": reference_images or [],
        "count": count,
        "size": size,
        "output_format": output_format,
        "response_format": response_format,
        "provider_options": provider_options or {},
        "model_config": model_config,
        "context": context or {},
    }
    return await _pixelle_request("POST", "/api/stages/images/create", db, json=payload)
```

- [ ] **Step 4: Write Pixelle schema/router tests**

Create `D:\devWorkspace\Pixelle-Video\tests\test_stage_image_create.py`:

```python
from fastapi.testclient import TestClient

from api.app import app


def test_stage_image_create_accepts_mock_provider():
    client = TestClient(app)
    payload = {
        "external_task_id": "task-1",
        "mode": "text_to_image",
        "capability_key": "text_to_image",
        "output_mode": "single",
        "prompt": "rainy street",
        "negative_prompt": "",
        "reference_images": [],
        "source_image_url": "",
        "count": 1,
        "size": "3K",
        "output_format": "png",
        "response_format": "url",
        "provider_options": {},
        "model_config": {"provider": "mock", "model": "mock-image"},
        "context": {"series_id": "series-1"},
    }

    resp = client.post("/api/stages/images/create", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["stage_task_id"]


def test_stage_image_create_rejects_empty_prompt():
    client = TestClient(app)
    payload = {
        "external_task_id": "task-1",
        "mode": "text_to_image",
        "capability_key": "text_to_image",
        "output_mode": "single",
        "prompt": "",
        "model_config": {"provider": "mock"},
    }

    resp = client.post("/api/stages/images/create", json=payload)

    assert resp.status_code == 400
```

- [ ] **Step 5: Add Pixelle task type**

In `D:\devWorkspace\Pixelle-Video\api\tasks\models.py`, extend `TaskType`:

```python
class TaskType(str, Enum):
    """Task type"""
    VIDEO_GENERATION = "video_generation"
    IMAGE_BATCH = "image_batch"
    IMAGE_CREATE = "image_create"
    VIDEO_BATCH = "video_batch"
    COMPOSE = "compose"
```

- [ ] **Step 6: Add Pixelle schemas**

In `D:\devWorkspace\Pixelle-Video\api\schemas\stages.py`, add:

```python
class ImageReference(BaseModel):
    url: str
    role: str = "reference"
    asset_id: str | None = None


class ImageCreateRequest(BaseModel):
    external_task_id: str
    mode: str
    capability_key: str
    output_mode: str = "single"
    prompt: str
    negative_prompt: str = ""
    reference_images: list[ImageReference] = Field(default_factory=list)
    source_image_url: str = ""
    count: int = 1
    size: str | None = None
    output_format: str | None = None
    response_format: str | None = None
    watermark: bool | None = None
    provider_options: dict[str, Any] = Field(default_factory=dict)
    stage_model_config: dict[str, Any] = Field(default_factory=dict, alias="model_config")
    context: dict[str, Any] = Field(default_factory=dict)

    class Config:
        populate_by_name = True
```

Update imports in `D:\devWorkspace\Pixelle-Video\api\routers\stages.py` to include `ImageCreateRequest`.

- [ ] **Step 7: Add Seedream image create helper**

In `D:\devWorkspace\Pixelle-Video\api\services\ark_plan_v3.py`, add:

```python
def _seedream_image_values(reference_images: list[dict[str, Any]], source_image_url: str) -> str | list[str] | None:
    values: list[str] = []
    if source_image_url:
        values.append(source_image_url)
    for item in reference_images or []:
        url = str(item.get("url") or "").strip()
        if url:
            values.append(url)
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return values


def extract_seedream_image_urls(data: dict[str, Any]) -> list[str]:
    output_items = data.get("data") if isinstance(data.get("data"), list) else [data]
    urls: list[str] = []
    for item in output_items:
        if isinstance(item, dict):
            urls.append(_extract_image_url(item))
    return [url for url in urls if url]


async def create_seedream_images(
    *,
    prompt: str,
    model_config: dict[str, Any],
    mode: str,
    negative_prompt: str = "",
    reference_images: list[dict[str, Any]] | None = None,
    source_image_url: str = "",
    count: int = 1,
    size: str | None = None,
    output_format: str | None = None,
    response_format: str | None = None,
    provider_options: dict[str, Any] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    options = dict(provider_options or {})
    sequential = options.pop("sequential_image_generation", None)
    if sequential is None:
        sequential = "auto" if mode.endswith("_set") else "disabled"
    payload: dict[str, Any] = {
        "model": _model_name(model_config, SEEDREAM_IMAGE_MODEL),
        "prompt": prompt,
        "sequential_image_generation": sequential,
    }
    image_value = _seedream_image_values(reference_images or [], source_image_url)
    if image_value:
        payload["image"] = image_value
    if size:
        payload["size"] = size
    if output_format:
        payload["output_format"] = output_format
    if response_format:
        payload["response_format"] = response_format
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt
    if count:
        payload["sequential_image_generation_options"] = {"max_images": count}
    payload.update(options)

    async with _client(model_config, transport) as client:
        data = await _json_or_error(await client.post(ARK_PLAN_V3_IMAGE_PATH, json=payload), "image generation")

    return {"raw_response": data, "payload": payload, "image_urls": extract_seedream_image_urls(data)}
```

- [ ] **Step 8: Add Pixelle `/images/create` route**

In `D:\devWorkspace\Pixelle-Video\api\routers\stages.py`, add before the existing `/images/batch` route:

```python
async def _run_image_create(request: ImageCreateRequest, task_id: str) -> dict:
    task_manager.update_progress(task_id, 0, max(request.count, 1), "Creating image assets")
    provider = request.stage_model_config.get("provider")
    assets: list[dict] = []
    if provider == "mock":
        for index in range(1, request.count + 1):
            local_path = f"output/{task_id}/image-{index}.png"
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            Path(local_path).write_bytes(_MINIMAL_PNG)
            assets.append(StageAsset(
                frame_id=f"image-{index}",
                asset_type="image",
                url=_public_file_url(local_path),
                local_path=local_path,
                metadata={**request.context, "group_id": task_id, "group_index": index, "mode": request.mode},
            ).model_dump())
            task_manager.update_progress(task_id, index, request.count, f"Created image {index}")
        return {"assets": assets}

    if provider == "seedance":
        result = await create_seedream_images(
            prompt=request.prompt,
            model_config=request.stage_model_config,
            mode=request.mode,
            negative_prompt=request.negative_prompt,
            reference_images=[item.model_dump() for item in request.reference_images],
            source_image_url=request.source_image_url,
            count=request.count,
            size=request.size,
            output_format=request.output_format,
            response_format=request.response_format,
            provider_options={**request.provider_options, "watermark": request.watermark}
            if request.watermark is not None
            else request.provider_options,
        )
        raw = result["raw_response"]
        image_urls = result.get("image_urls") or []
        for index, url in enumerate(image_urls, start=1):
            assets.append(StageAsset(
                frame_id=f"image-{index}",
                asset_type="image",
                url=url,
                local_path=url,
                metadata={**request.context, "group_id": task_id, "group_index": index, "raw_response": raw},
            ).model_dump())
        task_manager.update_progress(task_id, len(assets), max(request.count, 1), "Created Seedream images")
        return {"assets": assets}

    raise ValueError(f"Unsupported image create provider: {provider}")


@router.post("/images/create", response_model=StageTaskResponse)
async def image_create(request: ImageCreateRequest):
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt is required")
    task = task_manager.create_task(TaskType.IMAGE_CREATE, request.model_dump(exclude={"stage_model_config"}))
    await task_manager.execute_task(task.task_id, _run_image_create, request, task.task_id)
    return StageTaskResponse(ok=True, stage_task_id=task.task_id, assets=[], logs=[])
```

- [ ] **Step 9: Run Pixelle tests**

Run:

```powershell
cd D:\devWorkspace\Pixelle-Video
pytest tests/test_stage_image_create.py -q
```

Expected: both tests pass.

- [ ] **Step 10: Run dy_auto Pixelle client tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_pixelle_stage_client.py tests/test_image_creation_pixelle_client.py -q
```

Expected: all selected tests pass.

- [ ] **Step 11: Commit both repos**

Run in dy_auto:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add server/app/services/pixelle_stage_client.py server/tests/test_pixelle_stage_client.py server/tests/test_image_creation_pixelle_client.py
git commit -m "feat: add Pixelle standalone image creation client"
```

Run in Pixelle-Video:

```powershell
cd D:\devWorkspace\Pixelle-Video
git add api/schemas/stages.py api/routers/stages.py api/services/ark_plan_v3.py api/tasks/models.py tests/test_stage_image_create.py
git commit -m "feat: add standalone image creation stage"
```

---

### Task 4: Backend Image Creation Service And API

**Files:**
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_creation_errors.py`
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_creation_storage.py`
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_creation_service.py`
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\app\routers\image_creation.py`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\main.py`
- Test: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_creation_api.py`

- [ ] **Step 1: Write API tests**

Create `server/tests/test_image_creation_api.py`:

```python
from uuid import uuid4

from app.db_models import AIModel, ImageCreationAsset
from app.services.crypto import encrypt


def _seed_image_model(db, scene_key="image_generation", capabilities=None):
    model = AIModel(
        name=f"{scene_key}-test",
        model_type="image",
        provider="mock",
        base_url="http://pixelle.test",
        api_key=encrypt("secret"),
        model_name=f"mock-image-{uuid4().hex}",
        enabled=True,
        config_json={
            "scene_key": scene_key,
            "capabilities": capabilities or {"text_to_image": True},
            "limits": {"max_output_images": 15, "max_reference_images": 14},
        },
    )
    db.add(model)
    db.commit()
    return model


def test_create_text_to_image_task_submits_pixelle(client, db_session, monkeypatch):
    _seed_image_model(db_session)
    calls = []

    async def fake_submit(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "stage_task_id": "stage-1"}

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "雨夜街头",
        "count": 1,
        "size": "3K",
        "idempotency_key": "idem-1",
        "destination_role": "image_to_video_input",
        "cost_confirmation": True,
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["task"]["pixelle_task_id"] == "stage-1"
    assert calls[0]["mode"] == "text_to_image"
    assert calls[0]["context"]["destination_role"] == "image_to_video_input"


def test_reusing_idempotency_key_with_different_request_returns_conflict(client, db_session, monkeypatch):
    _seed_image_model(db_session)

    async def fake_submit(**kwargs):
        return {"ok": True, "stage_task_id": "stage-1"}

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    first = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "雨夜街头",
        "count": 1,
        "idempotency_key": "same-key",
        "cost_confirmation": True,
    })
    second = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "晴天街头",
        "count": 1,
        "idempotency_key": "same-key",
        "cost_confirmation": True,
    })

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error_code"] == "IMAGE_TASK_CONFLICT"


def test_image_to_image_requires_source_image(client, db_session, monkeypatch):
    _seed_image_model(db_session, scene_key="image_editing", capabilities={"image_to_image": True})

    async def fake_submit(**kwargs):
        raise AssertionError("submit_image_create should not run when the source image is missing")

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "image_to_image",
        "prompt": "make the lighting warmer",
        "count": 1,
        "cost_confirmation": True,
    })

    assert resp.status_code == 400
    assert resp.json()["error_code"] == "SOURCE_IMAGE_REQUIRED"


def test_multi_reference_respects_reference_count(client, db_session, monkeypatch):
    _seed_image_model(db_session, scene_key="image_editing", capabilities={"multi_reference_to_image": True})

    async def fake_submit(**kwargs):
        raise AssertionError("submit_image_create should not run when references are insufficient")

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "multi_reference_to_image",
        "prompt": "merge style and character",
        "reference_images": [{"url": "http://example.test/a.png"}],
        "count": 1,
        "cost_confirmation": True,
    })

    assert resp.status_code == 400
    assert resp.json()["error_code"] == "REFERENCE_IMAGES_REQUIRED"


def test_list_assets_filters_approved_destination(client, db_session):
    task_resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "asset seed",
        "count": 1,
        "idempotency_key": "list-seed",
        "cost_confirmation": True,
    })
    if task_resp.status_code != 200:
        _seed_image_model(db_session)
        task_resp = client.post("/api/image-creation/tasks", json={
            "mode": "text_to_image",
            "prompt": "asset seed",
            "count": 1,
            "idempotency_key": "list-seed",
            "cost_confirmation": True,
        })
    task_id = task_resp.json()["task"]["id"]
    asset = ImageCreationAsset(
        task_id=task_id,
        asset_type="image",
        url="http://example.test/approved.png",
        status="approved",
        version=1,
        destination_role="image_to_video_input",
        prompt_hash="hash",
        is_latest=True,
        storage_status="persisted",
    )
    db_session.add(asset)
    db_session.commit()

    resp = client.get("/api/image-creation/assets?status=approved&destination_role=image_to_video_input")

    assert resp.status_code == 200
    assert resp.json()["assets"][0]["id"] == asset.id
```

- [ ] **Step 2: Run API tests and confirm failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_image_creation_api.py -q
```

Expected: route not found or import failure.

- [ ] **Step 3: Add named errors**

Create `server/app/services/image_creation_errors.py`:

```python
from fastapi import HTTPException


def image_error(
    status_code: int,
    error_code: str,
    message: str,
    repair_action: str,
    repair_route: str | None = None,
    retryable: bool = True,
    affected_ids: list[str] | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "ok": False,
            "error_code": error_code,
            "message": message,
            "repair_action": repair_action,
            "repair_route": repair_route,
            "retryable": retryable,
            "affected_ids": affected_ids or [],
        },
    )
```

- [ ] **Step 4: Add storage helpers**

Create `server/app/services/image_creation_storage.py`:

```python
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from fastapi import UploadFile


IMAGE_CREATION_ROOT = Path(__file__).resolve().parents[1] / "static" / "image-creation"
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff", "image/gif"}
MAX_UPLOAD_BYTES = 30 * 1024 * 1024


def ensure_storage_dirs() -> None:
    for name in ("uploads", "outputs", "thumbs"):
        (IMAGE_CREATION_ROOT / name).mkdir(parents=True, exist_ok=True)


async def save_upload(file: UploadFile, public_base_url: str) -> dict:
    ensure_storage_dirs()
    content = await file.read()
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("SOURCE_IMAGE_UNSUPPORTED_TYPE")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("SOURCE_IMAGE_TOO_LARGE")
    digest = hashlib.sha256(content).hexdigest()
    suffix = Path(file.filename or "upload.png").suffix.lower() or ".png"
    local_path = IMAGE_CREATION_ROOT / "uploads" / f"{digest}{suffix}"
    local_path.write_bytes(content)
    return {
        "url": f"{public_base_url.rstrip('/')}/static/image-creation/uploads/{local_path.name}",
        "local_path": str(local_path),
        "checksum": digest,
        "size_bytes": len(content),
    }


def checksum_file(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def configured_public_base_url() -> str:
    return os.getenv("DY_AUTO_PUBLIC_BASE_URL", "http://127.0.0.1:8000")
```

- [ ] **Step 5: Add service functions**

Create `server/app/services/image_creation_service.py`:

```python
from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import ImageCreationAsset, ImageCreationReviewRecord, ImageCreationTask
from app.services.image_creation_errors import image_error
from app.services.pixelle_stage_client import get_stage_task, submit_image_create
from app.services.runtime_model_config import (
    RuntimeModelConfigError,
    redact_runtime_model_config,
    resolve_image_model_for_capability,
)


MODE_TO_SCENE_CAPABILITY = {
    "text_to_image": ("image_generation", "text_to_image", "single"),
    "image_to_image": ("image_editing", "image_to_image", "single"),
    "multi_reference_to_image": ("image_editing", "multi_reference_to_image", "single"),
    "text_to_image_set": ("image_generation", "text_to_image_set", "image_set"),
    "image_to_image_set": ("image_editing", "image_to_image_set", "image_set"),
    "multi_reference_to_image_set": ("image_editing", "multi_reference_to_image_set", "image_set"),
}
DESTINATION_ROLES = {"character_anchor", "scene_reference", "style_reference", "storyboard_frame", "image_to_video_input"}


def normalized_request_hash(payload: dict[str, Any]) -> str:
    clean = {key: value for key, value in payload.items() if key not in {"idempotency_key", "cost_confirmation"}}
    encoded = json.dumps(clean, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_payload(payload: dict[str, Any]) -> tuple[str, str, str]:
    mode = payload.get("mode")
    if mode not in MODE_TO_SCENE_CAPABILITY:
        raise image_error(400, "IMAGE_MODE_UNSUPPORTED", f"Unsupported image mode: {mode}", "Choose a supported image mode.")
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise image_error(400, "IMAGE_PROMPT_REQUIRED", "Prompt is required.", "Enter a prompt.")
    destination_role = payload.get("destination_role")
    if destination_role and destination_role not in DESTINATION_ROLES:
        raise image_error(400, "DOWNSTREAM_DESTINATION_INVALID", "Unsupported destination role.", "Pick a supported destination or clear it.")
    return MODE_TO_SCENE_CAPABILITY[mode]


def _image_reference_count(payload: dict[str, Any]) -> int:
    count = len(payload.get("reference_images") or [])
    if (payload.get("source") or {}).get("url") or (payload.get("source") or {}).get("asset_id"):
        count += 1
    return count


def _validate_provider_limits(payload: dict[str, Any], model_config: dict[str, Any]) -> None:
    mode = payload["mode"]
    source = payload.get("source") or {}
    references = payload.get("reference_images") or []
    reference_count = _image_reference_count(payload)
    output_count = int(payload.get("count") or 1)
    limits = ((model_config.get("config") or {}).get("limits") or {})
    max_reference_images = int(limits.get("max_reference_images") or 14)
    max_output_images = int(limits.get("max_output_images") or 15)
    max_reference_plus_output = int(limits.get("max_reference_plus_output_images") or 15)

    if output_count < 1 or output_count > max_output_images:
        raise image_error(400, "IMAGE_OUTPUT_COUNT_INVALID", "Requested image count exceeds model limits.", "Lower the output count or choose another model.")
    if output_count > 1 and not mode.endswith("_set"):
        raise image_error(400, "IMAGE_OUTPUT_MODE_INVALID", "Multiple outputs require an image-set mode.", "Switch to a group image mode or reduce count to 1.")
    if mode in {"image_to_image", "image_to_image_set"} and not (source.get("url") or source.get("asset_id")):
        raise image_error(400, "SOURCE_IMAGE_REQUIRED", "Image-to-image mode requires a source image.", "Upload or select a source image.")
    if mode.startswith("multi_reference") and len(references) < 2:
        raise image_error(400, "REFERENCE_IMAGES_REQUIRED", "Multi-reference mode requires at least two reference images.", "Add more reference images.")
    if reference_count > max_reference_images or reference_count + output_count > max_reference_plus_output:
        raise image_error(400, "REFERENCE_LIMIT_EXCEEDED", "Reference images and output count exceed model limits.", "Remove references or reduce output count.")


def _estimate_cost(payload: dict[str, Any]) -> dict[str, Any]:
    count = int(payload.get("count") or 1)
    return {"amount": round(count * 0.01, 4), "currency": "CNY", "estimate_source": "local_policy"}


async def create_image_task(db: Session, payload: dict[str, Any]) -> ImageCreationTask:
    scene_key, capability_key, output_mode = _validate_payload(payload)
    request_hash = normalized_request_hash(payload)
    idempotency_key = payload.get("idempotency_key")
    if idempotency_key:
        existing = db.query(ImageCreationTask).filter(ImageCreationTask.idempotency_key == idempotency_key).first()
        if existing:
            if existing.request_hash != request_hash:
                raise image_error(409, "IMAGE_TASK_CONFLICT", "Idempotency key was reused for a different image request.", "Use a new task or restore the original request.", retryable=False)
            return existing

    estimated_cost = _estimate_cost(payload)
    if estimated_cost["amount"] > 1 and not payload.get("cost_confirmation"):
        raise image_error(409, "IMAGE_COST_CONFIRMATION_REQUIRED", "Image request cost requires confirmation.", "Confirm the task cost or reduce count/options.")

    try:
        model_config = resolve_image_model_for_capability(db, scene_key, capability_key, payload.get("model_id"))
    except RuntimeModelConfigError as exc:
        raise image_error(400, "IMAGE_CAPABILITY_UNSUPPORTED", str(exc), "Choose a compatible model or change mode.", "/ai-config") from exc
    _validate_provider_limits(payload, model_config)
    provider_options = dict(payload.get("provider_options") or {})
    if payload.get("watermark") is not None:
        provider_options.setdefault("watermark", payload.get("watermark"))

    task = ImageCreationTask(
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        mode=payload["mode"],
        output_mode=output_mode,
        capability_key=capability_key,
        status="queued",
        series_id=payload.get("series_id"),
        episode_id=payload.get("episode_id"),
        prompt=payload["prompt"],
        negative_prompt=payload.get("negative_prompt") or "",
        source_type=(payload.get("source") or {}).get("type"),
        source_url=(payload.get("source") or {}).get("url"),
        source_asset_id=(payload.get("source") or {}).get("asset_id"),
        reference_images_json=payload.get("reference_images") or [],
        destination_role=payload.get("destination_role"),
        destination_context_json=payload.get("destination_context") or {},
        size=payload.get("size"),
        count=int(payload.get("count") or 1),
        output_format=payload.get("output_format"),
        response_format=payload.get("response_format"),
        watermark=payload.get("watermark"),
        provider_options_json=provider_options,
        estimated_cost_json=estimated_cost,
        cost_status="confirmed",
        storage_status="pending",
        model_scene_key=scene_key,
        model_trace_json=redact_runtime_model_config(model_config),
    )
    db.add(task)
    db.flush()
    result = await submit_image_create(
        db=db,
        external_task_id=task.id,
        mode=task.mode,
        capability_key=task.capability_key,
        output_mode=task.output_mode,
        prompt=task.prompt,
        negative_prompt=task.negative_prompt or "",
        source_image_url=task.source_url or "",
        reference_images=task.reference_images_json or [],
        count=task.count,
        size=task.size,
        output_format=task.output_format,
        response_format=task.response_format,
        provider_options=task.provider_options_json or {},
        model_config=model_config,
        context={
            "series_id": task.series_id,
            "episode_id": task.episode_id,
            "source_asset_id": task.source_asset_id,
            "destination_role": task.destination_role,
            "destination_context": task.destination_context_json or {},
        },
    )
    task.pixelle_task_id = result.get("stage_task_id")
    task.status = "running"
    db.commit()
    db.refresh(task)
    return task


def task_payload(task: ImageCreationTask) -> dict[str, Any]:
    return {
        "id": task.id,
        "mode": task.mode,
        "capability_key": task.capability_key,
        "output_mode": task.output_mode,
        "status": task.status,
        "model_scene_key": task.model_scene_key,
        "pixelle_task_id": task.pixelle_task_id,
        "cost_status": task.cost_status,
        "estimated_cost": task.estimated_cost_json or {},
        "destination_role": task.destination_role,
        "destination_context": task.destination_context_json or {},
    }


def asset_payload(asset: ImageCreationAsset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "task_id": asset.task_id,
        "series_id": asset.series_id,
        "episode_id": asset.episode_id,
        "asset_type": asset.asset_type,
        "url": asset.url,
        "local_path": asset.local_path,
        "thumbnail_url": asset.thumbnail_url,
        "status": asset.status,
        "version": asset.version,
        "source_asset_id": asset.source_asset_id,
        "source_url": asset.source_url,
        "reference_images": asset.reference_images_json or [],
        "group_id": asset.group_id,
        "group_index": asset.group_index,
        "destination_role": asset.destination_role,
        "destination_context": asset.destination_context_json or {},
        "downstream_usage": asset.downstream_usage_json or {},
        "metadata": asset.metadata_json or {},
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
        "updated_at": asset.updated_at.isoformat() if asset.updated_at else None,
    }
```

- [ ] **Step 6: Add sync, asset list, review, and edit helpers**

Append to `server/app/services/image_creation_service.py`:

```python
async def sync_image_task(db: Session, task_id: str) -> ImageCreationTask:
    task = db.query(ImageCreationTask).filter(ImageCreationTask.id == task_id).first()
    if not task:
        raise image_error(404, "IMAGE_TASK_NOT_FOUND", "Image creation task not found.", "Reload the task list.", retryable=False)
    if not task.pixelle_task_id:
        raise image_error(400, "PIXELLE_TASK_PENDING", "Pixelle task is not available yet.", "Sync again after task submission completes.")
    status = await get_stage_task(db, task.pixelle_task_id)
    if status.get("status") not in {"completed", "success", "succeeded", "done"}:
        task.status = "failed" if status.get("status") == "failed" else "running"
        task.error_message = status.get("error")
        db.commit()
        return task

    assets = status.get("assets") or []
    failures = 0
    for index, item in enumerate(assets, start=1):
        if item.get("status") == "failed" or item.get("error"):
            failures += 1
            continue
        metadata = item.get("metadata") or {}
        group_id = metadata.get("group_id") or item.get("group_id") or task.pixelle_task_id
        group_index = metadata.get("group_index") or item.get("group_index") or index
        existing = db.query(ImageCreationAsset).filter(
            ImageCreationAsset.task_id == task.id,
            ImageCreationAsset.group_id == str(group_id),
            ImageCreationAsset.group_index == int(group_index),
            ImageCreationAsset.version == 1,
        ).first()
        if existing:
            continue
        asset = ImageCreationAsset(
            task_id=task.id,
            series_id=task.series_id,
            episode_id=task.episode_id,
            asset_type="image",
            url=item.get("url") or "",
            local_path=item.get("local_path") or "",
            thumbnail_url=item.get("thumbnail_url"),
            status="review_pending",
            version=1,
            source_asset_id=task.source_asset_id,
            source_url=task.source_url,
            reference_images_json=task.reference_images_json or [],
            group_id=str(group_id),
            group_index=int(group_index),
            destination_role=metadata.get("destination_role") or task.destination_role,
            destination_context_json=metadata.get("destination_context") or task.destination_context_json or {},
            provider_task_id=item.get("provider_task_id"),
            pixelle_task_id=task.pixelle_task_id,
            prompt_hash=task.request_hash,
            is_latest=True,
            metadata_json=metadata,
            storage_status="persisted",
        )
        db.add(asset)
    task.status = "completed_with_warnings" if failures else "completed"
    task.storage_status = "persisted"
    task.usage_json = status.get("usage") or {}
    task.completed_at = bj_now()
    db.commit()
    db.refresh(task)
    return task


def list_image_assets(
    db: Session,
    status: str | None = None,
    destination_role: str | None = None,
    series_id: str | None = None,
    episode_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[ImageCreationAsset], int]:
    query = db.query(ImageCreationAsset)
    if status:
        query = query.filter(ImageCreationAsset.status == status)
    if destination_role:
        query = query.filter(ImageCreationAsset.destination_role == destination_role)
    if series_id:
        query = query.filter(ImageCreationAsset.series_id == series_id)
    if episode_id:
        query = query.filter(ImageCreationAsset.episode_id == episode_id)
    total = query.count()
    safe_page = max(page, 1)
    safe_page_size = min(max(page_size, 1), 100)
    rows = (
        query.order_by(ImageCreationAsset.created_at.desc())
        .offset((safe_page - 1) * safe_page_size)
        .limit(safe_page_size)
        .all()
    )
    return rows, total


def review_image_asset(db: Session, asset_id: str, action: str, comment: str = "", reviewer_user_id: str | None = None, asset_version: int | None = None) -> ImageCreationAsset:
    asset = db.query(ImageCreationAsset).filter(ImageCreationAsset.id == asset_id).first()
    if not asset:
        raise image_error(404, "SOURCE_ASSET_NOT_FOUND", "Image asset not found.", "Pick another asset.", retryable=False)
    if asset_version is not None and asset.version != asset_version:
        raise image_error(409, "STALE_ASSET_VERSION", "This review targets an older asset version.", "Reload latest asset.")
    if action not in {"approve", "reject"}:
        raise image_error(400, "IMAGE_REVIEW_ACTION_INVALID", "Review action must be approve or reject.", "Choose approve or reject.")
    asset.status = "approved" if action == "approve" else "rejected"
    db.query(ImageCreationReviewRecord).filter(ImageCreationReviewRecord.asset_id == asset.id).update({"is_latest_asset_review": False})
    db.add(ImageCreationReviewRecord(
        task_id=asset.task_id,
        asset_id=asset.id,
        review_type="human",
        status=asset.status,
        comment=comment,
        reviewer_user_id=reviewer_user_id,
        asset_version=asset.version,
        is_latest_asset_review=True,
    ))
    db.commit()
    db.refresh(asset)
    return asset
```

- [ ] **Step 7: Add router**

Create `server/app/routers/image_creation.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.image_creation_service import (
    asset_payload,
    create_image_task,
    list_image_assets,
    review_image_asset,
    sync_image_task,
    task_payload,
)
from app.services.image_creation_storage import configured_public_base_url, save_upload

router = APIRouter(prefix="/api/image-creation", tags=["image-creation"])


class CreateImageTaskRequest(BaseModel):
    mode: str
    prompt: str
    negative_prompt: str = ""
    source: dict | None = None
    reference_images: list[dict] = Field(default_factory=list)
    size: str | None = None
    count: int = 1
    output_format: str | None = None
    response_format: str | None = None
    watermark: bool | None = None
    provider_options: dict = Field(default_factory=dict)
    idempotency_key: str | None = None
    destination_role: str | None = None
    destination_context: dict = Field(default_factory=dict)
    cost_confirmation: bool = False
    series_id: str | None = None
    episode_id: str | None = None
    model_id: str | None = None


class ReviewImageAssetRequest(BaseModel):
    action: str
    comment: str = ""
    asset_version: int | None = None


@router.post("/uploads")
async def upload_image(file: UploadFile = File(...)):
    saved = await save_upload(file, configured_public_base_url())
    return {"ok": True, **saved}


@router.post("/tasks")
async def create_task(body: CreateImageTaskRequest, db: Session = Depends(get_db)):
    task = await create_image_task(db, body.model_dump())
    return {"ok": True, "task": task_payload(task), "assets": [], "reviews": []}


@router.get("/tasks/{task_id}")
async def read_task(task_id: str, db: Session = Depends(get_db)):
    from app.db_models import ImageCreationAsset, ImageCreationTask
    task = db.query(ImageCreationTask).filter(ImageCreationTask.id == task_id).first()
    if not task:
        from app.services.image_creation_errors import image_error
        raise image_error(404, "IMAGE_TASK_NOT_FOUND", "Image creation task not found.", "Reload the task list.", retryable=False)
    assets = db.query(ImageCreationAsset).filter(ImageCreationAsset.task_id == task.id).all()
    return {"ok": True, "task": task_payload(task), "assets": [asset_payload(asset) for asset in assets], "reviews": []}


@router.post("/tasks/{task_id}/sync")
async def sync_task(task_id: str, db: Session = Depends(get_db)):
    task = await sync_image_task(db, task_id)
    return {"ok": True, "task": task_payload(task)}


@router.get("/assets")
async def assets(
    status: str | None = Query(None),
    destination_role: str | None = Query(None),
    series_id: str | None = Query(None),
    episode_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    rows, total = list_image_assets(
        db,
        status=status,
        destination_role=destination_role,
        series_id=series_id,
        episode_id=episode_id,
        page=page,
        page_size=page_size,
    )
    return {"ok": True, "assets": [asset_payload(row) for row in rows], "page": page, "page_size": page_size, "total": total}


@router.post("/assets/{asset_id}/review")
async def review_asset(asset_id: str, body: ReviewImageAssetRequest, db: Session = Depends(get_db)):
    asset = review_image_asset(db, asset_id, body.action, body.comment, asset_version=body.asset_version)
    return {"ok": True, "asset": asset_payload(asset)}
```

- [ ] **Step 8: Register router**

In `server/app/main.py`, update the router import:

```python
from app.routers import device, tasks, accounts, devices, auth, selectors, stats, content, account_groups, chains, settings, channels, prompt_templates, data, videos, pixelle, ai_config, characters, scenes, series, pipeline, audit, director, reference_data, dm_sequences, video_production, agency, image_creation
```

Add after `app.include_router(agency.router)`:

```python
app.include_router(image_creation.router)
```

- [ ] **Step 9: Run backend API tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_image_creation_api.py -q
```

Expected: selected tests pass.

- [ ] **Step 10: Commit**

Run:

```powershell
git add server/app/services/image_creation_errors.py server/app/services/image_creation_storage.py server/app/services/image_creation_service.py server/app/routers/image_creation.py server/app/main.py server/tests/test_image_creation_api.py
git commit -m "feat: add image creation backend API"
```

---

### Task 5: Mocked End-To-End Backend Flow And Downstream Guard

**Files:**
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_creation_service.py`
- Test: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_creation_mocked_e2e.py`

- [ ] **Step 1: Write mocked E2E tests**

Create `server/tests/test_image_creation_mocked_e2e.py`:

```python
from app.db_models import AIModel
from app.services.crypto import encrypt


def _model(db):
    row = AIModel(
        name="Mock image generation",
        model_type="image",
        provider="mock",
        base_url="http://pixelle.test",
        api_key=encrypt("secret"),
        model_name="mock-image",
        enabled=True,
        config_json={
            "scene_key": "image_generation",
            "capabilities": {"text_to_image": True, "text_to_image_set": True},
            "limits": {"max_output_images": 15, "max_reference_images": 14},
        },
    )
    db.add(row)
    db.commit()


def test_text_to_image_review_and_downstream_selector(client, db_session, monkeypatch):
    _model(db_session)

    async def fake_submit(**kwargs):
        return {"ok": True, "stage_task_id": "stage-1"}

    async def fake_status(db, stage_task_id):
        return {
            "ok": True,
            "status": "completed",
            "assets": [
                {
                    "asset_type": "image",
                    "url": "http://example.test/output.png",
                    "local_path": "output/output.png",
                    "metadata": {"group_id": "group-1", "group_index": 1},
                }
            ],
        }

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)
    monkeypatch.setattr("app.services.image_creation_service.get_stage_task", fake_status)

    create = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "雨夜街头",
        "count": 1,
        "idempotency_key": "e2e-1",
        "destination_role": "image_to_video_input",
        "cost_confirmation": True,
    })
    task_id = create.json()["task"]["id"]

    sync = client.post(f"/api/image-creation/tasks/{task_id}/sync")
    assert sync.status_code == 200
    assert sync.json()["task"]["status"] == "completed"

    assets = client.get("/api/image-creation/assets?status=review_pending")
    asset_id = assets.json()["assets"][0]["id"]

    review = client.post(f"/api/image-creation/assets/{asset_id}/review", json={"action": "approve", "asset_version": 1})
    assert review.status_code == 200

    selectable = client.get("/api/image-creation/assets?status=approved&destination_role=image_to_video_input")
    assert selectable.json()["assets"][0]["id"] == asset_id


def test_unapproved_asset_is_not_returned_for_approved_selector(client, db_session, monkeypatch):
    _model(db_session)

    async def fake_submit(**kwargs):
        return {"ok": True, "stage_task_id": "stage-2"}

    async def fake_status(db, stage_task_id):
        return {
            "ok": True,
            "status": "completed",
            "assets": [{"asset_type": "image", "url": "http://example.test/unapproved.png", "metadata": {"group_id": "g", "group_index": 1}}],
        }

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)
    monkeypatch.setattr("app.services.image_creation_service.get_stage_task", fake_status)

    create = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "待审图",
        "count": 1,
        "idempotency_key": "unapproved-1",
        "destination_role": "image_to_video_input",
        "cost_confirmation": True,
    })
    task_id = create.json()["task"]["id"]
    client.post(f"/api/image-creation/tasks/{task_id}/sync")

    selectable = client.get("/api/image-creation/assets?status=approved&destination_role=image_to_video_input")

    assert selectable.status_code == 200
    assert selectable.json()["assets"] == []
```

- [ ] **Step 2: Run mocked E2E tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_image_creation_mocked_e2e.py -q
```

Expected: tests pass after Task 4.

- [ ] **Step 3: Add edit-again endpoint**

Append route to `server/app/routers/image_creation.py`:

```python
@router.post("/assets/{asset_id}/edit")
async def edit_asset(asset_id: str, body: CreateImageTaskRequest, db: Session = Depends(get_db)):
    from app.db_models import ImageCreationAsset
    from app.services.image_creation_errors import image_error
    asset = db.query(ImageCreationAsset).filter(ImageCreationAsset.id == asset_id).first()
    if not asset:
        raise image_error(404, "SOURCE_ASSET_NOT_FOUND", "Image asset not found.", "Pick another asset.", retryable=False)
    payload = body.model_dump()
    payload["mode"] = "image_to_image"
    payload["source"] = {"type": "asset", "asset_id": asset.id, "url": asset.url}
    payload["series_id"] = payload.get("series_id") or asset.series_id
    payload["episode_id"] = payload.get("episode_id") or asset.episode_id
    task = await create_image_task(db, payload)
    asset.status = "regenerating"
    db.commit()
    return {"ok": True, "task": task_payload(task)}
```

- [ ] **Step 4: Add edit-again API test**

Append to `server/tests/test_image_creation_api.py`:

```python
def test_edit_again_creates_image_to_image_task(client, db_session, monkeypatch):
    _seed_image_model(db_session, scene_key="image_editing", capabilities={"image_to_image": True})

    async def fake_submit(**kwargs):
        return {"ok": True, "stage_task_id": "stage-edit"}

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)
    task = client.post("/api/image-creation/tasks", json={
        "mode": "image_to_image",
        "prompt": "初始修复",
        "source": {"type": "url", "url": "http://example.test/source.png"},
        "count": 1,
        "idempotency_key": "source-task",
        "cost_confirmation": True,
    }).json()["task"]
    asset = ImageCreationAsset(
        task_id=task["id"],
        asset_type="image",
        url="http://example.test/source.png",
        status="rejected",
        version=1,
        prompt_hash="source-hash",
        is_latest=True,
        storage_status="persisted",
    )
    db_session.add(asset)
    db_session.commit()

    resp = client.post(f"/api/image-creation/assets/{asset.id}/edit", json={
        "mode": "image_to_image",
        "prompt": "修复人物手部",
        "count": 1,
        "idempotency_key": "edit-again-1",
        "cost_confirmation": True,
    })

    assert resp.status_code == 200
    assert resp.json()["task"]["mode"] == "image_to_image"
```

- [ ] **Step 5: Run backend image creation suite**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_image_creation_models.py tests/test_image_creation_model_resolution.py tests/test_image_creation_pixelle_client.py tests/test_image_creation_api.py tests/test_image_creation_mocked_e2e.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add server/app/routers/image_creation.py server/app/services/image_creation_service.py server/tests/test_image_creation_api.py server/tests/test_image_creation_mocked_e2e.py
git commit -m "feat: add image creation review and edit flow"
```

---

### Task 6: Frontend API, Routing, Navigation, And Workbench Shell

**Files:**
- Create: `D:\devWorkspace\jsProjects\dy_auto\web\src\api\imageCreation.js`
- Create: `D:\devWorkspace\jsProjects\dy_auto\web\src\views\ImageCreationPage.vue`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\web\src\router\index.js`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\web\src\constants\navigation.js`
- Test: `D:\devWorkspace\jsProjects\dy_auto\web\src\__tests__\image-creation-api.test.js`
- Test: `D:\devWorkspace\jsProjects\dy_auto\web\src\__tests__\image-creation-page.test.js`
- Test: `D:\devWorkspace\jsProjects\dy_auto\web\src\__tests__\navigation.test.js`

- [ ] **Step 1: Write frontend API tests**

Create `web/src/__tests__/image-creation-api.test.js`:

```javascript
import { describe, expect, it, vi } from 'vitest'

vi.mock('../api/client.js', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

describe('imageCreation api', () => {
  it('creates image task through image creation endpoint', async () => {
    const client = (await import('../api/client.js')).default
    client.post.mockResolvedValueOnce({ data: { ok: true, task: { id: 'task-1' } } })
    const api = await import('../api/imageCreation.js')

    const result = await api.createImageTask({ mode: 'text_to_image', prompt: '雨夜街头' })

    expect(client.post).toHaveBeenCalledWith('/image-creation/tasks', { mode: 'text_to_image', prompt: '雨夜街头' })
    expect(result.task.id).toBe('task-1')
  })

  it('lists approved image-to-video assets', async () => {
    const client = (await import('../api/client.js')).default
    client.get.mockResolvedValueOnce({ data: { ok: true, assets: [{ id: 'asset-1' }] } })
    const api = await import('../api/imageCreation.js')

    const result = await api.listImageAssets({ status: 'approved', destination_role: 'image_to_video_input' })

    expect(client.get).toHaveBeenCalledWith('/image-creation/assets', { params: { status: 'approved', destination_role: 'image_to_video_input' } })
    expect(result.assets[0].id).toBe('asset-1')
  })
})
```

- [ ] **Step 2: Implement frontend API client**

Create `web/src/api/imageCreation.js`:

```javascript
import client from './client'

export async function uploadImageSource(formData) {
  const { data } = await client.post('/image-creation/uploads', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function createImageTask(payload) {
  const { data } = await client.post('/image-creation/tasks', payload)
  return data
}

export async function getImageTask(taskId) {
  const { data } = await client.get(`/image-creation/tasks/${taskId}`)
  return data
}

export async function syncImageTask(taskId) {
  const { data } = await client.post(`/image-creation/tasks/${taskId}/sync`)
  return data
}

export async function listImageAssets(params = {}) {
  const { data } = await client.get('/image-creation/assets', { params })
  return data
}

export async function reviewImageAsset(assetId, payload) {
  const { data } = await client.post(`/image-creation/assets/${assetId}/review`, payload)
  return data
}

export async function editImageAsset(assetId, payload) {
  const { data } = await client.post(`/image-creation/assets/${assetId}/edit`, payload)
  return data
}
```

- [ ] **Step 3: Add route and nav**

In `web/src/router/index.js`, add child route near `ai-video-review`:

```javascript
      {
        path: 'image-creation',
        name: 'ImageCreation',
        component: () => import('../views/ImageCreationPage.vue'),
      },
```

Add `/image-creation` to `ADMIN_ONLY_PATHS`.

In `web/src/constants/navigation.js`, add under the `AI 视频` items near `AI 视频审查`:

```javascript
      { name: '图像创作', path: '/image-creation', icon: 'M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-8h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z' },
```

Add route category:

```javascript
  '/image-creation': 'ai-video',
```

- [ ] **Step 4: Write page smoke tests**

Create `web/src/__tests__/image-creation-page.test.js`:

```javascript
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

vi.mock('../api/imageCreation.js', () => ({
  createImageTask: vi.fn().mockResolvedValue({ ok: true, task: { id: 'task-1', status: 'running' }, assets: [] }),
  listImageAssets: vi.fn().mockResolvedValue({ ok: true, assets: [] }),
  reviewImageAsset: vi.fn(),
  syncImageTask: vi.fn().mockResolvedValue({ ok: true, task: { id: 'task-1', status: 'completed' } }),
}))

describe('ImageCreationPage', () => {
  it('renders Chinese mode tabs and disables submit without prompt', async () => {
    const Page = (await import('../views/ImageCreationPage.vue')).default
    const wrapper = mount(Page)

    expect(wrapper.text()).toContain('图像创作')
    expect(wrapper.text()).toContain('文生图')
    expect(wrapper.text()).toContain('以图改图')
    expect(wrapper.text()).toContain('多图参考')
    expect(wrapper.text()).toContain('组图生成')
    expect(wrapper.find('[data-testid="image-create-submit"]').attributes('disabled')).toBeDefined()
  })
})
```

- [ ] **Step 5: Create workbench shell**

Create `web/src/views/ImageCreationPage.vue`:

```vue
<template>
  <div class="image-workbench">
    <header class="image-workbench__header">
      <div>
        <h1>图像创作</h1>
        <p>生成、改图、审查并复用视频生产前置视觉资产</p>
      </div>
      <button data-testid="image-create-submit" class="primary-button" :disabled="!canSubmit || submitting" @click="submit">
        {{ submitting ? '生成中' : '生成' }}
      </button>
    </header>

    <nav class="mode-tabs" aria-label="图像创作模式">
      <button v-for="item in modes" :key="item.key" :class="{ active: mode === item.key }" @click="mode = item.key">
        {{ item.label }}
      </button>
    </nav>

    <main class="image-workbench__grid">
      <section class="panel">
        <label>
          提示词
          <textarea v-model="form.prompt" rows="6" />
        </label>
        <label>
          目标用途
          <select v-model="form.destination_role">
            <option value="">未指定目标用途</option>
            <option value="character_anchor">角色锚点</option>
            <option value="scene_reference">场景参考</option>
            <option value="style_reference">风格参考</option>
            <option value="storyboard_frame">分镜帧</option>
            <option value="image_to_video_input">图生视频</option>
          </select>
        </label>
        <label>
          数量
          <input v-model.number="form.count" type="number" min="1" max="15" />
        </label>
      </section>

      <section class="panel reference-board">
        <h2>来源与参考图</h2>
        <p v-if="mode === 'text_to_image'">文生图不需要来源图。</p>
        <p v-else>上传图片、选择资产或粘贴图片 URL 后再生成。</p>
      </section>

      <section class="panel task-panel" aria-live="polite">
        <h2>任务与结果</h2>
        <div v-if="currentTask">当前任务：{{ currentTask.status }}</div>
        <div v-else>暂无任务</div>
        <div class="result-grid">
          <article v-for="asset in assets" :key="asset.id" class="asset-tile">
            <img :src="asset.url" :alt="assetAlt(asset)" />
            <strong>{{ reviewLabel(asset.status) }}</strong>
          </article>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { createImageTask } from '../api/imageCreation'

const modes = [
  { key: 'text_to_image', label: '文生图' },
  { key: 'image_to_image', label: '以图改图' },
  { key: 'multi_reference_to_image', label: '多图参考' },
  { key: 'multi_reference_to_image_set', label: '组图生成' },
]

const mode = ref('text_to_image')
const submitting = ref(false)
const currentTask = ref(null)
const assets = ref([])
const form = reactive({
  prompt: '',
  count: 1,
  destination_role: 'image_to_video_input',
})

const canSubmit = computed(() => form.prompt.trim().length > 0 && form.count >= 1)

function assetAlt(asset) {
  return `图像创作结果 ${asset.group_index || 1}`
}

function reviewLabel(status) {
  const labels = { review_pending: '待审查', approved: '已批准', rejected: '已驳回', failed: '失败' }
  return labels[status] || status || '未知'
}

async function submit() {
  if (!canSubmit.value) return
  submitting.value = true
  try {
    const result = await createImageTask({
      mode: mode.value,
      prompt: form.prompt,
      count: form.count,
      destination_role: form.destination_role || null,
      cost_confirmation: true,
      idempotency_key: `image-${Date.now()}`,
    })
    currentTask.value = result.task
    assets.value = result.assets || []
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.image-workbench {
  padding: 24px;
}
.image-workbench__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}
.mode-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}
.mode-tabs button.active {
  background: #2563eb;
  color: white;
}
.image-workbench__grid {
  display: grid;
  grid-template-columns: minmax(260px, 360px) minmax(320px, 1fr) minmax(320px, 420px);
  gap: 16px;
}
.panel {
  border: 1px solid #d8dee9;
  border-radius: 8px;
  padding: 16px;
  background: white;
}
.panel label {
  display: grid;
  gap: 6px;
  margin-bottom: 12px;
}
.primary-button {
  min-height: 40px;
  padding: 0 16px;
}
.result-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px;
}
.asset-tile img {
  width: 100%;
  aspect-ratio: 9 / 16;
  object-fit: cover;
  border-radius: 6px;
}
@media (max-width: 900px) {
  .image-workbench__grid {
    grid-template-columns: 1fr;
  }
}
</style>
```

- [ ] **Step 6: Run frontend tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/image-creation-api.test.js src/__tests__/image-creation-page.test.js src/__tests__/navigation.test.js
```

Expected: selected tests pass after navigation expectations are updated.

- [ ] **Step 7: Commit**

Run:

```powershell
git add web/src/api/imageCreation.js web/src/views/ImageCreationPage.vue web/src/router/index.js web/src/constants/navigation.js web/src/__tests__/image-creation-api.test.js web/src/__tests__/image-creation-page.test.js web/src/__tests__/navigation.test.js
git commit -m "feat: add image creation workbench shell"
```

---

### Task 7: Workbench Interaction Completion And Regression Verification

**Files:**
- Modify: `D:\devWorkspace\jsProjects\dy_auto\web\src\views\ImageCreationPage.vue`
- Create: `D:\devWorkspace\jsProjects\dy_auto\web\src\__tests__\image-creation-responsive.test.js`
- Create: `D:\devWorkspace\jsProjects\dy_auto\web\src\__tests__\image-creation-a11y.test.js`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_video_production_mocked_e2e.py`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_pixelle_stage_client.py`

- [ ] **Step 1: Write responsive and accessibility tests**

Create `web/src/__tests__/image-creation-a11y.test.js`:

```javascript
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

vi.mock('../api/imageCreation.js', () => ({
  createImageTask: vi.fn(),
  listImageAssets: vi.fn().mockResolvedValue({ ok: true, assets: [] }),
  reviewImageAsset: vi.fn(),
  syncImageTask: vi.fn(),
}))

describe('ImageCreationPage accessibility', () => {
  it('exposes task panel as live status region and labels primary inputs', async () => {
    const Page = (await import('../views/ImageCreationPage.vue')).default
    const wrapper = mount(Page)

    expect(wrapper.find('[aria-live="polite"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('提示词')
    expect(wrapper.text()).toContain('目标用途')
    expect(wrapper.text()).toContain('数量')
  })
})
```

Create `web/src/__tests__/image-creation-responsive.test.js`:

```javascript
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

vi.mock('../api/imageCreation.js', () => ({
  createImageTask: vi.fn(),
  listImageAssets: vi.fn().mockResolvedValue({ ok: true, assets: [] }),
  reviewImageAsset: vi.fn(),
  syncImageTask: vi.fn(),
}))

describe('ImageCreationPage responsive shell', () => {
  it('keeps the mode tabs and result panel in the same page shell', async () => {
    const Page = (await import('../views/ImageCreationPage.vue')).default
    const wrapper = mount(Page)

    expect(wrapper.find('.mode-tabs').exists()).toBe(true)
    expect(wrapper.find('.task-panel').exists()).toBe(true)
    expect(wrapper.find('.reference-board').exists()).toBe(true)
  })
})
```

- [ ] **Step 2: Add sync, review, edit-again, and error rendering to the page**

Extend `ImageCreationPage.vue` with imported APIs:

```javascript
import {
  createImageTask,
  editImageAsset,
  listImageAssets,
  reviewImageAsset,
  syncImageTask,
  uploadImageSource,
} from '../api/imageCreation'
```

Add methods:

```javascript
async function syncCurrentTask() {
  if (!currentTask.value?.id) return
  const result = await syncImageTask(currentTask.value.id)
  currentTask.value = result.task
}

async function approveAsset(asset) {
  const result = await reviewImageAsset(asset.id, { action: 'approve', asset_version: asset.version })
  replaceAsset(result.asset)
}

async function rejectAsset(asset) {
  const result = await reviewImageAsset(asset.id, { action: 'reject', asset_version: asset.version })
  replaceAsset(result.asset)
}

async function editAgain(asset) {
  const result = await editImageAsset(asset.id, {
    mode: 'image_to_image',
    prompt: form.prompt,
    count: 1,
    destination_role: asset.destination_role || form.destination_role || null,
    cost_confirmation: true,
    idempotency_key: `image-edit-${Date.now()}`,
  })
  currentTask.value = result.task
}

function replaceAsset(nextAsset) {
  assets.value = assets.value.map((asset) => (asset.id === nextAsset.id ? nextAsset : asset))
}
```

Add buttons inside each result tile:

```vue
<div class="asset-actions">
  <button type="button" @click="approveAsset(asset)">批准</button>
  <button type="button" @click="rejectAsset(asset)">驳回</button>
  <button type="button" @click="editAgain(asset)">再次改图</button>
</div>
```

Add sync button in the task panel:

```vue
<button type="button" :disabled="!currentTask" @click="syncCurrentTask">同步</button>
```

- [ ] **Step 3: Add usable source and reference image controls**

Replace the placeholder reference board with actual controls:

```vue
<section class="panel reference-board">
  <h2>来源与参考图</h2>
  <label v-if="mode !== 'text_to_image'">
    来源图 URL
    <input v-model="sourceUrl" type="url" placeholder="https://example.com/source.png" />
  </label>
  <label v-if="mode !== 'text_to_image'">
    上传来源图
    <input type="file" accept="image/*" @change="uploadSourceFile" />
  </label>
  <label v-if="mode.includes('reference')">
    参考图 URL
    <input v-model="referenceUrl" type="url" placeholder="https://example.com/ref.png" @keyup.enter="addReferenceUrl" />
  </label>
  <button v-if="mode.includes('reference')" type="button" @click="addReferenceUrl">添加参考图</button>
  <button type="button" @click="loadApprovedAssets">读取已批准资产</button>
  <ul>
    <li v-for="item in referenceImages" :key="item.url">{{ item.role }} - {{ item.url }}</li>
  </ul>
</section>
```

Add state and methods:

```javascript
const sourceUrl = ref('')
const referenceUrl = ref('')
const referenceImages = ref([])
const approvedAssets = ref([])

async function uploadSourceFile(event) {
  const file = event.target.files?.[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  const result = await uploadImageSource(formData)
  sourceUrl.value = result.url
}

function addReferenceUrl() {
  const url = referenceUrl.value.trim()
  if (!url || referenceImages.value.some((item) => item.url === url)) return
  referenceImages.value.push({ url, role: 'reference' })
  referenceUrl.value = ''
}

async function loadApprovedAssets() {
  const result = await listImageAssets({ status: 'approved', page_size: 30 })
  approvedAssets.value = result.assets || []
}
```

Update `submit()` payload so edit modes are actually usable:

```javascript
const payload = {
  mode: mode.value,
  prompt: form.prompt,
  count: form.count,
  destination_role: form.destination_role || null,
  cost_confirmation: true,
  idempotency_key: `image-${Date.now()}`,
}
if (mode.value !== 'text_to_image') {
  payload.source = sourceUrl.value ? { type: 'url', url: sourceUrl.value } : null
}
if (mode.value.includes('reference')) {
  payload.reference_images = referenceImages.value
}
const result = await createImageTask(payload)
```

Extend `image-creation-page.test.js` to verify `image_to_image` submits `source.url` and `multi_reference_to_image` submits `reference_images`; add a negative test that submit stays disabled or returns a visible error when a required source/reference is missing.

- [ ] **Step 4: Add regression assertion for existing stage image batch**

Append to `server/tests/test_pixelle_stage_client.py`:

```python
@pytest.mark.asyncio
async def test_submit_image_create_does_not_change_image_batch_endpoint(monkeypatch):
    calls = []

    async def fake_request(method, path, db=None, **kwargs):
        calls.append(path)
        return {"ok": True, "stage_task_id": "stage-1", "assets": []}

    monkeypatch.setattr("app.services.pixelle_stage_client._pixelle_request", fake_request)

    await submit_image_batch(
        db=None,
        run_id="run-1",
        episode_id="episode-1",
        frames=[{"frame_id": "frame-001", "image_prompt": "prompt", "reference_urls": [], "duration": 5}],
        model_config={"provider": "mock", "api_key": "secret"},
    )

    assert calls == ["/api/stages/images/batch"]
```

- [ ] **Step 5: Run backend and frontend regression tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_pixelle_stage_client.py tests/test_video_production_mocked_e2e.py tests/test_image_creation_mocked_e2e.py -q
```

Expected: all selected backend tests pass.

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/image-creation-page.test.js src/__tests__/image-creation-responsive.test.js src/__tests__/image-creation-a11y.test.js src/__tests__/ai-video-review-page.test.js
```

Expected: all selected frontend tests pass.

- [ ] **Step 6: Build frontend**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm run build
```

Expected: production build completes.

- [ ] **Step 7: Commit**

Run:

```powershell
git add web/src/views/ImageCreationPage.vue web/src/__tests__/image-creation-responsive.test.js web/src/__tests__/image-creation-a11y.test.js server/tests/test_pixelle_stage_client.py server/tests/test_video_production_mocked_e2e.py
git commit -m "test: complete image creation workbench interactions"
```

---

## Final Verification

Run the focused backend suite:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_model_schema.py tests/test_image_creation_models.py tests/test_image_creation_model_resolution.py tests/test_image_creation_pixelle_client.py tests/test_image_creation_api.py tests/test_image_creation_mocked_e2e.py tests/test_pixelle_stage_client.py tests/test_video_production_mocked_e2e.py -q
```

Run the focused frontend suite:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/image-creation-api.test.js src/__tests__/image-creation-page.test.js src/__tests__/image-creation-responsive.test.js src/__tests__/image-creation-a11y.test.js src/__tests__/navigation.test.js src/__tests__/ai-video-review-page.test.js
```

Run the Pixelle focused suite:

```powershell
cd D:\devWorkspace\Pixelle-Video
pytest tests/test_stage_image_create.py -q
```

Build the frontend:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm run build
```

Manual smoke check:

1. Start dy_auto backend.
2. Start dy_auto frontend.
3. Start Pixelle-Video API.
4. Open `/image-creation`.
5. Submit `文生图` with mock provider.
6. Sync the task.
7. Approve the generated image.
8. Confirm approved image appears in the image-to-video selector.
9. Confirm existing AI video review and staged production image batch still work.

## Self-Review

Spec coverage:

- Provider-neutral model capability: Task 1.
- Dedicated image creation persistence: Task 2.
- Pixelle standalone execution endpoint: Task 3.
- dy_auto image creation API and idempotent task creation: Task 4.
- Review, edit-again, and downstream selector behavior: Task 5.
- Frontend route, navigation, and workbench: Task 6.
- Accessibility, responsive behavior, and regressions: Task 7.

Risk checks:

- Duplicate task submission is covered by `idempotency_key` and `request_hash`.
- Duplicate sync is covered by the asset uniqueness constraint and service upsert check.
- Video production regression is covered by keeping `/api/stages/images/batch` unchanged.
- Provider secret leakage is limited by existing `redact_runtime_model_config` and runtime-only Pixelle payloads.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-27-image-creation-workbench-implementation.md`.

Two execution options:

1. **Subagent-Driven (recommended)**: use `superpowers:subagent-driven-development`; run one fresh implementation worker per task and review between tasks.
2. **Inline Execution**: use `superpowers:executing-plans`; execute tasks in this session with checkpoints after each task.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | NOT RUN | Optional; image workbench scope already came from the approved design/spec chain. |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | NOT RUN | Deferred until implementation diff exists. |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR | 5 issues found and revised in-plan; 0 critical gaps remain. |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | PRIOR SPEC REVIEWED | Design review already ran on the spec; re-run after frontend implementation if the page diverges. |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | NOT RUN | Not required for this internal workflow feature. |

- **ENG FIXES APPLIED:** Replaced duplicate Seedream editing model with multi-scene capability config; preserved destination metadata through Pixelle sync; added source/reference validation; passed negative prompt and watermark to Pixelle; added real frontend source/reference controls.
- **UNRESOLVED:** 0.
- **VERDICT:** ENG CLEARED. Ready to implement with `superpowers:subagent-driven-development` or `superpowers:executing-plans`.

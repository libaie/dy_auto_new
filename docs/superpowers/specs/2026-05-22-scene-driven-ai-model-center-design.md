# Scene-Driven AI Model Center Design

## Summary

The current AI model configuration center already has an `AIModel` table and CRUD page, but provider lists, field templates, and pipeline model keys are still hard-coded in the frontend and backend. This design upgrades the system to a scene-driven model center.

Users configure models once through a single model center. Each model has shared connection fields plus scene-specific fields. Runtime systems such as pipeline, director, style lock, and audit resolve models by application scene instead of provider-specific UI logic.

The chosen scope is:

- Main path: model center plus pipeline, director, style lock, and audit all resolve models by application scene.
- Migration path: old Settings, Pixelle, and Seedance model configuration data is automatically migrated into `AIModel`.
- Cleanup path: old model configuration entrances and old model configuration logic are removed after dependencies are cleared.
- Field model: built-in scene templates plus user-added custom fields.

## Goals

- Replace hard-coded frontend provider lists and type-specific fields with backend schema metadata.
- Keep one configuration entrance for LLM, Image, Video, TTS, and Audit models.
- Let generation workflows resolve models by scene keys such as `script_generation`, `image_generation`, `video_rendering`, `tts_synthesis`, and `quality_audit`.
- Preserve existing configured credentials by automatically migrating legacy settings into `AIModel`.
- Remove old Settings, Pixelle, and Seedance configuration entrances so users no longer configure the same provider in multiple places.
- Keep the first implementation compatible with existing `AIModel` storage and avoid adding tables unless the current shape cannot express the behavior.

## Non-Goals

- No full plugin marketplace for providers in the first version.
- No visual workflow editor for model routing.
- No per-tenant or per-user model policy in the first version.
- No automatic provider capability discovery from remote APIs.
- No public exposure of API keys or API secrets.

## Current State

The repo already contains:

- `server/app/db_models.py`: `AIModel` with shared fields and `config_json`.
- `server/app/routers/ai_config.py`: CRUD, options, connection test, and default seed data.
- `web/src/views/AIConfigPage.vue`: a single page that renders grouped models and type-specific fields.
- `web/src/api/aiConfig.js`: AI model CRUD client functions.
- `web/src/components/video-studio/PipelineLayerConfig.vue`: layer model selectors using `/api/ai-models/options`.
- `server/app/routers/pipeline.py`: hard-coded layer keys such as `scriptLLM`, `imageModel`, `videoModel`, and `ttsModel`.
- `server/app/routers/audit.py`: audit model lookup directly queries `AIModel.model_type == "audit"`.
- `server/app/routers/series.py`: style-lock reference image generation directly queries enabled image models.
- Legacy configuration still exists in Settings, Pixelle, and Seedance paths.

## Recommended Architecture

Use `AIModel` as the single model configuration record and add two backend service layers:

1. `model_schema`
   - Owns application scene definitions.
   - Owns provider presets.
   - Owns shared field definitions and scene-specific field templates.
   - Returns metadata to the frontend through a read-only schema endpoint.

2. `model_registry`
   - Resolves runtime model configuration by scene key.
   - Accepts explicit model IDs for compatibility.
   - Falls back to the default enabled model for the scene.
   - Decrypts secrets only for runtime use.
   - Produces user-facing errors with scene names and repair actions.

The frontend becomes a renderer of backend schema instead of a hard-coded dictionary of provider and field options.

```text
AIConfigPage
  -> GET /api/ai-models/schema
  -> GET /api/ai-models?scene_key=video_rendering
  -> POST/PUT /api/ai-models

pipeline/director/audit/style-lock
  -> model_registry.get_model_for_scene(scene_key, explicit_model_id)
  -> AIModel
  -> provider-specific runtime call
```

## Scene Model

Application scenes are stable product concepts, while `model_type` remains a coarse technical category.

| Scene key | Label | model_type | Used by |
|---|---|---|---|
| `script_generation` | LLM · 脚本生成 | `llm` | director plan, narration, title, prompt generation |
| `image_generation` | Image · 画面生成 | `image` | style-lock references, L0 image assets |
| `video_rendering` | Video · 视频渲染 | `video` | L4 video generation, Seedance independent panel after migration |
| `tts_synthesis` | TTS · 语音合成 | `tts` | narration audio and future voice synthesis |
| `quality_audit` | Audit · 质量审计 | `audit` | image/video quality audit |

First version can derive scene support from `model_type`. The scene key is passed at runtime and used for labels, defaults, schema selection, and error messages. A separate scene binding table is deferred until one physical model must have different defaults for multiple scenes.

## Data Model

Reuse `AIModel`:

- `name`: user-facing model name.
- `model_type`: `llm`, `image`, `video`, `tts`, or `audit`.
- `provider`: provider identifier, including custom providers.
- `base_url`: endpoint root or provider-specific endpoint.
- `api_key`: encrypted API key.
- `api_secret`: encrypted secondary secret when needed.
- `model_name`: remote model identifier.
- `config_json`: scene-specific config, provider-specific config, and custom fields.
- `enabled`: whether the model can be selected and used.
- `sort_order`: default model priority.

`config_json` shape:

```json
{
  "scene_key": "video_rendering",
  "protocol": "openai_compatible",
  "scene_config": {
    "default_resolution": "720p",
    "default_duration": 5,
    "default_aspect_ratio": "9:16",
    "poll_interval_seconds": 10,
    "poll_timeout_seconds": 180
  },
  "custom_fields": {
    "workflow_id": "optional-provider-workflow"
  }
}
```

For backwards compatibility, readers should also tolerate existing flat keys such as `default_resolution` and `temperature`. Writers should save the normalized shape above after the refactor.

## Backend Interfaces

### `GET /api/ai-models/schema`

Returns everything the frontend needs to render the model center:

```json
{
  "ok": true,
  "common_fields": [],
  "scenes": [
    {
      "key": "video_rendering",
      "label": "Video · 视频渲染",
      "model_type": "video",
      "description": "用于 L4 渲染和独立视频生成",
      "providers": ["seedance", "kling", "wan", "pixelle", "custom"],
      "fields": [],
      "default_config": {}
    }
  ],
  "protocols": ["openai_compatible", "anthropic", "gemini", "http_custom", "local_service"],
  "custom_field_policy": {
    "enabled": true,
    "allowed_types": ["string", "number", "boolean", "select", "secret"]
  }
}
```

### Existing CRUD Endpoints

Keep the existing route names:

- `GET /api/ai-models`
- `GET /api/ai-models/{id}`
- `POST /api/ai-models`
- `PUT /api/ai-models/{id}`
- `DELETE /api/ai-models/{id}`
- `GET /api/ai-models/options`
- `POST /api/ai-models/{id}/test`

Enhance list and options filters to accept `scene_key`. The backend maps scene key to model type.

### Registry Service

Add a backend service, for example `server/app/services/model_registry.py`:

```python
def get_model_for_scene(db, scene_key: str, explicit_model_id: str | None = None) -> dict:
    ...
```

Resolution rules:

1. If `explicit_model_id` exists, load that model and validate it supports the scene.
2. If not, choose the first enabled model for the scene's `model_type`, ordered by `sort_order` and `created_at`.
3. If no usable model exists, raise a user-facing error naming the scene and repair action.
4. Decrypt `api_key` and `api_secret` only in the returned runtime dict.
5. Do not leak secrets in list, options, schema, or frontend payloads.

## Runtime Integration

### Pipeline

Keep request compatibility for now:

```json
{
  "model_ids": {
    "scriptLLM": "uuid",
    "imageModel": "uuid",
    "videoModel": "uuid",
    "ttsModel": "uuid",
    "auditModel": "uuid"
  }
}
```

Internally map old layer keys to scenes:

| Old key | Scene key |
|---|---|
| `scriptLLM` | `script_generation` |
| `imageModel` | `image_generation` |
| `videoModel` | `video_rendering` |
| `ttsModel` | `tts_synthesis` |
| `auditModel` | `quality_audit` |

Each pipeline layer calls `model_registry.get_model_for_scene()`. Provider-specific generation functions receive the normalized runtime config.

### Director

`POST /api/director/auto-plan` should use `script_generation` unless the caller explicitly supplies a model ID. Missing model errors should say the script generation model is missing.

### Style Lock

Reference image generation should use `image_generation`. If no image model is configured, the style-lock API should return `missing_assets` plus a clear repair action.

### Audit

Audit should use `quality_audit` and remove direct `AIModel.model_type == "audit"` lookup from the router.

### TTS

TTS resolution is prepared as `tts_synthesis`. If the current production path still delegates audio to Pixelle, the model center should still allow TTS configuration, but runtime usage can be staged behind the existing audio layer.

## Frontend Design

The model center has one entry and three states.

### List State

- Group models by application scene.
- Show model count, default model, connection status, and missing-key status per scene.
- Provide a single `新增模型` action.
- Remove navigation entries for old Settings, Pixelle, and Seedance model configuration.

### Detail State

- Show common fields and scene-specific fields.
- Show whether API Key and API Secret are configured, never their plaintext values.
- Show the application scenes that can use the model.
- Show latest connection test result.
- Show whether the model is available for the automated video pipeline.

### Edit State

Four-step form:

1. Select application scene.
2. Select provider or custom provider.
3. Fill common fields: name, provider, base URL, API Key, API Secret, model identifier.
4. Fill scene-specific fields and optional custom fields.

Custom provider requires a protocol:

- OpenAI Compatible
- Anthropic
- Gemini
- HTTP Custom
- Local Service

`AIConfigPage.vue` should be split into smaller components:

- `ModelSceneSidebar.vue`
- `ModelDetailPanel.vue`
- `ModelEditForm.vue`
- `ModelSchemaField.vue`
- `ModelConnectionStatus.vue`

## Migration

Automatic migration runs during startup or seed.

Rules:

- Idempotent by provider, model name, and model type.
- Existing valid `AIModel` rows are not overwritten unless the old setting provides a secret for an otherwise empty model.
- Secrets are encrypted using the existing crypto service.
- Migration logs counts and skipped records.

Sources:

- Settings LLM keys: migrate to `script_generation` LLM model.
- Pixelle base URL and related API settings: migrate to provider `pixelle` for supported scenes.
- Seedance API key: migrate to provider `seedance` for image or video models when model identifiers are known.
- Kling keys: migrate to provider `kling` video model.
- RunningHub or ComfyUI keys: migrate to image model records if currently used by image generation.

After migration:

- Remove old UI entrances for Settings AI config, Pixelle config, and Seedance config.
- Remove old backend configuration logic once call sites use `model_registry`.
- Keep non-model settings such as OSS or unrelated system settings outside this migration.

## Error Handling

All runtime model errors should be scene-aware:

- Missing model: `未配置 Video · 视频渲染模型，请到 AI 模型配置中心新增或启用模型。`
- Missing API Key: `Seedance 2.0 缺少 API Key，请到模型详情页补齐。`
- Unsupported scene: `当前模型类型不能用于质量审计。`
- Connection failed: include HTTP status or timeout summary, but never include secrets.
- Custom provider missing protocol: block save and ask user to choose a protocol.

Pipeline and agency console summaries should surface the scene name and repair action rather than raw provider exceptions.

## Test Plan

Backend:

- Schema endpoint returns scenes, providers, common fields, scene fields, and custom field policy.
- CRUD saves normalized `config_json` while still reading legacy flat `config_json`.
- Registry returns explicit model when valid.
- Registry falls back to default enabled model by scene.
- Registry rejects missing, disabled, or wrong-type explicit models.
- Migration creates AIModel rows from legacy settings and is idempotent.
- Pipeline layer model lookup calls registry with expected scene keys.
- Director auto-plan uses `script_generation`.
- Style-lock image generation uses `image_generation`.
- Audit uses `quality_audit`.
- Secret fields remain masked outside admin detail and runtime registry.

Frontend:

- `AIConfigPage` loads schema and does not use hard-coded provider lists.
- Scene sidebar shows LLM, Image, Video, TTS, and Audit groups.
- Edit form changes field template when scene changes.
- Custom provider requires protocol selection.
- API Key fields display configured status without plaintext in detail state.
- Old Settings/Pixelle/Seedance configuration navigation entries are removed.
- Pipeline model selectors still work through scene-compatible options.

Regression:

- Existing Pixelle quick creation flow still starts generation through migrated model config.
- Existing Seedance independent panel either routes through model center or is removed with replacement entry.
- Series style lock, auto-plan, pipeline start, and audit flows still pass mocked tests.

## Rollout Plan

1. Add schema and registry services with tests.
2. Add migration tests and migration implementation.
3. Update pipeline, director, style-lock, and audit to use registry.
4. Refactor model center frontend around backend schema.
5. Remove old model configuration UI entrances.
6. Remove obsolete backend config readers after call sites are migrated.
7. Run backend tests, frontend tests, and frontend build.

## Open Decisions Closed

- Scope: B plus C. The model center must power runtime workflows and old model config entrances must be removed.
- Legacy data: automatically migrate into `AIModel`.
- Field flexibility: built-in scene templates plus user-added custom fields.
- UI structure: approved left scene navigation with right-side detail/edit panels.

## Spec Self-Review

- No placeholder requirements remain.
- The design keeps `AIModel` as the core table and does not contradict the existing 2026-05-14 model config design. It extends that design from type-driven to scene-driven.
- The first implementation is scoped to model configuration and runtime resolution, not a full provider plugin system.
- Old entrances are removed only after their runtime dependencies are moved to `model_registry`, preserving configured credentials through automatic migration.

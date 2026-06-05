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

### Information Architecture

- **Default view**: All 5 scene groups expanded. Empty scenes display a "no model" empty state with an inline add action. Users can scan the full pipeline configuration status at a glance.
- **Scene order** (sidebar, fixed): `script_generation` → `image_generation` → `video_rendering` → `tts_synthesis` → `quality_audit`. Matches the video production pipeline workflow in mental-model order.
- **Navigation**: Click a model card → right panel transitions to detail/edit view in-place. A breadcrumb bar at the top of the panel reads "← Back to model list". The scene sidebar remains visible at all times.
- **Add model button**: Single `+ 新增模型` button in the top toolbar of the right content area, aligned with the breadcrumb. It opens the 4-step edit form in the right panel. Not repeated per scene group.
- **Sidebar width**: ~240px fixed, with scene labels, model count badges, and a visual indicator for scenes with missing/disabled models.

### Interaction States

Every UI feature must specify loading, empty, error, success, and in-progress states.

| Feature | Loading | Empty | Error | Success | In-Progress |
|---------|---------|-------|-------|---------|-------------|
| Schema fetch | Sidebar skeleton placeholder + right panel spinner | — | Full right-panel error illustration + "配置加载失败" + [Retry] button; sidebar shows skeleton | — | — |
| Model list fetch | Right panel skeleton cards (3-4 placeholder cards with shimmer) | Scene group shows "暂无模型" with inline "新增模型" CTA | Inline error banner in right panel with retry; sidebar still visible | — | — |
| Connection test | — | — | Inline result below button: "✗ 连接超时 (10s)" or "✗ HTTP 502" — no secrets exposed | Inline result: "✓ 连接成功 (230ms)" | Button shows spinner + "测试中..."; button disabled during test |
| Save model | — | — | Inline field errors highlighted red; step indicator shows red icon on failing step | Return to detail view with brief green toast "模型已保存" | Save button shows spinner; form fields disabled |
| Delete model | — | — | Inline error if delete fails: "删除失败: 模型可能已被其他流程使用" | Card animates out; brief green toast "模型已删除" | Inline confirmation expands; confirm button shows spinner during deletion |
| 4-step form validation | — | — | Per-step: invalid fields show red border + inline message; step indicator shows red icon. Cannot proceed to next step until current step valid | Completed steps show green checkmark on step indicator | Save button disabled until all validations pass |

**Delete confirmation flow**: Click delete → card/row expands a red confirmation area: "确定删除模型 [name]？如果该模型是某场景的唯一可用模型，该场景将变为未配置状态。[取消] [确认删除]". The confirmation text warns about cascading effects (scene becomes unconfigured).

**4-step form validation timing**: Validate on "Next step" click, not on field blur. Current step must pass all validations before proceeding. User can return to previous steps freely. Save button on step 4 remains disabled until all validations pass.

### User Journey

**First-time experience (migration soft-landing):** When a user opens the model center for the first time and legacy configs are detected, show a welcome card in the right panel:

> "欢迎使用 AI 模型中心 — 我们发现您的系统中已有 [N] 项旧版模型配置（Settings / Pixelle / Seedance），可以一键迁移到新模型中心。[开始迁移] [跳过，手动配置]"

After migration completes, show a migration report (created / skipped / conflicts). If migration is skipped, proceed to the normal empty-state flow.

**Scene readiness at a glance:** The sidebar shows a red/amber/green status dot next to each scene:
- Green: at least one enabled model with a passing connection test
- Amber: models exist but untested or missing API key
- Red: no enabled model available

A summary bar at the top of the right panel reads: "视频生产链路就绪: [N]/5 场景可用". Clicking a non-ready scene auto-expands it and highlights the gap (missing model, disabled, untested).

**Emotional arc per user type:**
- **Operator checking readiness (5-second scan):** Opens page → sees sidebar dots + summary bar → knows if pipeline is ready → closes or drills down. No reading required.
- **Admin configuring a new model (5-minute task):** Clicks +新增 → picks scene → picks provider → fills fields → tests connection → saves. Each step has clear completion feedback.
- **Debugger investigating a failed generation (5-minute investigation):** Opens model center → sees which scene has amber/red status → opens that model → sees "last test: failed 502" → fixes and re-tests.

| Step | User Does | User Feels | Plan Specifies? |
|------|-----------|------------|-----------------|
| 1. Open model center | Lands on page | "Is my pipeline ready?" | Summary bar + status dots |
| 2. First-time migration | Sees welcome card | "What happened to my old config?" | Migration prompt with counts |
| 3. Add new model | Clicks +新增 | "What do I need to fill?" | 4-step guided form |
| 4. Test connection | Clicks 测试连接 | "Did it work?" | Button spinner → inline result |
| 5. Check readiness | Scans sidebar dots | "Can I generate now?" | Green means go |

### Visual Design System

**Direction**: Dark professional dashboard (Linear/Vercel/PlanetScale style). Dark background with low-saturation accent color, high-density information layout. Cards and rows distinguished by subtle borders over shadows. Suitable for extended-watching operations scenarios.

**Color system:**
- Background: deep gray (#0f1419 or similar)
- Surface/cards: slightly lighter (#1a1f2e or similar)
- Accent: single low-saturation blue (#3b82f6 or similar)
- Text primary: #e2e8f0, secondary: #94a3b8
- Status dots: green (#22c55e), amber (#eab308), red (#ef4444)

**Typography:**
- Primary font: system sans-serif stack with explicit CJK fallback ("Inter, 'Noto Sans SC', system-ui, sans-serif"). Not default Inter-only since CJK text needs proper rendering.
- Body text minimum 14px on dense dashboard views, 16px on form views
- No system-ui as primary font

**Scene icons:** Monochrome SVG line icons (Lucide/Heroicons style), 20x20px: `script_generation`=MessageSquare, `image_generation`=Image, `video_rendering`=Video, `tts_synthesis`=Volume2, `quality_audit`=ShieldCheck. Icons follow text color, not accent color.

**Anti-slop constraints:**
- No purple/violet/indigo gradients
- No icons in colored circles
- No decorative shadows or blobs
- No centered text layouts
- No emoji as UI elements
- No colored left-borders on cards
- Cards earn their existence — use border-separated rows where a card is not needed
- No border-radius larger than 8px on functional elements

### Responsive & Accessibility

**Responsive strategy:** Full responsive coverage from 375px (mobile) to 2560px (wide screen). Breakpoints:
- 375-767px (mobile): Sidebar collapses to bottom tab bar. Single-column content. Form steps stack vertically. Model cards full-width.
- 768-1279px (tablet): Sidebar collapsible (icon-only mode, expand on tap). Two-column model card grid.
- 1280px+ (desktop, primary target): Full sidebar (~240px) + right panel layout. Multi-column card grid as space allows.

**Accessibility minimum bar:**
- Keyboard navigation: all interactive elements (sidebar items, cards, form fields, buttons) reachable via Tab key. Visible focus ring on all focused elements.
- ARIA landmarks: `nav` for sidebar, `main` for right panel, `form` with labeled fields for edit view, `status` roles for connection test results and scene readiness indicators.
- Color not sole indicator: status dots accompanied by text or icon shape difference. Red/green status dots have distinct shapes (circle/triangle) for colorblind users.
- Contrast: all text meets WCAG AA 4.5:1 minimum. Dark theme text (#e2e8f0 on #1a1f2e passes; #94a3b8 secondary text on #1a1f2e needs verification).
- Touch targets: minimum 44x44px on all interactive elements, including mobile breakpoints.

### View Transitions & Form Steps

**View transitions:** List → Detail/Edit slides in from right (~200ms ease-out, transformX + opacity). Detail/Edit → List slides out to left. The scene sidebar remains static — only the right panel content transitions. This preserves spatial context and avoids full-page re-renders.

**4-step form progress indicator:** Horizontal step indicator bar at top of the edit form:
```
● 选择场景  ──  ● 选择提供商  ──  ○ 通用字段  ──  ○ 场景配置
   (active)        (pending)       (pending)      (pending)
```
Completed steps show a green checkmark. Current step is highlighted with accent color. Clicking a completed step returns to it for editing. Pending steps are not clickable.

**Old entrance removal timing:** Legacy Settings/Pixelle/Seedance UI entrances are removed in a single, separate PR after ALL of: new model center ships, migration completes, all runtime consumers use model_registry, and regression tests pass. Backend legacy routes are marked deprecated but retained as fallback. This is the safest rollout — old paths stay reachable via direct URL if needed.

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

## GSTACK REVIEW REPORT

### Autoplan Verdict (2026-05-22)

结论：方案可行，建议批准进入实现。用统一 `AIModel` 加场景化 schema 和 `model_registry` 替代分散硬编码配置。

### Review Scores

| Review | Score | Status | Gate |
| --- | ---: | --- | --- |
| CEO | 8.5 / 10 | Clean with condition | 旧入口删除需要依赖清理条件 |
| Design (plan-design-review) | 5→8 / 10 | Clean | IA、交互状态、用户旅程、视觉系统、响应式/a11y 全部补齐 |
| Engineering (plan-eng-review) | 8.5→9 / 10 | CLEAN | 4 P1 issues resolved: secret preservation, model_name dedup, Pixelle/Seedance strategy, model_trace |
| DX | 8.5 / 10 | Clean after examples | provider schema 示例 + registry 错误示例 |
| Overall | 8.8 / 10 | Approve with required constraints | 可进入实现 |

### Engineering Deep Review — /plan-eng-review 2026-05-22

Mode: FULL_REVIEW. Complexity check triggered (8+ files, 2+ new services). Complexity justified — three consumers (pipeline/audit/series) each implemented different model resolution patterns; registry unifies and reduces total complexity.

#### Architecture Review (4 P1 issues, all resolved)

| # | Severity | Confidence | File:Line | Finding | Resolution |
|---|----------|------------|-----------|---------|------------|
| 1 | P1 | 9/10 | `ai_config.py:131-132` | Blank `api_key`/`api_secret` on PUT wipes encrypted secret | Backend treats blank as preserve-existing; `clear_secret: true` flag for explicit clear |
| 2 | P1 | 8/10 | `db_models.py:658` | SQLite NULL semantics allow duplicate `(type, provider, NULL)` rows | Normalize NULL/empty to `""` in migration + app-level dedup check |
| 3 | P1 | 9/10 | `seedance.py:32-37`, `config.py:221-246` | Seedance reads key from SystemSetting; Pixelle has separate service config layer | Migrate all to AIModel; config.py resolves from registry; Pixelle service config stored in config_json |
| 4 | P1 | 8/10 | `pipeline.py:151-170` | `_get_model_config()` returns dict but run.layers_json doesn't record model choice | `model_trace` {model_id, provider, scene_key, resolution_source} written to layers_json per layer |

#### Code Quality Review (3 issues, all resolved)

| # | Severity | Confidence | Finding | Resolution |
|---|----------|------------|---------|------------|
| 5 | P2 | 8/10 | Three different model resolution patterns in pipeline.py, audit.py, series.py | Build registry first, then migrate consumers one by one |
| 6 | P2 | 8/10 | `ai_config.py:176` — connection test hardcodes `/models` endpoint | Provider-specific test_strategy in schema: `list_models`, `health_check`, `noop` |
| 7 | P2 | 8/10 | `AIConfigPage.vue` at 899 lines, proposed split into 5 components | Split timing: schema loading first, component split only where reduces complexity |

#### Test Review

Coverage: 5/28 paths tested (18%). 23 gaps, 4 CRITICAL.

**Required new backend tests:**
- `server/tests/test_model_schema.py` — schema scenes/providers/protocols
- `server/tests/test_model_registry.py` — explicit/fallback/missing/disabled/wrong-type
- `server/tests/test_ai_model_migration.py` — idempotency, blank model_name, conflict report
- `server/tests/test_ai_config_scene_schema.py` — scene_key filter, blank secret preservation
- `server/tests/test_pipeline_model_registry.py` — pipeline via registry
- `server/tests/test_pixelle_seedance_model_center_regression.py` — Pixelle/Seedance still work

**Required new frontend tests:**
- `web/src/__tests__/ai-config-scene-schema.test.js` — schema client, scene sidebar, form validation

**CRITICAL gaps:**
1. Blank secret preservation test (regression if missing)
2. Migration blank model_name idempotency (data corruption risk)
3. Pixelle/Seedance regression test before old entrance removal
4. Registry error paths (missing/disabled/wrong-type)

Test plan artifact: `~/.gstack/projects/server/HNXE-feature-video-review-fixes-eng-review-test-plan-20260522-171519.md`

#### Performance Review

No issues found. AIModel has `model_type` index. Registry lookup is single indexed query. No caching needed in v1.

#### Failure Modes

| Codepath | Failure mode | Test | Handling | User sees |
| --- | --- | --- | --- | --- |
| Registry explicit lookup | Model ID missing | Required | ModelResolutionError | "Selected model no longer exists" |
| Registry explicit lookup | Model disabled | Required | reject before provider call | repair action |
| Registry fallback | No enabled model | Required | scene-aware 400 | model center link |
| Registry runtime dict | Decrypt failure | Required | log, reject if secret required | "API Key cannot be decrypted" |
| AIConfig update | Blank secret wipes existing | CRITICAL | preserve by default | no accidental loss |
| Migration | Blank model_name duplicates | CRITICAL | normalized matching | conflict/warning |
| Pixelle migration | Service URL deleted | CRITICAL | dependency gate | quick-create still works |
| Seedance migration | Panel still reads SystemSetting | CRITICAL | route adapter or removal | no broken panel |
| Pipeline | Model trace missing | Required | write model_trace | transparent run history |
| Frontend | Schema load fails | Required | fallback error state | retry action |

#### Implementation Tasks

- [ ] **T1 (P1, human: ~1h / CC: ~10min)** — ai_config.py — Blank api_key/api_secret on PUT preserves existing secret
  - Surfaced by: Architecture #1 — `ai_config.py:131-132` empty string wipes encrypted secret
  - Files: `server/app/routers/ai_config.py`
  - Verify: `pytest server/tests/test_ai_config.py -k test_update_preserves_blank_secret -v`

- [ ] **T2 (P1, human: ~1.5h / CC: ~15min)** — db_models + migration — Normalize blank model_name, app-level dedup
  - Surfaced by: Architecture #2 — SQLite NULL semantics allow duplicates
  - Files: `server/app/db_models.py`, migration script
  - Verify: `pytest server/tests/test_ai_model_migration.py -v`

- [ ] **T3 (P1, human: ~2h / CC: ~15min)** — seedance.py, config.py — Migrate all to AIModel + registry resolution
  - Surfaced by: Architecture #3 — Seedance/Pixelle still use legacy config paths
  - Files: `server/app/routers/seedance.py`, `server/app/config.py`, `server/app/services/model_registry.py`
  - Verify: `pytest server/tests/test_pixelle_seedance_model_center_regression.py -v`

- [ ] **T4 (P1, human: ~1h / CC: ~10min)** — pipeline.py — Add model_trace to run.layers_json per layer
  - Surfaced by: Architecture #4 — no model selection trace in pipeline runs
  - Files: `server/app/routers/pipeline.py`
  - Verify: `pytest server/tests/test_pipeline_model_registry.py -k test_model_trace -v`

- [ ] **T5 (P2, human: ~3h / CC: ~20min)** — model_registry + model_schema services
  - Surfaced by: Code Quality #5 — three duplicate model resolution patterns
  - Files: `server/app/services/model_registry.py`, `server/app/services/model_schema.py`
  - Verify: `pytest server/tests/test_model_registry.py server/tests/test_model_schema.py -v`

- [ ] **T6 (P2, human: ~1h / CC: ~10min)** — ai_config.py — Protocol-aware connection test
  - Surfaced by: Code Quality #6 — `/models` endpoint hardcoded
  - Files: `server/app/routers/ai_config.py`
  - Verify: `pytest server/tests/test_ai_config_scene_schema.py -k test_connection -v`

- [ ] **T7 (P2, human: ~1h / CC: ~10min)** — Frontend schema renderer + tests
  - Surfaced by: Test Review — 23 test gaps
  - Files: `web/src/views/AIConfigPage.vue`, `web/src/api/aiConfig.js`, `web/src/__tests__/ai-config-scene-schema.test.js`
  - Verify: `cd web && npx vitest run ai-config-scene-schema`

#### Parallelization Strategy

| Step | Modules touched | Depends on |
| --- | --- | --- |
| Backend schema + registry (T5) | `server/app/services`, `server/app/routers` | none |
| Secret preservation (T1) | `server/app/routers/ai_config.py` | none |
| model_name dedup (T2) | `server/app/db_models.py`, migration | T5 (contract) |
| Pixelle/Seedance migration (T3) | seedance.py, config.py, registry | T5 (contract) |
| model_trace (T4) | pipeline.py | T5 (contract) |
| Connection test (T6) | ai_config.py | T5 (contract) |
| Runtime consumers (pipeline/audit/series) | routers | T5 (contract) |
| Frontend (T7) | web/ | schema endpoint (T5) |
| Old entrance cleanup | navigation, Settings, Pixelle/Seedance panels | T3, T5, runtime consumers |
| Regression tests | server tests, web tests | corresponding implementation lanes |

**Parallel lanes:**
- Lane A: T1 + T5 (independent) — backend foundation
- Lane B: T7 (independent of backend, uses mocked schema) — frontend
- Lane C: T2 + T3 + T4 + T6 (after T5 contract stable) — dependent features
- Lane D: Runtime consumers (after T5) — pipeline/director/audit/series
- Lane E: Old entrance cleanup (after C + D pass) — final cleanup

#### NOT in Scope Confirmed

- Fallback chains, cost budgets, provider health routing, rate limits
- New database tables for scene bindings
- Full replacement of Pixelle proxy semantics
- Full E2E against live external providers
- Non-video device/task AI config migration

#### What Already Exists and Should Be Reused

- `AIModel` table with encrypted key fields, CRUD router, options endpoint
- `AIConfigPage.vue` existing model page (899 lines, to be split)
- `PipelineLayerConfig.vue` model selectors
- Existing crypto service for secret encryption
- `server/tests/test_ai_config.py` (13 tests, CRUD coverage)
- `server/tests/test_series_style_lock_pipeline.py` (2 tests)
- `web/src/__tests__/api-clients.test.js` (API client tests)

#### Engineering Completion Summary

```
+====================================================================+
|            PLAN ENG REVIEW - COMPLETION SUMMARY                    |
+====================================================================+
| Mode selected        | FULL_REVIEW                                 |
| Scope Challenge      | complexity justified, staged implementation |
| Section 1 (Arch)     | 4 P1 issues found, all resolved             |
| Section 2 (Quality)  | 3 issues found, all resolved                |
| Section 3 (Tests)    | coverage diagram produced, 23 gaps / 4 CRIT |
| Section 4 (Perf)     | clear, no issues found                      |
+--------------------------------------------------------------------+
| NOT in scope         | written (5 items)                           |
| What already exists  | written                                     |
| Failure modes        | 10 total, 4 CRITICAL test requirements       |
| Parallelization      | 5 lanes, 3 sequential gates                 |
| Test artifact        | written                                     |
| Lake Score           | 7/7 recommendations chose complete option   |
| Unresolved decisions | 0                                           |
+====================================================================+
```

#### Engineering Final Verdict

**CLEAR — 4 P1 gates satisfied:**

1. Backend preserves secrets on blank update at API level (T1)
2. Registry handles missing, disabled, wrong-type, undecryptable models with tests (T5)
3. Migration proves idempotency with blank/null model_name and conflict reports (T2)
4. Pixelle and Seedance fully migrated to AIModel + registry path (T3)
5. Pipeline run detail records model_trace for every AI-powered layer (T4)

Implementation order: T5 (registry) → T1+T2+T3+T4+T6 (dependent features) → T7 (frontend) → Runtime consumers → Old entrance cleanup.

### /autoplan Final Gate (2026-05-22)

Approved. 3 CEO dual voices, Design + Eng subagent reviews, 10 implementation tasks.

#### Cross-Phase Themes (multi-model consensus)

1. **"场景"抽象可能是欠设计的** — CEO Codex + Eng subagent 一致指出：5 个固定场景在工作流中看似整洁，但实际路由会很快需要 provider capability、quality tier、latency、cost、region 等维度。v1 的 `model_type` 映射到 scene_key 是合理的起点，但应预留扩展点。

2. **迁移信任危机** — CEO + Design + Eng 三个子代理独立提出：自动迁移假设过于乐观。"空密钥"的定义模糊、迁移后全红点的 UX、增量 vs 覆盖的策略都需要更明确的处理。

3. **配置就绪 ≠ 管线就绪** — CEO Codex + Claude 子代理同时指出：连接测试通过 ≠ 供应商能生成目标资源。"基于 API key 已配置 + 测试通过 = 就绪"的判断会产生虚假信心。

#### New Security Findings (from Eng subagent)

- **T8 (P1):** Schema endpoint 需要显式的 auth middleware 要求，防止未认证的信息泄露
- **T9 (P1):** 连接测试存在 SSRF 风险 — 拒绝私有/环回/链路本地 IP 的 base_url
- **T10 (P2):** 迁移策略改为仅增量（INSERT only, never UPDATE），冲突生成报告

#### Dual Voice Consensus

| Phase | Source | Confirmed | Disagree | Key Finding |
|-------|--------|-----------|----------|-------------|
| CEO | codex+subagent | 2 | 2 | 产品定位应重定义为"管线就绪"而非"模型中心" |
| Design | subagent-only | 3 | 0 | 自定义字段编辑器 UX 未定义 → 实施时最大风险 |
| Eng | subagent-only | 4 | 0 | SSRF + schema auth + 迁移增量策略 → 3 个新增 P1 |

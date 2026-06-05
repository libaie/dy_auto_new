<!-- /autoplan restore point: C:\Users\HNXE\.gstack\projects\dy_auto\feature-video-review-fixes-image-creation-autoplan-restore-20260527-164021.md -->

# Image Creation Workbench Design

## Summary

Add an independent image creation workbench to dy_auto. The workbench supports a provider-neutral image generation capability matrix:

- Text to image: generate images from prompts.
- Image to image: edit or redraw an existing image with a prompt.
- Multi-reference image generation: generate an image from 2 or more reference images plus a prompt.
- Image set generation: generate a coherent group of related images from text, one reference image, or multiple reference images.

dy_auto remains the orchestration and review layer. Pixelle-Video remains the execution layer. dy_auto owns model configuration, task creation, Pixelle runtime config delivery, task status sync, asset storage, AI review, human review, and later use of approved images in image-to-video production.

Seedream is the first provider adapter, not the business model. The design must allow later image providers such as OpenAI, Flux, ComfyUI, RunningHub, or other custom providers to add their own image capabilities without changing the dy_auto workflow.

The first version does not add a mask editor. Image-to-image uses whole-image editing, style redraw, multi-reference fusion, and prompt-guided changes.

## Confirmed Product Decisions

- Execution owner: Pixelle-Video.
- dy_auto owner scope: page, model configuration, task orchestration, asset library, review, and downstream usage.
- Entry: independent image creation page, not only a button inside video review.
- Modes: text to image, image to image, multi-reference image generation, and image set generation in one page.
- Source image options: local upload, existing image asset, and public image URL.
- Reference image options: one or many sources, depending on selected model capability.
- Generated results enter dy_auto asset and review flow.
- First version does not support mask upload or online mask painting.
- Existing video production generation flow must not be blocked or interrupted by this standalone tool.
- The model center must describe image capabilities declaratively. Seedream-specific parameters live under provider options, not hard-coded UI branches.
- For Volcengine Ark image generation, the project must use the previously required Plan V3 path: `https://ark.cn-beijing.volces.com/api/plan/v3/images/generations`. Do not use `/api/v3/images/generations`.

## Goals

- Let users create images independently before video generation.
- Let users edit images by using a source image plus an edit prompt.
- Let users generate images from multiple reference images.
- Let users generate coherent image groups for character sheets, scene boards, storyboard variants, and style exploration.
- Let model configuration center expose a dedicated `Image · 以图改图` scene.
- Let model configuration center expose capability metadata so future image models can be added without changing the business workflow.
- Send all execution work to Pixelle with dy_auto-resolved runtime model config.
- Persist generated images in dy_auto with task trace, prompt trace, model trace, source trace, and review status.
- Reuse dy_auto review concepts and UI patterns while avoiding a hard dependency on `VideoProductionRun`.
- Allow approved images to be selected later as image-to-video inputs.

## CEO Product Review

Verdict: proceed as a production-control wedge, not as a generic image toy.

The business reason this page should exist is not "dy_auto can make images." The product reason is that long video production wastes time and provider spend when weak images reach the image-to-video stage. The image creation workbench should create, repair, review, and approve visual assets before they become video inputs.

### Premise Challenge

- Right problem: yes, if the workbench becomes the upstream visual asset control point for automated video production.
- Wrong framing to avoid: a standalone prompt form that generates nice images but does not feed style lock, storyboard, image review, or image-to-video.
- Outcome: reduce failed video-stage attempts, improve character/scene consistency, and make reference assets reusable across episodes.
- If we do nothing: operators keep discovering bad images only after Pixelle/Seedance video generation has already spent time and budget.

### Implementation Alternatives

| Approach | Completeness | Effort | Risk | Decision |
|---|---:|---|---|---|
| Minimal standalone image form | 5/10 | S | Medium | Reject. It ships fast but becomes another disconnected tool. |
| Production workbench with review and downstream bridges | 9/10 | M | Medium | Choose this. It keeps scope bounded while serving the video production promise. |
| Full unified media asset platform | 8/10 | XL | High | Defer. It is directionally right but too broad for the first image creation slice. |

The chosen approach is the middle path: a real workbench, dedicated image records, provider-neutral model capability handling, review gates, and explicit bridges into video production.

### North-Star Product Flow

```text
one sentence / episode brief
  -> style lock and storyboard
  -> identify missing or weak visual assets
  -> create or repair images in 图像创作
  -> persist provider output to dy_auto storage
  -> AI review, then human review when needed
  -> approved asset becomes selectable as:
       character anchor
       scene reference
       style reference
       storyboard/frame replacement
       image-to-video first-frame input
  -> video production continues through the staged control room
```

The user-facing promise remains automatic video production. This page is a visible intervention and preparation surface for images, not a required manual stop for every frame.

### Scope Accepted By CEO Review

- Add approved-asset destination metadata so an image can be marked for `character_anchor`, `scene_reference`, `style_reference`, `storyboard_frame`, or `image_to_video_input`.
- Add task-level cost visibility before and after generation: estimated image count, selected model, provider options that affect cost, final usage, and cost status.
- Add a high-cost confirmation rule when output count or provider options exceed configured thresholds.
- Add launch metrics for approval rate, downstream usage, cost per approved asset, failed persistence rate, and image-to-video rejection avoided.
- Add a first-class "repair from rejected asset" path so review failures become new image-to-image tasks instead of dead ends.

### Scope Still Not Accepted

- No full media asset platform or campaign asset manager.
- No bulk creative campaign generation outside video-production needs.
- No marketplace of providers or public template store.
- No mask editor in this slice.
- No forced human review for every successful image when AI confidence is high and project policy allows auto-approval.

### Launch Criteria

The first release should be considered successful only if these are true:

- A user can create a text-to-image result, persist it, review it, approve it, and select it as an image-to-video source.
- A user can take a rejected or weak image and start `再次改图` without re-uploading or losing lineage.
- A user can see which model, provider endpoint, capability, prompt, references, cost, and review result produced each approved asset.
- The page can run with Seedream first, but the UI and backend validation are driven by capability metadata rather than Seedream-only branches.
- Existing automatic video generation still runs without requiring this page unless the workflow explicitly needs image repair or manual preparation.

### Product Metrics

| Metric | Why it matters |
|---|---|
| Time to first persisted image | Measures whether the workbench feels operational, not decorative. |
| AI approval rate and human override rate | Shows whether generation quality and audit policy are calibrated. |
| Rejected-to-repaired conversion rate | Shows whether `再次改图` prevents dead-end review queues. |
| Approved image downstream usage rate | Proves the page feeds video production instead of becoming isolated. |
| Cost per approved image | Keeps provider spend tied to usable output, not raw attempts. |
| Temp URL persistence failure rate | Catches the most dangerous asset-loss path before users trust the library. |
| Image-stage rejection before video-stage spend | Measures whether early review avoids wasted video generation. |

### Failure Modes To Avoid

- Hidden provider work: every running, failed, pending, and partially completed task must be visible.
- Review bypass: unapproved standalone images must not silently enter image-to-video.
- Provider lock-in: Seedream can be the first adapter, but the product contract must stay capability-driven.
- Asset orphaning: generated images without destination, lineage, or review state become clutter and should be filterable.
- Manual workflow creep: the workbench should help exception handling and asset preparation, not force users to manually drive every video frame.

## Non-Goals

- No mask editor in the first version.
- No visual timeline editor.
- No direct provider call from the frontend.
- No second Pixelle model configuration UI.
- No Douyin publishing loop.
- No full generic media asset platform rewrite.
- No mandatory paid-provider E2E gate before mocked flows are stable.
- No provider-specific UI page for Seedream only.
- No blind pass-through form that exposes raw provider JSON as the primary UX.

## Current Baseline

Relevant current code:

- `server/app/data/model_schema_data.py` defines `image_generation`, but not `image_editing`.
- `server/app/routers/ai_config.py` seeds `Seedream 5.0 Lite` for `image_generation`.
- `server/app/services/pixelle_stage_client.py` has `submit_image_batch`, `submit_video_batch`, and `submit_compose`.
- `server/app/db_models.py` has `VideoProductionRun`, `VideoProductionAsset`, and `VideoReviewRecord`.
- `VideoProductionAsset.run_id` and `VideoProductionAsset.episode_id` are non-null.
- `VideoReviewRecord.run_id` is non-null.
- `web/src/views/AIVideoReviewPage.vue` provides video production review and regeneration actions.

Important constraint: standalone image creation cannot be safely stored directly in `VideoProductionAsset`, because independent images may not have a video run or episode. Forcing hidden runs or dummy episodes would make review, costs, and lineage inaccurate. The design therefore adds a focused image creation asset model and bridges approved assets into video production only when they are used downstream.

## Chosen Approach

Use a dedicated image creation task and asset flow:

```text
ImageCreationPage
  -> dy_auto image creation API
  -> normalize common request into image capability contract
  -> resolve model scene
  -> pick provider adapter through Pixelle
  -> Pixelle image create task
  -> dy_auto task sync
  -> ImageCreationAsset records
  -> AI review
  -> human review when needed
  -> approved asset can be selected by image-to-video flow
```

Scene resolution:

```text
text_to_image                 -> image_generation
image_to_image                -> image_editing
multi_reference_to_image      -> image_editing
text_to_image_set             -> image_generation
image_to_image_set            -> image_editing
multi_reference_to_image_set  -> image_editing
```

## Engineering Review

Verdict: implementable after locking down idempotency, transactional sync, storage lifecycle, and migration constraints.

### Scope Challenge

Existing code already solves important parts of this problem:

- `AIModel`, `model_schema_data.py`, and `runtime_model_config.py` already provide the model center and runtime config handoff.
- `pixelle_stage_client.py` already centralizes Pixelle stage calls.
- `VideoProductionRun`, `VideoProductionAsset`, and `VideoReviewRecord` already provide a proven pattern for stage assets, review records, versioning, provider trace, and latest-review guards.
- Existing video production tests provide the right shape for mocked Pixelle E2E, named errors, review latest-version guards, and frontend control-room coverage.

The plan should not build a second model center, a second Pixelle config system, or a full media asset platform. It should add the smallest dedicated image creation slice that can safely store standalone images without dummy video runs.

### Required Engineering Decisions

| Area | Decision |
|---|---|
| API router | Add a dedicated `image_creation` router instead of expanding `video_production.py` or `audit.py`. |
| Service boundary | Add an `image_creation_service` for validation, task creation, sync, persistence, AI review trigger, and review updates. |
| Pixelle client | Add `submit_image_create` beside `submit_image_batch`; do not overload the production frame batch endpoint. |
| Model resolver | Add `resolve_image_model_for_capability` instead of weakening the generic `resolve_runtime_model_config` contract. |
| Review storage | Use dedicated `ImageCreationReviewRecord`; do not make `VideoReviewRecord.run_id` nullable for this feature. |
| Asset bridge | Use metadata for the first release, but add a migration-ready nullable `source_image_creation_asset_id` only if downstream queries need joins. |
| Worker model | First version may use request-triggered `sync` and existing polling. Do not introduce a new queue or worker just for this slice. |

### Processing Pipeline

```text
POST /api/image-creation/tasks
  -> validate mode and source/reference contract
  -> resolve scene_key + capability_key
  -> resolve model config and redact trace copy
  -> validate provider-neutral limits and provider_options_schema
  -> estimate cost and enforce confirmation/budget gate
  -> verify or stage source/reference URLs for Pixelle reachability
  -> insert ImageCreationTask(status=queued/running)
  -> submit Pixelle /api/stages/images/create
  -> persist pixelle_task_id and running status

POST /api/image-creation/tasks/{id}/sync
  -> load task with write guard
  -> poll Pixelle stage task
  -> if pending: update task status only
  -> if failed: write named error and stop
  -> if completed: copy provider temp/base64 outputs to dy_auto storage
  -> upsert ImageCreationAsset rows by idempotency key
  -> record per-image provider failures
  -> finalize task status and usage/cost
  -> trigger AI review once per new persisted asset
```

### State Machines

Task status:

```text
queued -> running -> completed
                 \-> completed_with_warnings
                 \-> failed
queued/running -> cancelled
```

Asset status:

```text
review_pending -> approved
               \-> rejected -> regenerating -> review_pending
               \-> failed
```

Cost status:

```text
not_estimated -> estimated -> confirmed -> finalized
                         \-> blocked
```

Implementation must reject invalid backward transitions. For example, `approved` cannot become `review_pending` without creating a new asset version, and `completed` task sync must be idempotent.

### Migration And Index Requirements

Add a migration for the three new tables and include these constraints/indexes:

- `image_creation_tasks.pixelle_task_id` indexed and unique when present.
- `image_creation_tasks.status`, `series_id`, `episode_id`, `model_scene_key`, `capability_key`, and `created_at` indexed for list and review filters.
- `image_creation_assets.task_id`, `status`, `destination_role`, `series_id`, `episode_id`, `group_id`, `source_asset_id`, and `is_latest` indexed.
- `image_creation_assets` must have an idempotency constraint that prevents duplicate assets for repeated sync calls. Recommended key: `(task_id, group_id, group_index, version)` when `group_id` exists, plus `(task_id, prompt_hash, version)` fallback for single-image results.
- `image_creation_review_records.asset_id`, `task_id`, `status`, and `(asset_id, asset_version, is_latest_asset_review)` indexed.
- JSON fields are acceptable for provider traces, references, and context snapshots, but not for primary list filters such as `status`, `destination_role`, `series_id`, and `episode_id`.

### Idempotency And Concurrency Rules

- Create task should accept or generate an idempotency key. If the frontend retries after a timeout, dy_auto must not submit duplicate Pixelle tasks for the same request.
- Sync must run inside a transaction and upsert assets. Repeated polling, double-click sync, or two tabs must not duplicate `ImageCreationAsset` rows.
- AI review trigger must be once per persisted asset version. Repeated sync must not create duplicate latest AI review records.
- Human review must check `asset_version` and reject stale actions with `STALE_ASSET_VERSION`.
- `再次改图` must create a new task and link `source_asset_id`; it must not mutate the rejected asset in place.
- If Pixelle returns partial results, successful assets are persisted and failed positions are recorded without losing the original group order.

### Storage Lifecycle

- Uploaded source images, copied provider outputs, thumbnails, and base64-decoded files need separate directories or prefixes.
- Store `checksum` and `size_bytes` when files are persisted, even if the first table design keeps them in `metadata_json`.
- Add a cleanup policy for failed temporary uploads and unreferenced provider-copy failures. Do not delete approved assets while downstream usage exists.
- Provider temporary URLs are not trusted as final asset URLs. The sync path must copy them before setting `storage_status = persisted`.

### Security Boundary

- Public URL sources must reject localhost, link-local, metadata service, private network, and unsupported schemes unless explicit local development mode allows them.
- Model runtime config can be passed to Pixelle only in the request body. Stored task traces must use `redact_runtime_model_config`.
- Provider option schema is validation input, not an authorization boundary. Pixelle adapters must validate final provider constraints again.
- Upload validation should check MIME type, file extension, size, pixel count, and image dimensions before creating any task.

### Test Coverage Diagram

```text
BACKEND CODE PATHS                                     USER FLOWS
[+] model schema                                       [+] 文生图
  ├── [GAP] image_editing scene                          ├── [GAP] create -> sync -> persisted asset
  └── [GAP] capability metadata                          └── [GAP] approved asset selectable for 图生视频

[+] model resolution                                   [+] 以图改图
  ├── [GAP] explicit model supports capability            ├── [GAP] source asset -> new task -> lineage kept
  ├── [GAP] explicit model rejects unsupported mode        └── [GAP] rejected asset -> 再次改图
  └── [GAP] default fallback supports legacy text image

[+] task creation                                      [+] 多图参考/组图
  ├── [GAP] mode/source/reference validation              ├── [GAP] mixed upload/asset/url references
  ├── [GAP] provider option schema validation             ├── [GAP] capability limit shown and enforced
  ├── [GAP] cost confirmation and budget block            └── [GAP] partial provider failure preserves order
  └── [GAP] Pixelle unreachable named error

[+] sync/persistence                                   [+] 审查与下游使用
  ├── [GAP] pending task stays pending                    ├── [GAP] AI review success/failure visible
  ├── [GAP] completed task copies temp URLs               ├── [GAP] stale human approval rejected
  ├── [GAP] repeated sync is idempotent                   └── [GAP] unapproved asset blocked downstream
  └── [GAP] base64 output persisted before review
```

All gaps above must become implementation tests. Backend uses `pytest`; frontend uses `vitest` with Vue Test Utils.

### Performance Notes

- Asset listing must paginate. Do not return all generated images for a series.
- Use indexed columns for filters and keep JSON fields for snapshots only.
- Generate thumbnails or use provider thumbnails to avoid loading full-resolution images in grid views.
- Polling should use bounded intervals and stop after terminal states. Avoid unbounded frontend polling across old tasks.
- Group generation can create up to 15 assets per task for Seedream; the design is safe for this scale but should not be reused as a bulk campaign generator without queueing.

### Failure Mode Map

| Failure | Planned handling | Test required |
|---|---|---|
| Frontend retries create after timeout | Idempotency key prevents duplicate Pixelle task | Yes |
| Two tabs call sync for the same completed task | Transactional upsert prevents duplicate assets/reviews | Yes |
| Provider returns temporary URL that expires before copy | `TEMP_URL_PERSIST_FAILED`; asset not reviewable | Yes |
| Pixelle cannot fetch dy_auto upload URL | `SOURCE_STORAGE_NOT_REACHABLE` before provider call | Yes |
| AI review provider fails | Asset remains visible for human review with `AI_REVIEW_FAILED` | Yes |
| Human approves stale asset version | `STALE_ASSET_VERSION` | Yes |
| Unapproved asset selected for video | `IMAGE_REVIEW_REQUIRED` | Yes |
| Cost estimate exceeds threshold | `IMAGE_COST_CONFIRMATION_REQUIRED` | Yes |

No critical silent-failure gap remains after the above requirements are implemented.

### Worktree Parallelization Strategy

| Step | Modules touched | Depends on |
|---|---|---|
| Model schema and resolver | `server/app/data`, `server/app/services`, `server/tests` | None |
| DB models and migration | `server/app/db_models.py`, `server/alembic`, `server/tests` | None |
| Pixelle image create client | `server/app/services`, `server/tests` | Model schema |
| Image creation API/service | `server/app/routers`, `server/app/services`, `server/tests` | DB models, resolver, Pixelle client |
| Frontend route/workbench/API client | `web/src/router`, `web/src/api`, `web/src/views`, `web/src/__tests__` | API contract |
| Downstream selector bridge | `server/app/services`, `web/src/views`, `server/tests`, `web/src/__tests__` | API/service |

Parallel lanes:

- Lane A: model schema and resolver -> Pixelle image create client.
- Lane B: DB models and migration.
- Lane C: frontend shell and API client can start from the documented contract, then integrate after backend routes land.
- Lane D: image creation API/service waits for Lane A and Lane B.
- Lane E: downstream selector bridge waits for Lane D.

Conflict flags: Lane A and Lane D both touch `server/app/services`; merge Lane A first or keep service file boundaries strict.

## Model Configuration

Add a new scene to the model schema while keeping the existing `image_generation` scene:

| Scene key | Label | model_type | Used by |
|---|---|---|---|
| `image_generation` | `Image · 画面生成` | `image` | Text-to-image and text-to-image-set modes |
| `image_editing` | `Image · 以图改图` | `image` | Image-to-image, multi-reference, and image-set modes that use source images |

Suggested scene fields:

| Field | Type | Default | Notes |
|---|---|---|---|
| `default_size` | string/select | `1440x2560` | Provider adapters validate exact allowed values. |
| `default_quality` | select | `hd` | Same shape as image generation. |
| `edit_strength` | number | `0.65` | Optional provider hint for how strongly to change the source image. |
| `preserve_subject` | boolean | `true` | Optional prompt/runtime hint for keeping identity and composition. |
| `supports_stream` | boolean | provider default | Whether the adapter can stream partial image outputs. |
| `supports_image_set` | boolean | provider default | Whether the adapter can return a coherent image group. |
| `max_reference_images` | number | provider default | Maximum accepted reference image count. |
| `max_output_images` | number | provider default | Maximum generated images per request. |
| `supported_output_formats` | string[] | provider default | Example: `jpeg`, `png`. |
| `supports_watermark_toggle` | boolean | provider default | Whether UI may show a watermark switch. |

Add a provider capability section to `AIModel.config_json`:

```json
{
  "scene_key": "image_editing",
  "capabilities": {
    "text_to_image": false,
    "image_to_image": true,
    "multi_reference_to_image": true,
    "text_to_image_set": false,
    "image_to_image_set": true,
    "multi_reference_to_image_set": true
  },
  "limits": {
    "min_reference_images": 1,
    "max_reference_images": 14,
    "max_output_images": 15,
    "max_reference_plus_output_images": 15,
    "max_input_image_mb": 30,
    "max_input_pixels": 36000000,
    "aspect_ratio_range": [0.0625, 16]
  },
  "supported_size_modes": ["preset", "pixels"],
  "supported_sizes": ["2K", "3K", "4K", "2048x2048", "1600x2848", "2304x4096"],
  "supported_output_formats": ["jpeg", "png"],
  "provider_options_schema": {
    "sequential_image_generation": ["disabled", "auto"],
    "max_images": { "type": "number", "min": 1, "max": 15 },
    "stream": { "type": "boolean" },
    "response_format": ["url", "b64_json"],
    "output_format": ["jpeg", "png"],
    "watermark": { "type": "boolean" },
    "optimize_prompt_mode": ["standard", "fast"],
    "web_search": { "type": "boolean" }
  }
}
```

The frontend reads this schema to render only supported controls. The backend validates against it before calling Pixelle. Pixelle adapters translate this provider-neutral contract into provider-specific payloads.

Default seed entry:

- Name: `Seedream 5.0 Lite Image Editing`
- model_type: `image`
- provider: `seedance`
- base_url: `https://ark.cn-beijing.volces.com/api/plan/v3`
- model_name: `doubao-seedream-5.0-lite`
- config_json.scene_key: `image_editing`
- config_json.capabilities: image-to-image, multi-reference image generation, image set generation

Do not duplicate API key storage. Use the existing AI model configuration secret handling.

### Seedream Adapter Mapping

The Seedream adapter is implemented inside Pixelle. dy_auto sends normalized image creation fields and provider options; Pixelle maps them to Ark image generation fields.

| dy_auto concept | Seedream field | Notes |
|---|---|---|
| Model identifier | `model` | `doubao-seedream-5.0-lite` by default. |
| Prompt | `prompt` | Keep prompts concise. Seedream docs recommend avoiding overly long prompts. |
| Reference images | `image` | String for one image, array for multiple images. URL or Base64 accepted by provider, dy_auto should prefer app-served URL. |
| Single image output | `sequential_image_generation = disabled` | Text-to-image, single-image edit, or multi-reference-to-image. |
| Image set output | `sequential_image_generation = auto` | Text, one image, or multiple references can create a coherent group. |
| Max generated images | `sequential_image_generation_options.max_images` | Seedream range is 1-15. For multi-reference groups, reference count plus output count must be no more than 15. |
| Size | `size` | Seedream supports presets such as `2K`, `3K`, `4K` and pixel values. Adapter validates per model. |
| Streaming | `stream` | Optional. The first version may store streamed partial results as task events; non-streaming is the default. |
| Output format | `output_format` | Seedream 5.0 lite supports `jpeg` and `png`. |
| Response format | `response_format` | Prefer `url`; if `b64_json`, Pixelle must persist it and return a dy_auto-accessible URL. |
| Watermark | `watermark` | Default provider behavior is true. dy_auto may expose a switch when model supports it. |
| Prompt optimization | `optimize_prompt_options.mode` | Provider option, not a global dy_auto field. |
| Web search | `tools: [{ type: "web_search" }]` | Optional Seedream capability. Store actual usage from `usage.tool_usage.web_search`. |

Seedream provider output URLs are temporary and may expire after 24 hours. Pixelle or dy_auto must persist generated images to controlled storage before the task is considered complete.

### Capability-Aware Model Resolution

The current runtime model resolver can resolve by `scene_key`, but image creation also needs capability filtering. Otherwise dy_auto may pick the first enabled `image` model even when that model cannot handle multi-reference input or image-set output.

Add a resolver contract:

```python
resolve_image_model_for_capability(
    db,
    scene_key: str,
    capability_key: str,
    explicit_model_id: str | None = None,
) -> dict
```

Resolution rules:

1. If `explicit_model_id` is supplied, load that model, validate `enabled`, `model_type = image`, matching `scene_key`, and advertised `capabilities[capability_key] = true`.
2. If no explicit model is supplied, query enabled image models for the scene and choose the first model whose `config_json.capabilities` supports the requested capability.
3. Existing image models without `capabilities` are backward-compatible only for `text_to_image` under `image_generation`.
4. If no model supports the capability, return `IMAGE_CAPABILITY_UNSUPPORTED` with a repair route to the model center.
5. Runtime traces must record both `scene_key` and `capability_key`.

This resolver is part of the dy_auto orchestration layer. Pixelle still validates provider-specific limits before execution, but dy_auto should fail early when no configured model can satisfy the requested capability.

## Data Model

Add `ImageCreationTask`:

| Field | Notes |
|---|---|
| `id` | UUID. |
| `idempotency_key` | Optional client or server generated key to prevent duplicate task submission. |
| `request_hash` | Normalized prompt/source/reference/options hash used as idempotency fallback. |
| `mode` | `text_to_image`, `image_to_image`, `multi_reference_to_image`, `text_to_image_set`, `image_to_image_set`, or `multi_reference_to_image_set`. |
| `output_mode` | `single` or `image_set`. |
| `capability_key` | The selected provider-neutral capability. |
| `status` | `queued`, `running`, `completed`, `completed_with_warnings`, `failed`, `cancelled`. |
| `series_id` | Nullable context link. |
| `episode_id` | Nullable context link. |
| `prompt` | Required. |
| `negative_prompt` | Optional. |
| `source_type` | `upload`, `asset`, `url`, `mixed`, or null for text-to-image. |
| `source_url` | First resolved source URL for backward-compatible single-image cases. |
| `source_asset_id` | First source asset id for backward-compatible single-image cases. |
| `reference_images_json` | Ordered array of `{type, url, asset_id, role, name}` for one or many reference images. |
| `size` | Requested output size. |
| `count` | Requested output count. |
| `output_format` | Requested file format when supported. |
| `response_format` | `url` or provider-supported equivalent. dy_auto stores final URL regardless. |
| `watermark` | Optional requested watermark behavior. |
| `provider_options_json` | Provider-specific options validated against `provider_options_schema`. |
| `estimated_cost_json` | Pre-submit estimate when model pricing metadata is available. |
| `cost_status` | `not_estimated`, `estimated`, `confirmed`, `blocked`, or `finalized`. |
| `requires_cost_confirmation` | Whether the frontend must confirm a high-cost request before submission. |
| `storage_status` | `pending`, `persisted`, or `failed`. A task is not review-ready until returned provider outputs are persisted. |
| `model_scene_key` | `image_generation` or `image_editing`. |
| `model_trace_json` | Redacted runtime model trace. No secrets. |
| `pixelle_task_id` | Pixelle task id. |
| `partial_results_json` | Optional streamed or partially completed provider results. |
| `usage_json` | Provider usage summary such as generated images, tokens, web search calls, cost, and duration. |
| `error_code` | Named blocking error. |
| `error_message` | User-facing message. |
| `repair_action` | User-facing recovery action. |
| `created_at`, `updated_at`, `completed_at` | Timestamps. |

Add `ImageCreationAsset`:

| Field | Notes |
|---|---|
| `id` | UUID. |
| `task_id` | FK to `ImageCreationTask`. |
| `series_id` | Nullable context link. |
| `episode_id` | Nullable context link. |
| `asset_type` | `image`. |
| `url` | Public or app-served URL. |
| `local_path` | Optional storage path. |
| `thumbnail_url` | Optional. |
| `checksum` | Persisted file checksum when available. |
| `size_bytes` | Persisted file size when available. |
| `status` | `review_pending`, `approved`, `rejected`, `failed`, `regenerating`. |
| `version` | Version within task/source lineage. |
| `source_asset_id` | Previous image when generated by image-to-image. |
| `source_url` | Source URL snapshot. |
| `reference_images_json` | Ordered reference snapshot used to generate this asset. |
| `group_id` | Shared id for assets generated in the same coherent image group. |
| `group_index` | 1-based order within a generated image group. |
| `destination_role` | Optional intended use: `character_anchor`, `scene_reference`, `style_reference`, `storyboard_frame`, or `image_to_video_input`. |
| `destination_context_json` | Optional target context such as series, episode, scene, character, shot, segment, or storyboard frame id. |
| `downstream_usage_json` | Where this asset has been used after approval. |
| `provider_error_json` | Per-image provider error when a group request partially fails. |
| `provider_task_id` | Provider task id when returned by Pixelle. |
| `pixelle_task_id` | Pixelle task id. |
| `prompt_hash` | Prompt/source hash for idempotency. |
| `is_latest` | Latest version marker for a lineage. |
| `metadata_json` | Prompt, source, references, size, output mode, model scene, cost, duration, usage, and provider metadata. |
| `storage_status` | `persisted` or `failed`. Assets with failed storage are not reviewable. |
| `created_at`, `updated_at` | Timestamps. |

Add `ImageCreationReviewRecord`:

| Field | Notes |
|---|---|
| `id` | UUID. |
| `asset_id` | FK to `ImageCreationAsset`. |
| `task_id` | FK to `ImageCreationTask`. |
| `review_type` | `ai` or `human`. |
| `status` | `approved`, `rejected`, `needs_human`, `failed`. |
| `score` | Optional. |
| `criteria_json` | Audit criteria. |
| `issues_json` | Audit issues. |
| `reviewer_user_id` | Optional human reviewer. |
| `model_trace_json` | Redacted audit model trace. |
| `comment` | Optional. |
| `asset_version` | Version snapshot. |
| `is_latest_asset_review` | Stale review guard. |
| `created_at` | Timestamp. |

Downstream bridge:

- Image-to-video selectors can read approved `ImageCreationAsset` records.
- Character, scene, style, storyboard, and segment selectors can read approved assets filtered by `destination_role`.
- The default selector list should show approved assets first and hide rejected assets unless the user is starting a repair flow.
- When an image is used inside a production run, create or reference the appropriate `VideoProductionAsset` for that run and preserve `source_image_creation_asset_id` in metadata or a nullable link column if the implementation needs queryable lineage.
- Do not create dummy `VideoProductionRun` rows for standalone image creation.

## dy_auto APIs

### Upload Source Image

```http
POST /api/image-creation/uploads
```

Multipart upload. Returns an app-served URL that Pixelle can fetch. The URL must be generated from a configured `DY_AUTO_PUBLIC_BASE_URL` or equivalent setting, not blindly from `localhost`, because Pixelle may run in a different process, container, or host.

Response:

```json
{
  "ok": true,
  "url": "http://localhost:8000/static/image-creation/uploads/source.png",
  "local_path": "..."
}
```

Upload URL rules:

- In local single-host development, `http://127.0.0.1:8000/...` may be acceptable if Pixelle runs on the same host.
- In Docker, LAN, or staging, dy_auto must return a URL reachable from Pixelle.
- If no reachable base URL is configured, return `SOURCE_STORAGE_NOT_REACHABLE` before creating a Pixelle task.
- Uploaded files may also be copied to Pixelle-owned staging storage when URL reachability cannot be guaranteed.

### Create Task

```http
POST /api/image-creation/tasks
```

Text-to-image request:

```json
{
  "mode": "text_to_image",
  "prompt": "赛博朋克风格女主角站在雨夜街头",
  "negative_prompt": "",
  "size": "1440x2560",
  "count": 2,
  "idempotency_key": "client-generated-key",
  "destination_role": "image_to_video_input",
  "cost_confirmation": false,
  "series_id": null,
  "episode_id": null
}
```

Image-to-image request:

```json
{
  "mode": "image_to_image",
  "prompt": "保持人物长相不变，改成夜晚霓虹灯场景",
  "negative_prompt": "",
  "source": {
    "type": "asset",
    "asset_id": "image-asset-id"
  },
  "size": "1440x2560",
  "count": 2,
  "series_id": null,
  "episode_id": null
}
```

Multi-reference image request:

```json
{
  "mode": "multi_reference_to_image",
  "prompt": "融合这些参考图，保持人物五官与服装，生成竖屏海报图",
  "negative_prompt": "",
  "reference_images": [
    { "type": "asset", "asset_id": "character-front" },
    { "type": "asset", "asset_id": "character-side" },
    { "type": "url", "url": "https://example.com/style.png", "role": "style" }
  ],
  "size": "2K",
  "count": 1,
  "provider_options": {
    "watermark": false,
    "output_format": "png"
  },
  "destination_role": "style_reference",
  "destination_context": { "series_id": "series-id" }
}
```

Image set request:

```json
{
  "mode": "multi_reference_to_image_set",
  "prompt": "基于角色参考图生成 6 张一致的漫剧分镜关键帧，包含远景、中景、近景和情绪特写",
  "reference_images": [
    { "type": "asset", "asset_id": "character-anchor-1", "role": "character" },
    { "type": "asset", "asset_id": "character-anchor-2", "role": "character" },
    { "type": "asset", "asset_id": "scene-anchor-1", "role": "scene" }
  ],
  "size": "3K",
  "count": 6,
  "provider_options": {
    "sequential_image_generation": "auto",
    "max_images": 6,
    "stream": false,
    "response_format": "url",
    "watermark": false
  },
  "destination_role": "storyboard_frame",
  "destination_context": { "episode_id": "episode-id", "shot_id": "shot-id" }
}
```

Backend validation:

- `text_to_image` and `text_to_image_set` do not require references.
- `image_to_image` and `image_to_image_set` require exactly one primary source image.
- `multi_reference_to_image` and `multi_reference_to_image_set` require at least two references.
- The selected model must advertise the requested `capability_key`.
- Reference count, output count, size, format, and provider options must pass model capability limits.
- Uploaded and asset-based references must resolve to Pixelle-reachable URLs before task submission.
- `destination_role` must be one of the supported downstream roles when supplied.
- If estimated cost exceeds the configured confirmation threshold, return `IMAGE_COST_CONFIRMATION_REQUIRED` unless `cost_confirmation = true`.

Response:

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
  }
}
```

### Read And Sync Task

```http
GET /api/image-creation/tasks/{task_id}
POST /api/image-creation/tasks/{task_id}/sync
```

`GET` returns task, assets, latest AI review, latest human review, and redacted model trace.

`sync` polls Pixelle, persists returned assets when complete, and triggers AI review. For providers that stream image results, `sync` may persist partial results to `partial_results_json` and create assets only when the adapter marks each image as durable.

### List Assets

```http
GET /api/image-creation/assets?status=approved&series_id=&episode_id=&destination_role=&source_type=
```

Used by the workbench, review queue, and image-to-video source selector.

### Review Asset

```http
POST /api/image-creation/assets/{asset_id}/review
```

Request:

```json
{
  "action": "approve",
  "comment": "可用于图生视频"
}
```

Supported actions: `approve`, `reject`.

### Start From Existing Asset

```http
POST /api/image-creation/assets/{asset_id}/edit
```

Convenience endpoint used by "再次改图". It creates a new image-to-image task using the selected asset as the source.

## Pixelle Protocol

dy_auto calls Pixelle with runtime model configuration. Secrets are runtime-only and must not be written to Pixelle history or dy_auto task model trace.

```http
POST /api/stages/images/create
```

Request:

```json
{
  "external_task_id": "dy_auto_image_creation_task_id",
  "mode": "multi_reference_to_image_set",
  "capability_key": "multi_reference_to_image_set",
  "output_mode": "image_set",
  "prompt": "基于角色参考图生成 6 张一致的漫剧分镜关键帧，包含远景、中景、近景和情绪特写",
  "negative_prompt": "",
  "reference_images": [
    {
      "url": "http://localhost:8000/static/image-creation/uploads/character-front.png",
      "role": "character",
      "asset_id": "optional"
    },
    {
      "url": "http://localhost:8000/static/image-creation/uploads/character-side.png",
      "role": "character",
      "asset_id": "optional"
    },
    {
      "url": "http://localhost:8000/static/image-creation/uploads/scene.png",
      "role": "scene",
      "asset_id": "optional"
    }
  ],
  "source_image_url": "http://localhost:8000/static/image-creation/uploads/character-front.png",
  "count": 6,
  "size": "3K",
  "output_format": "png",
  "response_format": "url",
  "provider_options": {
    "sequential_image_generation": "auto",
    "max_images": 6,
    "watermark": false,
    "stream": false
  },
  "model_config": {
    "scene_key": "image_editing",
    "provider": "seedance",
    "base_url": "https://ark.cn-beijing.volces.com/api/plan/v3",
    "api_key": "runtime-only",
    "model_name": "..."
  },
  "context": {
    "series_id": null,
    "episode_id": null,
    "source_asset_id": "optional"
  }
}
```

Task status can reuse:

```http
GET /api/stages/tasks/{stage_task_id}
```

Expected completed response:

```json
{
  "ok": true,
  "status": "completed",
  "assets": [
    {
      "asset_type": "image",
      "url": "https://...",
      "thumbnail_url": "https://...",
      "local_path": "output/...",
      "group_id": "group-001",
      "group_index": 1,
      "provider_task_id": "...",
      "metadata": {
        "duration_ms": 18000,
        "cost": 0.08,
        "size": "3K",
        "usage": {
          "generated_images": 6,
          "output_tokens": 12345,
          "total_tokens": 12345,
          "tool_usage": { "web_search": 0 }
        }
      }
    },
    {
      "asset_type": "image",
      "error": {
        "code": "PROVIDER_IMAGE_REJECTED",
        "message": "单张图片生成未通过提供商审核"
      },
      "group_id": "group-001",
      "group_index": 4
    }
  ]
}
```

Pixelle provider adapter rules:

- `/api/stages/images/create` is the standalone image creation endpoint.
- Existing `/api/stages/images/batch` remains for video production frame image generation.
- Adapters must translate normalized `mode`, `reference_images`, `count`, `size`, and `provider_options` into provider-specific payloads.
- Adapters must persist or copy temporary provider URLs before returning completed assets to dy_auto.
- Adapters may return per-image errors for image set requests. dy_auto stores successful images and records per-image failures without treating the whole task as failed unless the provider stops the request.

## Frontend Design

Add route and navigation item:

- Route: `/image-creation`
- Label: `图像创作`

Page layout:

```text
图像创作
  文生图 | 以图改图 | 多图参考 | 组图生成

左侧参数区
  文生图:
    提示词
    反向提示词
    尺寸
    数量
    输出模式: 单图 / 组图
    关联系列/剧集

  以图改图:
    原图来源: 上传图片 | 选择资产 | 图片 URL
    修改要求
    反向提示词
    尺寸
    数量
    输出模式: 单图 / 组图
    关联系列/剧集

  多图参考:
    参考图列表: 上传图片 | 选择资产 | 图片 URL
    每张参考图可标记角色、场景、风格、构图
    生成要求
    尺寸
    数量
    输出模式: 单图 / 组图
    关联系列/剧集

右侧任务与结果区
  当前任务状态
  Pixelle 任务
  使用模型
  能力匹配结果
  目标用途: 角色锚点 / 场景参考 / 风格参考 / 分镜帧 / 图生视频
  耗时/费用
  高成本确认
  错误与修复动作
  结果图片网格
  组图顺序与局部失败提示
  审查状态
  操作: 审查 / 批准 / 驳回 / 再次改图 / 用于图生视频
```

UX rules:

- All visible workflow labels must be Chinese.
- Do not use browser `prompt()` for review or edit instructions.
- Image-to-image submit is disabled until a source image is resolved.
- Multi-reference modes are disabled until the selected model advertises the matching capability.
- The UI must show reference count limits from the selected model, such as Seedream's 14 reference image limit.
- If output mode is group, the UI must show model max output and reference-plus-output limits.
- Public URL input must show whether Pixelle can fetch it.
- Upload source must show final resolved URL before submission.
- Existing asset picker defaults to approved assets, with an optional repair path from rejected assets.
- Destination role must be visible when supplied, because it decides where the approved image can be reused.
- High-cost requests must show estimated count, selected model, and confirmation status before submission.
- Generated assets stay on the page after sync and also appear in the review queue.
- Provider-specific controls live in an advanced section and are generated from schema. Examples: `水印`, `输出格式`, `流式返回`, `提示词优化`, `联网搜索`.

### Design Review Findings

Initial design score: 6/10. The original plan had the right workflow shape, but it did not yet specify hierarchy, interaction states, responsive behavior, or how the page should reuse current dy_auto UI patterns. After this review, target design score is 8.5/10 because the missing decisions below are now explicit enough for implementation.

No project `DESIGN.md` was found. The first implementation should therefore reuse the closest existing operational screens instead of inventing a separate visual language. Visual mockups were not generated in this review because the local gstack designer/browser helpers were unavailable in this environment.

### Existing UI Patterns To Reuse

- Reuse the model center's split workspace pattern from `web/src/views/AIConfigPage.vue`: left navigation or form rail, right detail surface, loading skeletons, empty states, and compact form controls.
- Reuse review-state language and review actions from `web/src/views/AIVideoReviewPage.vue`, but localize visible controls to Chinese and avoid browser prompt dialogs.
- Reuse task progress and transparency patterns from `web/src/views/VideoProductionMonitorPage.vue`: current stage, model trace, elapsed time, failure reason, and repair action must be visible.
- Place the navigation entry under the existing `AI 视频` group in `web/src/constants/navigation.js`, near `AI 视频审查` and `AI 模型配置`, so users find image creation as part of the production toolchain.

### Information Architecture

The page is a production workbench, not a landing page or gallery. First-screen hierarchy:

1. Mode and prompt/source input: users must immediately know whether they are doing `文生图`, `以图改图`, `多图参考`, or `组图生成`.
2. Capability fit and validation: the selected model, supported limits, missing source images, and incompatible mode warnings must be visible before submission.
3. Results, review, and downstream use: generated assets must show task state, review state, and `用于图生视频` actions without leaving the page.

Desktop layout:

```text
顶部: 页面标题 + 模式切换 + 当前模型能力摘要 + 生成按钮

左栏: 参数表单
  提示词 / 来源 / 参考图 / 尺寸 / 数量 / 关联系列剧集

中区: 来源与参考图画板
  上传、资产、URL 来源统一展示；支持排序、角色/场景/风格标签

右栏: 任务与结果
  Pixelle 状态、模型追踪、错误修复、结果网格、审查动作、下游使用

底部或抽屉: 高级提供商参数
  由 provider_options_schema 渲染，默认折叠
```

### Interaction State Coverage

| Area | Loading | Empty | Error | Success | Partial |
|---|---|---|---|---|---|
| Model capability | Show capability skeleton while config loads. | Show `请先配置可用图像模型`. | Show named model error and jump action to model center. | Show selected scene, model, limits, and supported modes. | Show supported modes and disable only unsupported controls. |
| Source/reference board | Show upload or asset loading state. | Show mode-specific empty guidance in Chinese. | Show unreachable URL, unsupported format, or size error. | Show resolved dy_auto-accessible URLs and reference roles. | Keep valid references and mark failed references inline. |
| Create task | Button shows submitting state and is not duplicated. | Disabled until prompt and required sources are valid. | Show named repair action near the button. | Create task and start polling. | For group generation, show created task even if some slots later fail. |
| Cost and destination | Show estimate loading when pricing metadata is available. | Show `未指定目标用途` but allow creation. | Show budget block or invalid destination repair action. | Show estimated/final cost and destination role. | Show per-asset cost when group results partially fail. |
| Task progress | Show queued/running/progress text and elapsed time. | No current task message. | Show Pixelle error, dy_auto error code, and retry action. | Show persisted assets and review readiness. | Show successful assets plus failed slots with retry controls. |
| Result grid | Use stable image tiles with skeleton previews. | Show no-result state tied to the current mode. | Show per-asset load failure and retry. | Show image preview, prompt trace, model trace, and review badge. | Preserve group order and mark failed or missing positions. |
| Review actions | Disable while AI review is running. | Hide actions until assets exist. | Route AI failure to human review with visible marker. | Allow approve, reject, and edit again from each selected asset. | Allow approving successful assets independently. |

### User Journey

1. User lands on `图像创作` and sees mode tabs plus the current model's capability summary, so the page feels like a controlled production tool.
2. User chooses a mode. The form changes only where the workflow differs; common fields stay stable to reduce disorientation.
3. User adds a prompt and source/reference images. The UI validates capability limits early and shows resolved source URLs before submission.
4. User submits. The right panel shows dy_auto orchestration, Pixelle task status, model trace, elapsed time, and cost/usage when available.
5. User inspects results. Assets stay visible with review state, group order, and source lineage.
6. User approves, rejects, or selects `再次改图`. Rejected assets cannot be used for image-to-video unless they are repaired and approved.
7. User selects `用于图生视频` only after approval. This keeps the standalone tool connected to the existing production chain without interrupting automatic video generation.

### Visual Direction

- Use a quiet operational workspace: dense but readable controls, restrained colors, clear panels, and strong image previews.
- Do not create a hero page, decorative gradient background, nested card stacks, or marketing-style layout.
- Cards are only for individual image assets, modals, or repeated results. Page sections should be full-width layout regions or unframed panels.
- The strongest visual element should be the selected source/reference board and generated result grid, not explanatory copy.
- Primary actions use Chinese verb labels: `生成`, `同步`, `批准`, `驳回`, `再次改图`, `用于图生视频`.

### Responsive And Accessibility Requirements

- Desktop `>=1280px`: use the three-zone layout of form, reference board, and task/result panel.
- Tablet `768px-1279px`: keep form and reference board side by side when space allows; move task/result below with a sticky task summary.
- Mobile `<768px`: use a single-column flow with sticky mode tabs, collapsed advanced options, and drawer-style asset/reference pickers.
- Every input must have a visible label. Do not rely on hint text as the only label.
- Task status changes must be announced with `aria-live="polite"` or equivalent.
- Image tiles need descriptive alt text based on mode, prompt summary, and asset index.
- Keyboard users must be able to switch modes, add/remove/reorder references, open asset details, approve/reject, and trigger `再次改图`.
- Focus rings must remain visible, touch targets should be at least 44px, and text contrast should meet WCAG AA for normal text.

### Design Not In Scope

- No full design system rewrite before this page ships.
- No unified media review center in the first version; image review remains local to the workbench.
- No visual mask editor or brush-based edit canvas in the first version.
- No generated visual mockup is attached to this plan because local design tooling was unavailable during this review.

### Design Review Completion Summary

| Review area | Before | After |
|---|---:|---:|
| Information architecture | 6/10 | 9/10 |
| Interaction states | 5/10 | 9/10 |
| User journey | 6/10 | 8/10 |
| AI-slop risk control | 7/10 | 9/10 |
| Design system alignment | 5/10 | 8/10 |
| Responsive and accessibility | 4/10 | 8/10 |
| Decisions resolved | 3 | 11 |

Plan is design-complete for implementation planning. Run a live visual QA pass after the frontend is implemented.

## Review Flow

AI review:

- Trigger after completed task assets are persisted.
- Use existing `quality_audit` model resolution.
- Store audit result in `ImageCreationReviewRecord`.
- If AI approves with enough confidence, asset may be marked `approved` according to current project policy.
- If AI rejects, has low confidence, or fails, asset remains visible for human review.

Human review:

- Operators can approve or reject assets from the image creation page.
- Existing AI video review page can be extended later to a unified media review page, but first version can keep image creation review local to this page.

Downstream usage:

- Only approved image creation assets are selectable as standard image-to-video inputs by default.
- Approved assets may also be selected as character anchors, scene references, style references, and storyboard frame replacements when their `destination_role` matches the target.
- Changing an approved asset's downstream destination should create an audit event or metadata version, because it changes how future video generation may reuse it.
- A repair flow may allow editing a rejected asset, but not using it directly for video generation.

## Named Errors

| Code | Trigger | Repair action |
|---|---|---|
| `IMAGE_MODEL_MISSING` | No enabled `image_generation` model | Configure `Image · 画面生成`. |
| `IMAGE_EDIT_MODEL_MISSING` | No enabled `image_editing` model | Configure `Image · 以图改图`. |
| `IMAGE_CAPABILITY_UNSUPPORTED` | Selected model does not support requested capability | Choose a compatible model or change mode. |
| `SOURCE_IMAGE_REQUIRED` | image-to-image without source | Upload, select, or paste a source image. |
| `REFERENCE_IMAGES_REQUIRED` | multi-reference mode without enough references | Add required reference images. |
| `REFERENCE_IMAGE_LIMIT_EXCEEDED` | Reference count exceeds model limit | Remove references or choose a model with a higher limit. |
| `SOURCE_ASSET_NOT_FOUND` | Selected source asset does not exist | Pick another asset. |
| `SOURCE_URL_UNREACHABLE` | Pixelle cannot fetch source URL | Upload the image or use a reachable URL. |
| `SOURCE_STORAGE_NOT_REACHABLE` | Uploaded or internal asset URL is not reachable from Pixelle | Configure dy_auto public media base URL or Pixelle staging copy. |
| `IMAGE_SIZE_UNSUPPORTED` | Requested size is not supported by the selected model | Pick an allowed size. |
| `OUTPUT_COUNT_UNSUPPORTED` | Requested output count exceeds capability limits | Lower count or use image set mode. |
| `PROVIDER_OPTION_INVALID` | Provider option does not match schema | Fix the advanced option. |
| `DOWNSTREAM_DESTINATION_INVALID` | Requested destination role or context is not supported | Pick a supported destination or clear the destination. |
| `IMAGE_COST_CONFIRMATION_REQUIRED` | Estimated provider spend exceeds confirmation threshold | Confirm the task cost or reduce count/options. |
| `IMAGE_BUDGET_EXCEEDED` | Request exceeds configured image generation budget | Adjust budget, lower count, or pause the task. |
| `IMAGE_TASK_CONFLICT` | Same idempotency key is reused with a different request hash | Retry with a new task or restore the original request. |
| `PIXELLE_TASK_FAILED` | Pixelle returns failed status | Show Pixelle error and allow retry. |
| `PIXELLE_TASK_PENDING` | Pixelle task still running | Keep polling or sync later. |
| `PIXELLE_PARTIAL_FAILURE` | Some images in an image set failed while others succeeded | Review successful images and retry failed slots if needed. |
| `ASSET_URL_MISSING` | Pixelle result has no usable URL | Retry the Pixelle task. |
| `TEMP_URL_PERSIST_FAILED` | Temporary provider URL could not be copied to controlled storage | Retry persistence before review. |
| `AI_REVIEW_FAILED` | Audit service failed | Route to human review with AI failure marker. |
| `IMAGE_REVIEW_REQUIRED` | Unapproved image is selected for downstream video use | Approve the image or run a repair task. |
| `STALE_ASSET_VERSION` | Human action targets old version | Reload latest asset. |

## Security And Privacy

- API keys remain in dy_auto model config and are only passed to Pixelle at task execution time.
- Redacted model traces must not include `api_key` or `api_secret`.
- Uploaded files must be validated by content type and size.
- Stored upload paths must not allow path traversal.
- Public URL sources should be normalized and rejected for local network SSRF-sensitive addresses unless local development mode explicitly allows them.
- Pixelle provider responses should be stored as summarized metadata, not raw secret-bearing payloads.
- Provider temporary URLs must be copied to controlled storage before an asset becomes reviewable.
- Base64 provider responses must be decoded and stored as files before returning to the frontend.
- Input image validation must use model capability limits, not only generic upload limits.
- App-served media URLs sent to Pixelle must use a configured reachable base URL. Do not assume `localhost` resolves correctly from Pixelle.
- Capability metadata must be treated as validation input, not a security boundary. The provider adapter still performs final provider-limit validation.

## Test Plan

Backend tests:

- `server/tests/test_image_creation_models.py`: migrations, indexes, uniqueness, latest review guards, and task/asset status transitions.
- `server/tests/test_image_creation_model_resolution.py`: capability-aware scene resolution, explicit model validation, and legacy `image_generation` compatibility.
- `server/tests/test_image_creation_api.py`: upload, create task, sync, list assets, review, and edit-again endpoints.
- `server/tests/test_image_creation_pixelle_client.py`: `submit_image_create` uses `/api/stages/images/create` and never calls `/api/stages/images/batch`.
- `server/tests/test_image_creation_mocked_e2e.py`: text-to-image -> Pixelle completed sync -> persisted asset -> AI review -> human approval -> downstream selector.
- Schema contains `image_editing` and maps it to `model_type = image`.
- Schema exposes image capability metadata and provider option schemas.
- Capability-aware model resolver selects a model that supports the requested capability.
- Existing image models without `capabilities` remain usable for `text_to_image`.
- Unsupported explicit model selection returns `IMAGE_CAPABILITY_UNSUPPORTED`.
- Text-to-image tasks resolve `image_generation`.
- Image-to-image tasks resolve `image_editing`.
- Multi-reference and image-set tasks resolve the correct scene and capability.
- Image-to-image without source returns validation error.
- Multi-reference modes reject too few or too many reference images.
- Unsupported size, output count, output format, and provider options return named errors.
- Invalid downstream destination returns `DOWNSTREAM_DESTINATION_INVALID`.
- High-cost requests return `IMAGE_COST_CONFIRMATION_REQUIRED` until confirmed.
- Requests over budget return `IMAGE_BUDGET_EXCEEDED`.
- Reusing the same idempotency key with the same request returns the existing task instead of submitting a duplicate Pixelle task.
- Reusing the same idempotency key with a different request returns `IMAGE_TASK_CONFLICT`.
- Upload endpoint rejects non-image files and oversized files.
- Upload endpoint returns `SOURCE_STORAGE_NOT_REACHABLE` when Pixelle cannot fetch the generated media URL.
- Pixelle create task success saves `ImageCreationTask`.
- Pixelle completed sync creates `ImageCreationAsset` records.
- Sync is idempotent for the same Pixelle task result.
- Concurrent or repeated sync calls do not duplicate assets or AI review records.
- Partial image set failures create assets for successful images and record per-image errors.
- Partial image set failures move the task to `completed_with_warnings`.
- Temporary provider URLs are persisted before assets become reviewable.
- Base64 provider responses are persisted and converted to dy_auto asset URLs.
- Completed assets trigger AI review.
- Pixelle failure stores named error and does not create reviewable assets.
- Human review prevents stale-version approval.
- Unapproved assets cannot be selected for downstream video use.
- Approved assets can be filtered by destination role for character anchors, scene references, style references, storyboard frames, and image-to-video.
- Approved image creation assets can be listed for image-to-video source selection.

Frontend tests:

- `web/src/__tests__/image-creation-page.test.js`: workbench modes, validation, cost confirmation, task status, result grid, and review actions.
- `web/src/__tests__/image-creation-api.test.js`: API client request/response mapping and named error display.
- `web/src/__tests__/image-creation-responsive.test.js`: desktop, tablet, and mobile layout behavior.
- `web/src/__tests__/image-creation-a11y.test.js`: keyboard navigation, focus, live status text, and image alt text.
- Page renders text-to-image, image-to-image, multi-reference, and image-set modes.
- Page renders multi-reference and image-set controls when the selected model supports them.
- Mode switching preserves sensible form state.
- Image-to-image source tabs support upload, asset, and URL.
- Multi-reference list supports uploading, selecting assets, and adding URLs in one ordered list.
- Submit is disabled without prompt or required source.
- Submit is disabled when the selected model does not support the requested capability.
- Capability limits are visible near reference count and output count controls.
- Destination role and cost estimate are visible before submission.
- High-cost confirmation blocks submission until the user confirms or lowers count/options.
- Success displays task status, model trace summary, images, and review state.
- Image set results show group order and partial failure messages.
- Failed task displays named repair action.
- Approve/reject actions call the image creation review API.
- "再次改图" creates an image-to-image task from the selected asset.
- UI copy for primary workflow controls is Chinese.
- Desktop, tablet, and mobile layouts preserve mode tabs, form validation, task state, and result actions without overlapping content.
- Keyboard navigation covers mode switching, source selection, reference ordering, result preview, approve/reject, and edit-again actions.
- Task progress and review status changes are exposed to assistive technology through live status text.
- Image tiles expose useful alt text and do not rely on color alone for review state.

Regression tests:

- Existing `AI Video Review` still works for `VideoProductionAsset`.
- Existing production image stage still calls `/api/stages/images/batch`.
- Existing Pixelle stage client tests still pass after adding `submit_image_create`.
- Existing Seedance standalone panel and video production monitor are not changed by the new route.
- Existing `image_generation` model config behavior remains compatible.
- Adding a second image model with different capabilities changes available controls without code changes.

## Autoplan Review Report

### CEO Review

Verdict: proceed, with one scope correction.

What was examined:

- Current Pixelle stage-gated design.
- Current control plane convergence design.
- Existing model center, Pixelle client, video production asset, and review models.

Findings:

| Severity | Finding | Decision |
|---|---|---|
| High | The original idea to write standalone image results directly into `VideoProductionAsset` conflicts with non-null `run_id` and `episode_id`. | Corrected by adding dedicated image creation task and asset tables. |
| High | A Seedream-only implementation would recreate hard-coded model behavior in the new model center. | Corrected by adding provider-neutral capabilities and provider option schema. |
| High | Multiple image models will exist, and picking by scene alone can silently select a model without the required capability. | Added capability-aware model resolution. |
| Medium | A standalone tool must still feed video production, or it becomes a disconnected toy. | Added approved-asset bridge into image-to-video selection. |
| Medium | The workbench needed a stronger business reason than "generate images." | Reframed it as the upstream visual asset control point for reducing wasted video-stage attempts. |
| Medium | Approved images need more than one downstream destination. | Added destination roles for character anchor, scene reference, style reference, storyboard frame, and image-to-video input. |
| Medium | Provider spend can grow silently through group generation and advanced options. | Added cost estimate, budget block, high-cost confirmation, and launch metrics. |
| Medium | Seedream image URLs may expire after 24 hours. | Added mandatory persistence before assets become reviewable. |
| Medium | Mask editing is valuable but would add a different UI and payload contract. | Deferred to keep first version shippable. |

Not in scope:

- Mask editor.
- Full media asset platform rewrite.
- Batch creative campaign tooling.

### Design Review

Verdict: design is viable if the page is a real workbench, not a thin form.

Findings:

| Severity | Finding | Decision |
|---|---|---|
| High | The page needs visible task state, model trace, errors, and review state to avoid hidden Pixelle work. | Included right-side task/result area and named repair actions. |
| High | Multi-reference and image-set generation need different mental models from simple image editing. | Added explicit `多图参考` and `组图生成` controls while still sharing one workbench. |
| Medium | Review actions should not use browser prompts. | Use inline textarea or modal controls in implementation. |
| Medium | Provider-specific options can clutter the core workflow. | Place them in schema-driven advanced controls. |
| Medium | English action labels already exist in review pages. | This feature must use Chinese labels for primary controls. |

### Engineering Review

Verdict: implement after adding the missing storage boundary.

Findings:

| Severity | Finding | Decision |
|---|---|---|
| High | Reusing `VideoProductionAsset` for standalone images would require dummy runs or nullable migrations across review records. | Add `ImageCreationTask`, `ImageCreationAsset`, and `ImageCreationReviewRecord`. |
| High | Pixelle task sync must be idempotent or repeated polling will duplicate images. | Use `pixelle_task_id`, `provider_task_id`, and `prompt_hash` as dedupe inputs. |
| High | Provider capabilities vary across Seedream, OpenAI, Flux, ComfyUI, and future models. | Add `capabilities`, `limits`, and `provider_options_schema` to model config and validate before execution. |
| High | Uploaded source URLs may not be reachable from Pixelle if dy_auto and Pixelle run in different hosts or containers. | Added `DY_AUTO_PUBLIC_BASE_URL`/staging-copy requirement and `SOURCE_STORAGE_NOT_REACHABLE`. |
| High | Repeated sync or frontend retry could duplicate Pixelle tasks, assets, or AI reviews. | Added idempotency keys, request hashes, transactional sync, asset upsert constraints, and once-per-version review triggers. |
| High | The first data model listed fields but not migration/index requirements. | Added required unique constraints and indexes for task, asset, review, and primary filters. |
| Medium | Runtime model config may leak secrets through trace fields. | Store only redacted model traces. |
| Medium | Public source URL support can create SSRF risk. | Validate and restrict URLs, with local-dev exceptions only where explicit. |
| Medium | Group generation may partially fail per image. | Persist successful assets and store per-image failure details. |
| Medium | Cost visibility needs an implementation source, not only UI text. | Added cost state machine, estimated/final usage fields, high-cost confirmation, and budget named errors. |
| Medium | Temporary uploads and copied provider outputs can accumulate indefinitely. | Added storage lifecycle, checksum/size metadata, and cleanup rules. |

### DX Review

Verdict: API shape is clear enough for dy_auto and Pixelle teams if errors stay named.

Findings:

| Severity | Finding | Decision |
|---|---|---|
| Medium | Pixelle endpoint naming must distinguish standalone image creation from frame batch generation. | Use `/api/stages/images/create` while keeping `/api/stages/images/batch` unchanged. |
| Medium | Runtime model selection must be predictable for integrators. | Added resolver rules for explicit model, default model, backward compatibility, and unsupported capability errors. |
| Medium | Seedream documentation uses `/api/v3/images/generations`, while this project previously required Plan V3 to avoid unwanted billing paths. | Documented that project implementation must use `/api/plan/v3/images/generations`. |
| Medium | Integrators need predictable repair actions, not raw provider errors. | Added named error contract. |
| Low | Model scene docs must show which mode uses which scene and capability. | Added scene and capability resolution table. |

## Final Implementation Guidance

Implementation should be split into these milestones:

1. Add `image_editing` scene and default seed support.
2. Add provider-neutral image capability metadata and provider option schema support in the model center.
3. Add capability-aware image model resolution.
4. Add image creation database models, migrations, indexes, idempotency constraints, and status transition helpers.
5. Add `submit_image_create` in the Pixelle stage client and Pixelle standalone image create endpoint support with a Seedream adapter.
6. Add dy_auto image creation APIs, upload storage reachability checks, idempotent task creation, and transactional sync.
7. Add temporary URL/Base64 persistence, checksum/size metadata, and cleanup rules before dy_auto marks assets reviewable.
8. Add AI review and human review with once-per-asset-version guards.
9. Add image creation frontend page with schema-driven capability controls, destination role, cost confirmation, and visible task state.
10. Add approved asset selection for image-to-video and other destination roles.
11. Run focused backend, frontend, regression, and mocked E2E tests.

Do not start by modifying the existing video production review page. The standalone workbench should land first, then the review center can be unified later if the duplicated UI becomes painful.

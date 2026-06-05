# Image Production Strategy Control Plane Design

## Summary

Upgrade the current image creation workbench from a parameter form into a production control plane for AI video image assets.

The system will let dy_auto manage reusable image production strategies, explain model selection, record reproducible parameter snapshots, enforce AI/human review gates, surface cost and capacity before execution, support fallback decisions, and compare strategies through A/B quality feedback.

This is the next stage after `2026-05-27-image-creation-workbench-design.md`. The existing workbench remains the execution surface; this design adds the strategy, trust, observability, and quality loop required for long-form automated video production.

## Confirmed Scope

- Image production strategy center.
- Model capability matrix and explainable automatic model selection.
- Parameter snapshots and reproducible production records.
- AI review rules and human review gates.
- Failure fallback and automatic repair suggestions.
- Cost, time, and capacity controls.
- Strategy A/B testing and quality feedback loop.

## Product Goal

The user should not have to understand every provider parameter before generating usable assets. They should choose a production intent, such as `角色锚定图`, `场景参考图`, `分镜首帧`, or `图生视频输入图`, and dy_auto should apply the right model, parameters, review policy, cost guard, and fallback behavior with visible reasoning.

The promise is:

```text
production intent + prompt/assets
  -> strategy selection
  -> model and parameter resolution
  -> visible cost/time estimate
  -> Pixelle execution
  -> persisted image asset
  -> AI review and optional human gate
  -> approved downstream asset
  -> quality/cost feedback updates strategy metrics
```

For one-sentence video production, the same control plane is used earlier in the chain:

```text
video intent
  -> required image asset plan
  -> strategy-bound image tasks for character anchors, scene references, style references, storyboard first frames, and image-to-video inputs
  -> reviewed image asset package
  -> video generation stages
```

This prevents the image workbench from becoming an isolated tool. It becomes the asset strategy layer for the full video production pipeline.

## What Already Exists

- `AIModel` stores provider, endpoint, credentials, `model_name`, `config_json`, and enabled state.
- `provider_options_schema` can describe provider-specific parameters.
- `ImageCreationPage.vue` already has model selection, common parameters, and dynamic provider option controls.
- `image_creation_service.py` validates mode capability, protected provider option keys, URL safety, idempotency, and asset persistence.
- Dedicated image task, asset, and review records exist for standalone image generation.
- Pixelle is already the execution layer for image creation and Seedream/Seedance integration.
- The video production control plane already has production concepts such as staged assets, review, cost, and status aggregation that can guide this design.

## Non-Goals

- No visual timeline editor.
- No mask painting editor in this phase.
- No direct frontend calls to image providers.
- No provider marketplace.
- No automatic Douyin publishing loop.
- No fully autonomous strategy mutation in the first release; metrics may recommend, but humans approve strategy changes.
- No opaque background bypass of review gates.

## Key Concepts

### Production Strategy

A strategy is a named, versioned configuration for a specific image production intent.

Examples:

- `角色锚定图`
- `场景参考图`
- `风格参考图`
- `分镜首帧`
- `图生视频输入图`
- `改图/重绘`
- `多图融合`
- `组图生成`

Strategy fields:

- `id`
- `name`
- `description`
- `destination_role`
- `supported_modes`
- `default_model_id`
- `fallback_model_ids`
- `common_parameters`
- `provider_options`
- `review_policy_id`
- `cost_policy`
- `capacity_policy`
- `ab_test_policy`
- `version`
- `status`
- `created_at`
- `updated_at`

### Capability Matrix

The capability matrix maps models to actual supported behavior:

- model type
- scene keys
- capability keys
- max source/reference images
- max output images
- supported output formats
- supported response formats
- provider option schema
- cost profile
- latency profile
- failure profile
- recommended strategy roles
- fallback compatibility

The source of truth remains `AIModel.config_json` and `provider_options_schema`. The capability matrix is a derived read model/resolver view unless implementation proves a separate indexed table is required. Do not dual-write capability metadata in both the model center and strategy center.

Required capability keys:

- `text_to_image`
- `image_to_image`
- `multi_image_fusion`
- `reference_image_batch`
- `character_anchor`
- `scene_reference`
- `style_reference`
- `storyboard_first_frame`
- `image_to_video_input`

### Selection Explanation

Every automatic model decision records:

- requested mode
- requested destination role
- strategy used
- candidate models considered
- rejected candidates and reasons
- selected model
- selected model reason
- fallback decision, if any

Selection preview is informational until task creation. If the frontend sends a `selection_preview_id`, the backend must validate the preview TTL, request hash, user scope, strategy version, and model config version. If any input changed, task creation must re-resolve and return a visible drift warning instead of trusting stale UI state.

### Production Snapshot

Every image task stores an immutable snapshot:

- user prompt and negative prompt
- selected strategy id/version
- resolved model id/name/provider/base URL without secrets
- common parameters
- provider options
- source asset id/version/url
- reference asset ids/versions/urls
- cost estimate
- selected review policy
- model selection explanation
- fallback state

For reproducibility, snapshots store asset ids, asset versions, checksums, and storage paths. URLs are display fields only and cannot be the sole reproduction record.

## Architecture

```text
ImageCreationPage
  -> Strategy selector
  -> Model/parameter panel
  -> Cost/time preview
  -> POST /api/image-production/selection-preview
  -> POST /api/image-creation/tasks

dy_auto API
  -> StrategyService
  -> CapabilityResolver
  -> ModelSelectionService
  -> CostEstimator
  -> ImageCreationService
  -> ReviewGateService
  -> FeedbackMetricsService

Pixelle-Video
  -> provider adapter
  -> image generation task
  -> result assets

dy_auto storage
  -> persisted outputs
  -> task snapshot
  -> review records
  -> strategy metrics
```

## Data Model

First choice is to add focused tables for strategy state, while reusing existing model center, review, cost, queue, and production asset concepts where possible.

Entity boundary:

- `AIModel.config_json` and `provider_options_schema` remain the capability source of truth.
- `image_production_strategies` stores human-managed production intent and default choices.
- `image_production_strategy_versions` stores immutable strategy snapshots.
- Review, cost, capacity, and A/B policies are versioned policies referenced by strategy versions, not silently mutable blobs on running tasks.
- `ImageCreationTask` stores the fully resolved immutable execution snapshot.
- A/B has first-class group/attempt records, not only a task-level group id.

### `image_production_strategies`

- `id`
- `name`
- `description`
- `destination_role`
- `supported_modes_json`
- `default_model_id`
- `fallback_model_ids_json`
- `common_parameters_json`
- `provider_options_json`
- `review_policy_version_id`
- `cost_policy_version_id`
- `capacity_policy_version_id`
- `ab_test_policy_version_id`
- `status`
- `version`
- `created_at`
- `updated_at`

### `image_production_strategy_versions`

Stores immutable versions for audit and historical task reproduction.

- `id`
- `strategy_id`
- `version`
- `snapshot_json`
- `created_at`

Constraints:

- unique `(strategy_id, version)`
- editing an active strategy creates a new version instead of mutating old task history
- task creation reads one strategy version inside the same transaction that writes the task snapshot
- update APIs use optimistic locking with `version`/`If-Match` semantics

### `image_production_metrics`

Aggregated strategy performance.

- `id`
- `strategy_id`
- `strategy_version`
- `model_id`
- `attempt_count`
- `success_count`
- `failure_count`
- `ai_pass_count`
- `human_pass_count`
- `repaint_count`
- `average_latency_seconds`
- `average_cost_amount`
- `created_at`
- `updated_at`

### `image_production_policy_versions`

Stores immutable policy definitions used by strategy versions.

- `id`
- `policy_type`: `review`, `cost`, `capacity`, or `ab_test`
- `name`
- `version`
- `snapshot_json`
- `status`
- `created_at`
- `updated_at`

Phase 1 can seed default policies and keep policy editing minimal. Later phases can split this into separate tables only if query patterns justify it.

### `image_production_ab_groups`

Stores an A/B comparison rooted in the same prompt/input package.

- `id`
- `source_request_hash`
- `prompt_snapshot_json`
- `cost_confirmation_json`
- `status`
- `winner_attempt_id`
- `created_at`
- `updated_at`

### `image_production_ab_attempts`

- `id`
- `group_id`
- `task_id`
- `strategy_id`
- `strategy_version`
- `model_id`
- `metrics_snapshot_json`
- `human_decision_json`
- `created_at`
- `updated_at`

### Existing Task Extensions

Extend `ImageCreationTask` with:

- `strategy_id`
- `strategy_version`
- `strategy_snapshot_json`
- `selection_explanation_json`
- `cost_estimate_json`
- `queue_job_id`
- `capacity_lease_id`
- `fallback_trace_json`
- `ab_test_group_id`

Avoid duplicating fields that already exist on `ImageCreationTask`, such as `estimated_cost_json`, `model_trace_json`, `request_json`, or `review_policy`. Prefer reusing them or clearly renaming old fields during migration.

## Naming Contract

Canonical `destination_role` values:

| Role | Meaning | Typical Mode |
|---|---|---|
| `character_anchor_image` | multi-angle character identity reference | `text_to_image`, `reference_image_batch` |
| `scene_reference_image` | reusable scene/location reference | `text_to_image`, `image_to_image` |
| `style_reference_image` | color, lighting, art direction reference | `text_to_image`, `multi_image_fusion` |
| `storyboard_first_frame` | first frame for a storyboard shot | `text_to_image`, `image_to_image` |
| `image_to_video_input` | approved image entering image-to-video | `image_to_image`, `multi_image_fusion` |
| `repaint_image` | repair/redraw an existing image | `image_to_image` |
| `fusion_image` | blend multiple inputs into one result | `multi_image_fusion` |
| `batch_story_images` | generate a group of related images | `reference_image_batch` |

Canonical task status values must be human-readable in the UI:

- `draft`
- `selection_previewed`
- `cost_confirmation_required`
- `queued`
- `running`
- `generated`
- `ai_review_pending`
- `manual_review_pending`
- `approved`
- `blocked`
- `fallback_confirmation_required`
- `failed`

## API Design

### Strategy Management

```text
GET    /api/image-production/strategies
POST   /api/image-production/strategies
GET    /api/image-production/strategies/{id}
PUT    /api/image-production/strategies/{id}
POST   /api/image-production/strategies/{id}/activate
POST   /api/image-production/strategies/{id}/archive
```

### Selection Preview

```text
POST /api/image-production/selection-preview
```

Request:

```json
{
  "mode": "image_to_image",
  "destination_role": "image_to_video_input",
  "strategy_id": "optional",
  "strategy_version": "optional",
  "model_id": "optional",
  "source_asset_ids": [],
  "reference_asset_ids": [],
  "common_parameters": {},
  "provider_options": {},
  "output_format": "url",
  "count": 1,
  "reference_count": 2
}
```

Response:

```json
{
  "ok": true,
  "selected_model": {},
  "strategy": {},
  "selection_explanation": {},
  "cost_estimate": {},
  "request_hash": "sha256:...",
  "expires_at": "2026-05-28T12:00:00Z",
  "warnings": []
}
```

The preview endpoint does not mutate production state. It may write a short-lived preview record for traceability, but task creation remains authoritative.

### Task Creation

The existing `POST /api/image-creation/tasks` remains compatible. New optional fields:

- `strategy_id`
- `strategy_version`
- `ab_test_strategy_ids`
- `selection_preview_id`
- `selection_preview_request_hash`

The backend resolves the final strategy/model/params and writes the snapshot before Pixelle submission.

Task creation transaction order:

1. Validate user scope and strategy permission.
2. Resolve strategy version and model capability from `AIModel.config_json`.
3. Validate preview hash/version if supplied.
4. Estimate cost and enforce budget confirmation.
5. Create task and immutable snapshot.
6. Reserve/queue work using existing production queue semantics when capacity policy is active.
7. Submit Pixelle work only after the task snapshot is durable.
8. Record audit events for every automatic decision and blocker.

### Image Asset To Video Bridge

Approved standalone image assets can be attached to video production only through an explicit bridge API:

```text
POST /api/image-production/assets/{asset_id}/promote-to-video-asset
```

Rules:

- asset must exist and belong to the current workspace/user scope
- required AI/human review gates must be passed
- strategy snapshot and review snapshot are copied into the video asset metadata
- downstream usage is recorded on the image asset
- blocked assets return `IMAGE_REVIEW_GATE_BLOCKED` with visible rescue actions

## Frontend Design

### Image Creation Page

The page should feel like a production console, not a parameter form.

Reuse the current dy_auto dark operational shell: slate background, compact tables, restrained borders, clear status badges, and work-focused density. Do not introduce a marketing hero, decorative cards, large empty illustrations, or a separate visual language for this feature.

First-screen information architecture:

1. Production intent summary: intent, selected strategy, strategy health, current version.
2. Trust panel: selection reason, cost/time estimate, capacity state, review gate, risk warnings.
3. Creation input: prompt, source image, reference images, output count, common parameters.
4. Advanced controls: model override and provider options collapsed by default.
5. Execution timeline: previewed, snapshotted, queued, generated, reviewed, approved/blocked.
6. Result and review cards.

First screen structure:

```text
+--------------------------------------------------------------------------------+
| Header: 图像生产控制台                         [成本预览] [创建任务/确认成本] |
+--------------------------------------------------------------------------------+
| Intent Strip                                                                    |
| [目标用途] [策略状态] [策略版本] [默认/手动模型] [审查门禁] [风险标签]         |
+---------------------------------------------+----------------------------------+
| Main Work Area                               | Trust Rail                       |
|                                             |                                  |
| Prompt and references                        | 1. 模型选择理由                  |
| Source image / reference images              | 2. 预计成本和耗时                |
| Output count and common params               | 3. 队列和产能                    |
| Collapsed advanced provider options          | 4. 审查规则                      |
|                                             | 5. 阻塞/回退提示                 |
+---------------------------------------------+----------------------------------+
| Execution Timeline: preview -> snapshot -> queue -> generate -> review -> gate  |
+--------------------------------------------------------------------------------+
| Results / Review Cards / Audit Drawer                                            |
+--------------------------------------------------------------------------------+
```

The three highest-priority facts above the fold are:

1. what asset the user is producing
2. why this model/strategy will be used
3. whether cost, capacity, or review gates can block the next video stage

Operational hierarchy:

1. Choose production intent.
2. Review the selected strategy and model explanation.
3. Add prompt/source/reference inputs.
4. Confirm cost/capacity/review warnings.
5. Submit.
6. Follow task timeline and review result.

Controls:

- Strategy dropdown grouped by destination role.
- A visible "auto model" state when no model is manually selected.
- Advanced model override panel.
- Dynamic provider options.
- Cost/time estimate panel.
- Review policy badge.
- A/B mode toggle for strategy comparison.
- Raw snapshot drawer hidden behind "audit details".

Raw JSON rule:

- default UI shows human-readable summaries, badges, diffs, and reasons
- provider JSON and snapshot JSON are only shown in an audit drawer
- protected keys and secrets are redacted before reaching the frontend

### Visual System

The visual direction is an operations console:

- background: `slate-950`
- panels: `slate-950/70` or `slate-900`
- borders: `slate-800`
- primary action: emerald for submit/approve actions
- informational state: sky
- warning state: amber
- blocked/error state: rose
- approved state: emerald
- neutral metadata: slate

Component rules:

- Use dense tables for strategy and asset lists.
- Use badges for status, risk, review gate, and strategy health.
- Use segmented controls for modes and intent groups.
- Use disclosure sections for advanced provider options and raw audit data.
- Use timeline rows for production steps, not floating decorative cards.
- Keep card radius at 8px or less to match the existing workbench feel.
- Keep technical data behind "审计详情"; do not expose raw JSON as the default reading path.

### Strategy Center Page

Add a dedicated page:

```text
/image-production/strategies
```

Views:

- strategy list
- strategy editor
- version history
- performance metrics
- fallback configuration
- review policy configuration

Strategy list columns:

- name
- destination role
- status: recommended, cautious, disabled, archived
- active version
- default model
- fallback model count
- recent success rate
- AI pass rate
- human pass rate
- average cost
- average latency
- sample count
- risk labels
- last updated
- actions

Required states:

- no strategies
- no active strategy for a role
- archived strategy selected
- version conflict while editing
- low sample size warning
- insufficient permission
- activation confirmation
- strategy used by historical tasks

Strategy center layout:

```text
+--------------------------------------------------------------------------------+
| Header: 图像策略中心                       [新建策略] [导入默认策略] [刷新指标] |
+--------------------------------------------------------------------------------+
| Filters: 目标用途 | 状态 | 模型服务商 | 风险 | 样本数 | 最近更新              |
+--------------------------------------------------------------------------------+
| Strategy Table                                                                  |
| 名称 | 用途 | 状态 | 版本 | 默认模型 | 回退 | 成功率 | AI通过 | 人工通过 | 成本 |
+--------------------------------------------------------------------------------+
| Right Drawer / Detail Panel                                                     |
| 基本信息 | 版本历史 | 参数摘要 | 审查策略 | 回退规则 | 指标 | 审计日志         |
+--------------------------------------------------------------------------------+
```

The list view is the default. The editor opens as a right-side drawer or dedicated detail page depending on available width. Editing an active strategy must show a version-change confirmation before save.

### Review Surface

Generated assets show:

- strategy name/version
- selected model and reason
- parameters snapshot
- AI review result
- manual review state
- repair suggestions
- "copy as new task"
- "save current params as strategy version"

Review state machine:

| State | Meaning | Main Actions |
|---|---|---|
| `generated` | asset exists but review has not started | run AI review, open snapshot |
| `ai_review_pending` | waiting for AI review | view queue state |
| `manual_review_pending` | AI passed or requires human decision | approve, reject, request repaint |
| `approved` | asset can enter downstream video stages | promote to video asset, view usage |
| `blocked` | asset failed required gate | view reason, copy as new task, repaint |
| `review_failed` | review service failed | retry review, send to manual review |
| `version_expired` | strategy/model version is superseded | copy as new task with latest strategy |

Review card layout:

```text
+---------------------------------------------+
| Asset preview                                |
| [用途] [策略 vN] [模型] [审查状态]           |
| 选择理由摘要                                 |
| AI 审查摘要 / 人工审查备注                  |
| [批准] [拒绝并重绘] [复制为新任务] [审计]    |
+---------------------------------------------+
```

Main action is state-dependent. Do not show "promote to video asset" until the asset is approved.

### A/B Comparison UX

A/B is not the default path. When enabled:

- lock the same prompt, source assets, reference assets, and output target
- show cost multiplication before execution
- create one A/B group with one attempt per strategy
- display results side by side
- show quality, AI/human pass state, cost, latency, and repaint count
- warn when sample size is too small
- support "no winner" and "manual winner requires approval"
- never mutate the winning strategy automatically

### Interaction State Matrix

| Feature | Loading | Empty | Error | Success | Partial |
|---|---|---|---|---|---|
| Strategy list | table skeleton rows | show default strategy seed action | show retry and diagnostics id | sortable table with metrics | show data with low-sample warning |
| Selection preview | trust rail skeleton | prompt user to choose intent | show error code and rescue action | selected model, rejected candidates, cost | show selected model with warning badges |
| Image task timeline | current step spinner | not shown before preview | failed step with retry/copy action | all steps with timestamps | generated asset but review pending |
| Review cards | review pending badge | no generated assets | review failed with retry/manual action | approved asset actions | some assets approved, some blocked |
| A/B comparison | waiting for attempts | no comparison started | failed side marked clearly | side-by-side results and winner action | one side failed, one side usable |
| Audit drawer | loading snapshot | no snapshot yet | redacted error details | readable snapshot sections | missing legacy fields explained |

### User Journey Storyboard

| Step | User Does | User Needs To Feel | Plan Specifies |
|---|---|---|---|
| 1 | Opens image creation | "I know what this screen is for." | header and intent strip name it as a production control surface |
| 2 | Chooses production intent | "The system understands the asset's role in the video." | canonical destination roles and strategy grouping |
| 3 | Enters prompt and references | "I can stay focused on the image, not provider internals." | prompt/reference area is primary; advanced params are collapsed |
| 4 | Reviews trust rail | "I understand why this model is selected and what it may cost." | model reason, rejected candidates, cost/time/capacity, review gate |
| 5 | Submits task | "Nothing hidden happened." | task snapshot and audit timeline are created before Pixelle submission |
| 6 | Reviews generated asset | "I can approve, repair, or block it." | review card state machine and state-specific actions |
| 7 | Sends asset downstream | "Only approved assets enter video production." | explicit promote-to-video bridge and gate check |

### Responsive And Accessibility Specs

Desktop, 1280px and above:

- two-column workbench with main area and trust rail
- strategy center table plus right-side detail drawer
- A/B comparison uses side-by-side results

Tablet, 768px to 1279px:

- trust rail moves below the intent strip and above prompt inputs
- strategy detail drawer becomes a full-width panel below the table
- A/B cards become two stacked panels with sticky comparison summary

Mobile, below 768px:

- single-column layout
- intent strip becomes compact stacked rows
- primary action remains visible at the top and repeated after trust rail
- tables become row cards with the same fields in fixed order
- advanced/audit drawers are closed by default

Accessibility:

- all interactive controls need visible focus states
- touch targets are at least 44px high
- status badges cannot rely on color alone; include text labels
- timeline steps use ordered semantics or accessible labels
- dialogs/drawers trap focus and restore focus on close
- contrast must meet WCAG AA for text and controls

### Design Decisions Considered And Deferred

| Decision | Status | Rationale |
|---|---|---|
| Full visual mockup generation | deferred | The current task is plan review; implementation can start from the screen diagrams and existing dark console style. |
| Mask painting or visual edit canvas | out of scope | This phase adds production control and review transparency, not a pixel editor. |
| Standalone analytics dashboard | deferred | Phase 1 only needs strategy table metrics and task timeline. |
| Automatic strategy mutation UI | out of scope | Strategy changes stay human-approved to protect style and cost. |

### Design Review Scorecard

| Pass | Before | After | Notes |
|---|---:|---:|---|
| Information architecture | 7/10 | 9/10 | Added first-screen structure and priority facts. |
| Interaction states | 6/10 | 9/10 | Added matrix for loading, empty, error, success, and partial states. |
| User journey | 6/10 | 9/10 | Added storyboard from intent to video bridge. |
| AI slop resistance | 7/10 | 9/10 | Explicitly rejects hero/card-heavy patterns and anchors to workbench console style. |
| Design system alignment | 7/10 | 8/10 | No project `DESIGN.md` found; calibrated against existing `ImageCreationPage.vue` dark slate UI. |
| Responsive and accessibility | 5/10 | 9/10 | Added viewport behavior, touch targets, focus, labels, and contrast requirements. |
| Unresolved design decisions | 2 deferred | 0 blocking | Mockups and analytics dashboard are deferred without blocking implementation. |

Overall design score: 7/10 -> 9/10.


## Error And Rescue Map

| Error Code | Trigger | Rescue | User Sees |
|---|---|---|---|
| `IMAGE_STRATEGY_NOT_FOUND` | strategy id missing | stop task creation | "策略不存在，请重新选择" |
| `IMAGE_STRATEGY_ARCHIVED` | archived strategy selected | stop task creation | "策略已归档，请选择新策略" |
| `IMAGE_STRATEGY_MODE_UNSUPPORTED` | strategy does not support mode | stop task creation | "该策略不支持当前生成模式" |
| `IMAGE_MODEL_SELECTION_EMPTY` | no candidate model | stop task creation | "没有可用模型支持该场景" |
| `IMAGE_MODEL_SELECTION_AMBIGUOUS` | multiple equivalent candidates and no strategy default | choose first by sort order, record warning | "已按优先级自动选择模型" |
| `IMAGE_PROVIDER_OPTIONS_INVALID` | schema mismatch | stop task creation | existing provider options error |
| `IMAGE_COST_CONFIRMATION_REQUIRED` | estimate exceeds threshold | require confirmation | "预计成本较高，请确认" |
| `IMAGE_CAPACITY_EXCEEDED` | queue or concurrency limit hit | offer queued/try later | "当前产能不足，可排队或稍后重试" |
| `IMAGE_REVIEW_GATE_BLOCKED` | AI/human review not passed | block downstream bridge | "未通过审查，不能进入视频阶段" |
| `IMAGE_FALLBACK_REQUIRES_CONFIRMATION` | fallback model available but quality/cost risk exists | ask user to confirm | "主模型失败，是否使用回退模型" |
| `IMAGE_AB_TEST_COST_CONFIRMATION_REQUIRED` | A/B would multiply cost | require confirmation | "多策略对比会增加成本" |

Developer-facing error contract:

| Error Code | HTTP | Log Event | Debug Fields |
|---|---:|---|---|
| `IMAGE_STRATEGY_NOT_FOUND` | 404 | `image_strategy_not_found` | `strategy_id`, `user_scope`, `trace_id` |
| `IMAGE_STRATEGY_ARCHIVED` | 409 | `image_strategy_archived` | `strategy_id`, `strategy_version`, `trace_id` |
| `IMAGE_STRATEGY_MODE_UNSUPPORTED` | 422 | `image_strategy_mode_unsupported` | `strategy_id`, `mode`, `supported_modes`, `trace_id` |
| `IMAGE_MODEL_SELECTION_EMPTY` | 422 | `image_model_selection_empty` | `destination_role`, `capability_keys`, `trace_id` |
| `IMAGE_MODEL_SELECTION_AMBIGUOUS` | 200 | `image_model_selection_ambiguous` | `candidate_model_ids`, `sort_key`, `trace_id` |
| `IMAGE_COST_CONFIRMATION_REQUIRED` | 409 | `image_cost_confirmation_required` | `estimate`, `threshold`, `trace_id` |
| `IMAGE_CAPACITY_EXCEEDED` | 429 | `image_capacity_exceeded` | `queue_depth`, `limit`, `trace_id` |
| `IMAGE_REVIEW_GATE_BLOCKED` | 409 | `image_review_gate_blocked` | `asset_id`, `review_state`, `trace_id` |
| `IMAGE_FALLBACK_REQUIRES_CONFIRMATION` | 409 | `image_fallback_requires_confirmation` | `primary_model_id`, `fallback_model_id`, `risk_labels`, `trace_id` |
| `IMAGE_AB_TEST_COST_CONFIRMATION_REQUIRED` | 409 | `image_ab_test_cost_confirmation_required` | `strategy_count`, `estimate`, `trace_id` |

All debug payloads must redact provider credentials and raw provider bodies containing secrets.

## Failure Modes Registry

| Failure Mode | Impact | Mitigation |
|---|---|---|
| Strategy drift after tasks are created | historical tasks unreproducible | immutable strategy snapshot per task |
| Provider schema changes | frontend renders stale options | version provider schema and validate server-side |
| Fallback model changes style | series inconsistency | fallback requires strategy compatibility flag and review gate |
| A/B tests multiply spend | unexpected cost | explicit estimate and confirmation |
| Review gate blocks too many assets | production slows | policy thresholds configurable by strategy |
| Auto model selection feels like a black box | user mistrust | selection explanation shown in task details |
| Metrics become misleading on low sample size | bad strategy recommendations | show sample count and confidence |
| Preview and create drift | UI approval no longer matches backend execution | validate preview hash and re-resolve with visible warning |
| Capacity JSON does not prevent oversubscription | multiple tasks overrun provider limits | use queue/lease semantics instead of task-local JSON only |
| Unreviewed image enters video stage | bad assets contaminate long-form video | explicit promote API and review gate check |
| Capability matrix duplicates model center | provider behavior diverges between pages | derive matrix from `AIModel.config_json` |

## Phased Rollout

### Phase 1: Strategy Center MVP

- Add strategy tables and migrations.
- Add strategy CRUD API.
- Add immutable strategy versions with optimistic locking.
- Seed default strategies for `character_anchor_image`, `storyboard_first_frame`, and `image_to_video_input`.
- Add strategy selector to image creation page.
- Add minimal selection preview with selected model reason and cost estimate.
- Persist strategy snapshot in image task.
- Add task details showing strategy/model/parameter snapshot.
- Add task audit timeline showing preview, snapshot, queue, generation, review, and block/approval state.
- Preserve current parameter panel and direct model override.

Exit criteria:

- A user can create a strategy, use it for a task, see why the model was selected, see the estimated cost before submit, and later inspect the exact snapshot/audit trail that produced an image.

### Phase 2: Explainable Selection And Fallback Advice

- Add capability resolver derived from `AIModel.config_json`.
- Add selection preview API.
- Add selection explanation.
- Add fallback model configuration.
- Add named fallback errors and repair suggestions.
- Add preview/create drift detection.

Exit criteria:

- A task can be created without manual model selection, and the UI explains why the model was selected or why no model was available.

### Phase 3: Review Gates, Cost, And Capacity

- Add review policy version references per strategy.
- Add cost estimate preview.
- Add high-cost confirmation.
- Add capacity policy using existing queue/lease semantics and queue status display.
- Block downstream image-to-video use for assets that have not passed required gates.
- Add explicit image asset to video asset bridge.

Exit criteria:

- A user sees cost/time before submit and blocked assets cannot silently enter video generation.

### Phase 4: A/B Testing And Feedback Loop

- Add multi-strategy A/B task groups.
- Add A/B attempts with shared prompt/input hash.
- Add comparison view.
- Track pass/fail/repaint/cost/latency metrics.
- Add recommended/caution/disabled strategy labels.
- Keep human approval for strategy changes.

Exit criteria:

- A user can compare strategies on the same prompt and see which strategy produced better reviewed results and lower effective cost.

## Default Data And Migration

Migration rules:

- Add new columns as nullable first.
- Backfill only safe defaults; old tasks remain readable without a strategy.
- Create strategy/version/policy tables before adding task references.
- Seed default policies before seed strategies.
- Add unique `(strategy_id, version)` before exposing updates.
- Use a follow-up migration to tighten non-null constraints only after old rows are verified.

Default seed strategies:

| Strategy | Destination Role | Default Mode | Notes |
|---|---|---|---|
| `默认角色锚定图` | `character_anchor_image` | `text_to_image` | supports multi-angle identity references |
| `默认分镜首帧` | `storyboard_first_frame` | `text_to_image` | optimized for video shot planning |
| `默认图生视频输入图` | `image_to_video_input` | `image_to_image` | requires review gate before video stage |

Rollback posture:

- strategy references on tasks are nullable
- strategy snapshots remain JSON and do not block old task rendering
- seeded strategies can be archived instead of deleted

## Provider Integration Contract

To add a new image provider:

1. Add or update an `AIModel` entry with provider, endpoint, model id, enabled state, and redacted credential reference.
2. Define `config_json.capabilities`, `config_json.scene_keys`, limits, response formats, and `provider_options_schema`.
3. Add provider adapter support in the image execution layer if Pixelle does not already expose it.
4. Add a mock provider fixture covering success, validation failure, provider failure, and slow response.
5. Add cost/latency profile data used by selection preview.
6. Add provider-specific options to the frontend only through schema rendering.
7. Verify that protected keys cannot be submitted through `provider_options`.
8. Add tests for model resolution, task creation, snapshot redaction, and asset persistence.

Provider-specific parameters must never become hardcoded Vue form fields unless they are also represented in `provider_options_schema`.

## Engineering Review Lockdown

### Scope Challenge Result

The core objective is not to build a second image production stack. The minimum complete implementation is a strategy and trust layer around the existing image workbench.

Existing code to reuse:

- `ImageCreationTask`, `ImageCreationAsset`, and `ImageCreationReviewRecord` already model task, asset, and review state.
- `create_image_task` already validates mode, prompt, provider limits, protected provider option keys, idempotency, cost confirmation, Pixelle submission, and task snapshots.
- `resolve_image_model_for_capability` already resolves enabled image models from `AIModel.config_json`.
- `ProductionJob` already has idempotency, queue state, retry state, and leases.
- `ProductionCostEvent` already has the cost event ledger for production plans.
- `video_production_state.assert_can_start_videos` already enforces approved video production image assets.

Scope reductions applied:

- Do not replace `POST /api/image-creation/tasks`.
- Do not create a second provider execution path.
- Do not create an independent writable capability matrix in Phase 1.
- Do not implement A/B, hard capacity leases, or full policy editors in Phase 1.
- Do not let the strategy center mutate `AIModel` capability config.

Phase 1 should touch a controlled file set:

- `server/app/db_models.py`
- one Alembic migration under `server/alembic/versions`
- `server/app/routers/image_production.py`
- `server/app/services/image_production_strategy_service.py`
- `server/app/services/image_selection_preview_service.py`
- `server/app/services/image_asset_bridge_service.py`
- `server/app/services/image_creation_service.py` only for optional strategy snapshot fields and request handling
- `web/src/api/imageProduction.js`
- `web/src/views/ImageCreationPage.vue`
- one strategy center route/view after backend contracts are stable

If implementation requires more services in Phase 1, stop and re-justify the split.

### Service Boundary

```text
Frontend
  ImageCreationPage
    -> imageProductionApi.selectionPreview()
    -> imageCreationApi.createImageTask()
    -> imageProductionApi.promoteAsset()

Backend
  image_production router
    -> ImageProductionStrategyService
    -> ImageSelectionPreviewService
    -> ImageAssetBridgeService

  image_creation router
    -> ImageCreationService
       -> existing model resolver
       -> existing provider option validation
       -> existing Pixelle submit path

Existing shared services
  runtime_model_config.py
  image_creation_service.py
  production_queue_service.py
  production_cost_service.py
  video_production_state.py
```

Ownership rules:

- Strategy service owns CRUD, immutable versions, default seeds, and activation/archive audit.
- Preview service owns read-only model/strategy resolution and request hash calculation.
- Image creation service owns authoritative task creation and Pixelle submission.
- Bridge service owns reviewed image asset promotion into video production assets.
- Runtime model config remains the source for model capabilities.

### Task Creation Transaction Contract

```text
request
  -> auth and scope check
  -> validate mode, prompt, source, references
  -> resolve strategy version if supplied
  -> resolve model from AIModel.config_json
  -> validate provider limits and provider_options_schema
  -> validate preview hash if supplied
  -> estimate cost and require confirmation if needed
  -> insert ImageCreationTask with immutable snapshots
  -> commit task before external Pixelle call
  -> submit Pixelle
  -> update provider task ids and status
```

Important rule: database state must be durable before the external Pixelle submission. If Pixelle submission fails, the task remains visible with `PIXELLE_IMAGE_SUBMIT_FAILED` and a retry/rescue action.

### Idempotency And Concurrency

- Existing `ImageCreationTask.idempotency_key` remains authoritative for task creation.
- Strategy update requires optimistic locking by active `version`; stale saves return `IMAGE_STRATEGY_VERSION_CONFLICT`.
- Strategy activation/archive uses a transaction and writes an audit event.
- `selection_preview_id` is never trusted without matching `request_hash`, `strategy_version`, `model_id`, and expiry.
- Concurrent preview calls are safe because they do not mutate production state.
- Concurrent task creation with the same idempotency key returns the original task only when `request_hash` matches.
- A/B group creation in Phase 4 must use one idempotency key per group and one derived idempotency key per attempt.

### Migration Order

```text
001 add strategy, strategy_version, policy_version tables
002 seed default policy versions and default strategies
003 add nullable strategy/snapshot/preview fields to image_creation_tasks
004 add optional image asset downstream usage indexes if query pressure requires them
005 add A/B group and attempt tables in Phase 4 only
```

Migration requirements:

- Every migration must be idempotent against partially upgraded local databases.
- Add indexes with names and rollback behavior.
- Do not tighten nullable columns until old image tasks have been verified.
- Add a migration graph test so the new revision depends on `f6a7b8c9d0e1_image_creation_workbench.py` or the current head after it.

### Auth And Scope Contract

- `image_production` routes use `verify_admin_token` for reads and `require_role("admin")` for strategy mutations.
- `image_creation` task creation/read/sync/assets/review/edit should be upgraded to require `verify_admin_token` as part of this work or explicitly scheduled as a prerequisite.
- Non-admin users can only see their own scoped tasks/assets where the existing role model supports it.
- Bridge promotion requires an approved image asset and current user access to the source asset and target video run/plan.
- All snapshot payloads redact credentials before storage and before response serialization.

### Failure Modes From Eng Review

| Code Path | Real Failure | Covered By Plan | Required Handling |
|---|---|---|---|
| Strategy update | stale editor overwrites active version | yes | optimistic lock and conflict response |
| Selection preview | model config changes before create | yes | preview hash/version drift response |
| Task creation | Pixelle submit fails after task insert | partial, existing behavior | keep failed visible task and retry action |
| Strategy seed | seed runs twice | yes | upsert by slug and version |
| Bridge promotion | unapproved image enters video stage | yes | server-side gate and `IMAGE_REVIEW_GATE_BLOCKED` |
| Cost estimate | estimate differs from actual provider cost | partial | record estimate source and later actual cost event |
| Queue capacity | local JSON limit overbooks provider | yes | reuse queue/lease semantics, no task-local-only capacity |
| Snapshot response | secrets leak through model trace | yes | server-side redaction tests |
| A/B attempt | retry double-counts metrics | Phase 4 | attempt ledger and idempotency |

No critical silent-failure gap remains after these constraints.

### Test Coverage Diagram

```text
CODE PATHS                                             USER FLOWS
[+] image_production_strategy_service.py               [+] Strategy center
  ├── [GAP] create/update/archive/activate               ├── [GAP] list, create, edit, activate, archive
  ├── [GAP] immutable version bump                       ├── [GAP] stale editor conflict
  └── [GAP] default seed idempotency                     └── [GAP] archived strategy cannot be selected

[+] image_selection_preview_service.py                 [+] Image creation trust rail
  ├── [GAP] derive candidates from AIModel config        ├── [GAP] model selected with explanation
  ├── [GAP] rejected candidate reasons                   ├── [GAP] no compatible model shows rescue
  ├── [GAP] request hash and expiry                      └── [GAP] stale preview blocks or re-resolves
  └── [GAP] protected provider options rejected

[+] image_creation_service.py extensions               [+] Existing task creation remains compatible
  ├── [★★ TESTED] current image task happy path          ├── [★★ TESTED] Pixelle mocked E2E
  ├── [GAP] strategy snapshot persisted                  ├── [GAP] no strategy path still works
  ├── [GAP] idempotency with strategy version            └── [GAP] Pixelle submit failure leaves visible task
  └── [GAP] snapshot secret redaction

[+] image_asset_bridge_service.py                      [+] Image to video gate
  ├── [GAP] approved asset promoted                      ├── [GAP] approved image can enter video stage
  ├── [GAP] pending/rejected asset blocked               └── [GAP] blocked asset shows review rescue
  └── [GAP] downstream usage recorded

[+] Strategy/A-B Phase 4                               [+] A/B comparison
  ├── [DEFERRED] group and attempts                      ├── [DEFERRED] cost multiplication confirmation
  └── [DEFERRED] winner approval                         └── [DEFERRED] no-winner/low-sample state

COVERAGE NOW: existing image creation basics only.
COVERAGE REQUIRED BEFORE IMPLEMENTATION COMPLETE: every GAP above has unit or integration tests.
```

### Required Test Files

Backend:

- `server/tests/test_image_production_strategy_service.py`
  - strategy CRUD, status transitions, version bump, stale version conflict, archive behavior, seed idempotency
- `server/tests/test_image_selection_preview_service.py`
  - candidate derivation from `AIModel.config_json`, rejected reasons, cost estimate, preview hash, expiry, drift
- `server/tests/test_image_creation_strategy_snapshot.py`
  - task creation with strategy, no-strategy compatibility, idempotency conflict, redacted snapshot
- `server/tests/test_image_asset_bridge.py`
  - approved promotion, blocked promotion, downstream usage record, target run/plan scope validation
- `server/tests/test_image_production_migration.py`
  - migration revision ordering, nullable old-task compatibility, seeded strategy rows
- extend `server/tests/test_image_creation_mocked_e2e.py`
  - one strategy -> task -> mocked Pixelle asset -> review -> bridge eligibility

Frontend:

- extend `web/src/__tests__/image-creation-page.test.js`
  - strategy selector, trust rail, selection preview, stale preview warning, cost confirmation, no-strategy compatibility
- add `web/src/__tests__/image-production-strategy-page.test.js`
  - strategy table states, filters, edit drawer, version conflict, archive confirmation
- extend `web/src/__tests__/image-creation-a11y.test.js`
  - focus order, drawer focus trap, status text labels, keyboard actions

### Performance And Scaling Constraints

- Strategy list uses pagination and server-side filters. Do not ship an unbounded `GET /strategies` result once metrics are joined.
- Strategy metrics are aggregated asynchronously or incrementally from task/review events; do not compute pass rates by scanning all assets per page load.
- Selection preview must avoid N+1 model config reads; load enabled image models once per request.
- Asset list keeps existing `page_size <= 100`.
- Bridge promotion should write one video asset and one usage record in a transaction; it must not recompute a full video production run.
- A/B metrics in Phase 4 need indexed group/attempt tables before UI comparison is enabled.

### Inline Diagram Comments To Add During Implementation

Add short ASCII comments only where the flow is non-obvious:

- `image_production_strategy_service.py`: strategy edit -> new immutable version -> activate
- `image_selection_preview_service.py`: preview hash inputs and drift validation
- `image_asset_bridge_service.py`: review gate -> video asset creation -> downstream usage
- `image_creation_service.py`: authoritative task creation order when strategy fields are present

### Worktree Parallelization Strategy

If implemented with parallel agents, use disjoint ownership:

- Backend schema/service worker: db models, migration, strategy service, preview service
- Backend bridge/test worker: image asset bridge, review gate integration, backend tests
- Frontend worker: image creation trust rail, strategy center view, frontend tests
- QA worker: mocked E2E, migration tests, regression pass

No worker should rewrite the existing Pixelle submission path without coordinating through `image_creation_service.py`.

## Observability

Metrics:

- strategy usage count
- model selection candidate count
- model selection failure rate
- average cost estimate vs actual cost
- queue wait time
- task latency
- persistence failure rate
- AI review pass rate
- human override rate
- fallback suggestion count
- fallback accepted count
- A/B test winner rate

Dashboards:

- image production health
- model capability coverage
- strategy quality scorecard
- cost and capacity panel
- review gate backlog

## Security

- Continue blocking unsafe source/reference URLs.
- Continue redacting model API keys and secrets from snapshots.
- Do not expose raw provider request bodies if they contain credentials.
- Strategy CRUD, activation, archive, policy editing, and A/B winner adoption require admin permission.
- Task and asset reads respect the current workspace/user scope.
- Strategy activation/archive actions are audit logged.
- A/B tasks must show cost multiplication before execution.
- Selection explanations may include candidate model ids, but never provider credentials, raw API keys, or unredacted request bodies.

## Testing Strategy

Backend tests:

- strategy CRUD and versioning
- strategy snapshot immutability
- model selection explanation
- unsupported mode/model errors
- cost confirmation
- fallback suggestion
- review gate blocking
- A/B task group creation
- migration compatibility for old tasks without strategy ids
- preview/create drift detection
- strategy version optimistic locking
- permission checks for strategy editing and asset reads
- snapshot redaction of secrets
- image asset to video asset bridge gate checks

Frontend tests:

- strategy selector loads and applies defaults
- auto model state does not force a model id
- strategy snapshot visible in task details
- cost confirmation flow
- review gate blocked state
- A/B comparison view
- first-screen production console hierarchy
- audit drawer hides raw JSON by default
- review card state-specific actions

Integration tests:

- one strategy -> image task -> persisted asset -> review -> downstream eligibility
- failed model -> fallback suggestion -> confirmed retry -> review
- A/B strategies -> two tasks -> comparison metrics

Local verification commands:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_creation_mocked_e2e.py tests/test_image_creation_tasks.py tests/test_ai_config.py

cd D:\devWorkspace\jsProjects\dy_auto\web
npm run test -- --run src/__tests__/image-creation-page.test.js
npm run build
```

The full implementation plan should expand this into a red/green TDD checklist before code changes begin.

## Autoplan Review Report

Autoplan ran four review lenses against this design and the current codebase direction:

| Lens | Score | Main Finding | Plan Response |
|---|---:|---|---|
| CEO | 8/10 | The plan is strategically right, but must become a video asset control tower instead of an advanced image form. | Added video-intent-to-image-asset-plan flow, audit timeline, and Phase 1 trust spine. |
| Design | 7/10 | UI spec was still too form-like and underspecified for operations. | Added first-screen IA, strategy table columns, review state machine, raw JSON rule, and A/B UX. |
| Engineering | 6/10 | Entity boundaries, capability ownership, preview/create consistency, queue/cost semantics, A/B entities, and auth were too loose. | Added entity boundary, immutable versions, derived capability matrix, transaction contract, bridge API, policy versions, and A/B tables. |
| DX | 6/10 | Implementers lacked naming contracts, seed data, migration notes, provider guide, concrete tests, and debug fields. | Added naming contract, default seeds, migration rules, provider integration contract, developer error contract, and local commands. |

Final gate recommendation:

- Approve the expanded direction.
- Do not implement the whole scope in one pass.
- Implement Phase 1 as a trusted vertical slice: strategy CRUD, immutable versions, default seeds, minimal preview/explanation/cost, task snapshot, audit timeline.
- Keep A/B, complex capacity, and automatic fallback outside the default path until review labels and cost accounting are stable.

Taste decisions surfaced:

| Decision | Recommendation | Rationale |
|---|---|---|
| Scope shape | Keep all 7 expansion areas in the blueprint, but ship in phases | They are valid for long-form video production, but coupling all of them into MVP would delay usable trust features. |
| Capability matrix | Derive from model center first | Prevents a second source of truth and matches current `AIModel.config_json` direction. |
| A/B testing | Phase 4 only, with first-class group/attempt records | Avoids noisy metrics and accidental cost multiplication before review data is reliable. |
| Raw JSON visibility | Hide by default, expose in audit drawer | Operators need readable reasons first; developers still need traceability. |

## Plan Eng Review Report

Engineering review result: CLEAR after plan fixes.

Findings resolved in the plan:

- `[P1] (confidence: 9/10)` avoid a parallel image production stack by keeping `POST /api/image-creation/tasks` authoritative.
- `[P1] (confidence: 9/10)` avoid a second capability source of truth by deriving selection from `AIModel.config_json`.
- `[P1] (confidence: 8/10)` make strategy versions immutable and enforce optimistic locking.
- `[P1] (confidence: 8/10)` require backend preview/create drift validation.
- `[P1] (confidence: 8/10)` define explicit reviewed image asset -> video asset bridge.
- `[P2] (confidence: 8/10)` reuse queue leases and cost events instead of task-local capacity/cost JSON only.
- `[P2] (confidence: 8/10)` tighten auth and scope expectations for image production and image creation routes.
- `[P2] (confidence: 8/10)` add concrete test files and coverage diagram before implementation begins.

Completion summary:

- Step 0 Scope Challenge: scope reduced to strategy/trust layer around existing image creation.
- Architecture Review: 8 issues found, all resolved in the plan.
- Code Quality Review: 4 module-boundary issues found, resolved by service ownership rules.
- Test Review: coverage diagram produced, 17 required test gaps identified and added.
- Performance Review: 6 constraints added.
- Critical gaps: 0 after plan updates.
- Unresolved decisions: 0.

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | Intake | Create a new strategy-control-plane spec instead of editing the existing workbench spec | Two-way, medium magnitude | Preserve context boundaries | Existing 2026-05-27 spec documents the base workbench; the new scope is a larger next-stage system | Overwrite the previous spec |
| 2 | Scope | Split delivery into four phases | Two-way, high magnitude | Focus as subtraction | The accepted scope is L/XL; phase gates keep delivery testable and reduce coupling | One large implementation PR |
| 3 | Product | Keep strategy changes human-approved in Phase 4 | One-way-ish, medium magnitude | Trust before autonomy | Automatic strategy mutation can silently degrade style consistency or cost | Fully autonomous strategy optimization |
| 4 | CEO Review | Add video intent -> image asset plan to the product goal | Two-way, high magnitude | User outcome first | The feature must serve one-sentence video production, not only standalone image work | Keep the spec limited to image workbench configuration |
| 5 | Design Review | Redesign the first screen as a production console | Two-way, medium magnitude | Make system state visible | Users need intent, strategy health, cost, capacity, review gates, and timeline before trusting automation | Keep a linear parameter form as the primary IA |
| 6 | Engineering Review | Make model capability matrix derived from `AIModel.config_json` | Mechanical, medium magnitude | Single source of truth | The project already stores capabilities and provider schemas on AI model config; duplicating would drift | Add a separate writable capability matrix immediately |
| 7 | Engineering Review | Add immutable strategy versions and preview/create drift validation | Mechanical, high magnitude | Reproducibility before automation | Long-form production requires auditable snapshots and exact execution records | Trust frontend preview state without backend revalidation |
| 8 | Engineering Review | Add explicit image asset to video asset bridge | Mechanical, high magnitude | No hidden bypasses | Review gates must block downstream video usage through a single audited path | Let downstream video stages pull image URLs directly |
| 9 | DX Review | Add naming, seed, migration, provider, and test contracts before implementation | Mechanical, medium magnitude | Remove implementation guesswork | The previous plan described concepts but left too many choices implicit | Let each implementer infer enums, seeds, and test entrypoints |
| 10 | Plan Eng Review | Keep existing image creation task endpoint authoritative | Mechanical, high magnitude | Incremental over revolutionary | Reusing `ImageCreationTask` and Pixelle submit path avoids a second stack and lowers regression risk | New `/api/image-production/tasks` execution path |
| 11 | Plan Eng Review | Phase 1 limited to strategy/trust vertical slice | Two-way, high magnitude | Right-sized diff | A/B, hard capacity leases, and full policy editors are useful but not required to prove transparent strategy execution | Ship all confirmed scope in one implementation pass |
| 12 | Plan Eng Review | Require auth/scope upgrade on image creation paths | Mechanical, high magnitude | Secure by boundary | Current image production routes must not expose strategy, task, asset, or review operations without the same admin/session boundary as other production APIs | Leave image creation routes unauthenticated while adding strategy controls |
| 13 | Plan Eng Review | Add explicit backend test files before implementation starts | Mechanical, medium magnitude | Tests as contract | The plan now maps every strategy/preview/snapshot/bridge path to a named test file | Rely only on existing mocked image creation tests |

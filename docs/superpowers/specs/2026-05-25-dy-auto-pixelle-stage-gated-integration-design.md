<!-- /autoplan restore point: C:\Users\HNXE\.gstack\projects\dy_auto\feature-video-review-fixes-autoplan-restore-20260525-014940.md -->

# dy_auto + Pixelle-Video Stage-Gated Integration Design

## Summary

dy_auto will become the orchestration layer for AI video production, while Pixelle-Video remains the execution layer. dy_auto owns content planning, series style lock, automatic storyboard generation, model configuration, runtime configuration delivery, production state, asset storage, review gates, and the video library. Pixelle-Video owns media execution: prompt/template execution, image generation, image-to-video rendering, frame processing, and final composition.

The first version uses API orchestration. dy_auto calls newly added Pixelle-Video stage APIs instead of sending one opaque full-pipeline job. The production flow pauses at batch review gates:

```text
storyboard
  -> batch image generation
  -> image AI review
  -> human review for exceptions
  -> batch image-to-video generation
  -> video segment AI review
  -> human review for exceptions
  -> final composition
  -> dy_auto video library
```

AI review is the default gate. Human review is required only when AI review fails, returns low confidence, or the audit service errors.

## Goals

- Let dy_auto orchestrate the full video production lifecycle without hidden Pixelle-Video state transitions.
- Let Pixelle-Video execute stage work through explicit APIs for image generation, video segment generation, and final composition.
- Use dy_auto as the only model configuration authority and deliver runtime model config to Pixelle-Video.
- Store generated images, video segments, final videos, review results, and model traces in dy_auto.
- Add an AI video review center in dy_auto for exception handling and manual approval.
- Support single-item regeneration for failed images or video segments without rerunning the whole episode.
- Preserve Pixelle-Video's strengths: prompt templates, ComfyUI/RunningHub workflows, Seedance/Kling/Wan renderers, TTS, frame composition, and final video assembly.

## Non-Goals

- No generic review center for non-video content in the first version.
- No Douyin publishing loop.
- No visual timeline editor.
- No full rewrite of the Pixelle-Video UI.
- No multi-user reviewer permission workflow in the first version.
- No advanced model fallback chains, cost budgets, or queue scheduling policy in the first version.
- No direct Python import embedding of Pixelle-Video inside dy_auto.
- No shared database between dy_auto and Pixelle-Video.

## Current State

dy_auto currently contains:

- AI model configuration center work around `AIModel`, scene schema, and registry.
- Series style lock and automatic storyboard work.
- A pipeline router that can call Pixelle-Video and persist final run/video records.
- Pixelle proxy/config bridge code.
- AI audit routes and generated video storage.
- Existing frontend areas for video studio, series details, pipeline monitoring, and model configuration.

Pixelle-Video currently contains:

- A FastAPI service with routes such as `/api/video/generate/async`, `/api/image/generate`, `/api/content/*`, `/api/frame/render`, `/api/tasks/{id}`, and `/api/admin/reload`.
- `PixelleVideoCore` and `FrameProcessor` for TTS, media generation, frame composition, and segment creation.
- `AIModelRegistry` reading model config from `config.yaml`.
- Render services for Seedance, Kling, Wan, ComfyUI, and RunningHub style workflows.
- Prompt templates, frame templates, BGM, history, and filesystem persistence.

The gap is that Pixelle-Video still tends to execute a whole video production pipeline internally, while dy_auto needs stage-level control so it can show intermediate assets, audit them, request human decisions, and regenerate individual failed items.

## Chosen Approach

Use stage APIs plus a dy_auto-owned state machine.

Pixelle-Video will expose stage execution endpoints:

- `POST /api/stages/images/batch`
- `POST /api/stages/videos/batch`
- `POST /api/stages/compose`
- `GET /api/stages/tasks/{stage_task_id}`

dy_auto will:

- Generate or load storyboard frames.
- Resolve model configs through dy_auto's model center.
- Send runtime model config to Pixelle-Video for a stage.
- Persist returned assets in dy_auto.
- Run AI review in dy_auto.
- Route exceptions to the dy_auto review center.
- Trigger the next stage only after the gate passes.

## Architecture

```text
dy_auto
  +-- Series / Episode / Storyboard
  +-- AI Model Center
  +-- VideoProductionRun state machine
  +-- VideoProductionAsset library
  +-- VideoReviewRecord audit trail
  +-- AI Video Review Center
  +-- Pixelle stage client
        |
        | HTTP API
        v
Pixelle-Video
  +-- Stage APIs
  +-- Prompt templates
  +-- FrameProcessor
  +-- Media renderers
  +-- TTS / template / composition services
  +-- Temporary execution logs and output files
```

Ownership boundaries:

| Capability | Owner | Notes |
|---|---|---|
| Content planning | dy_auto | Series, episode, expert team, style lock, storyboard. |
| Model configuration | dy_auto | Only dy_auto stores user-facing model config and secrets. |
| Runtime model execution | Pixelle-Video | Receives runtime config for the current stage. |
| Stage state | dy_auto | dy_auto decides what stage can run next. |
| Intermediate assets | dy_auto | Pixelle returns URLs/paths; dy_auto records assets. |
| AI/human review | dy_auto | Pixelle does not store review state. |
| Prompt/frame templates | Pixelle-Video | dy_auto passes selected template and parameters. |
| Final video library | dy_auto | Final output is written back to dy_auto `GeneratedVideo`/video library. |

## Production State Machine

Each episode production run uses a dy_auto state machine:

```text
draft
  -> storyboard_ready
  -> image_batch_running
  -> image_review_pending
  -> image_human_review_required
  -> image_approved
  -> video_batch_running
  -> video_review_pending
  -> video_human_review_required
  -> video_segments_approved
  -> composing
  -> final_review_pending
  -> completed

any stage
  -> failed
  -> regenerating_item
```

Gate rules:

- Image batch complete: dy_auto saves image assets, runs AI image audit, and either advances to `image_approved` or enters `image_human_review_required`.
- Video batch complete: dy_auto saves video segment assets, runs AI video audit, and either advances to `video_segments_approved` or enters `video_human_review_required`.
- Final composition complete: dy_auto saves final video, optionally runs final audit, and writes to the video library.
- If the audit service fails, dy_auto does not auto-approve. The asset enters human review.

Review statuses:

- `approved`: AI or human approved.
- `rejected`: human or AI rejected with sufficient confidence.
- `needs_human`: low confidence or audit failure.
- `regenerating`: item is being regenerated.
- `failed`: generation failed and needs operator action.

## Pixelle-Video Stage APIs

### Batch Image Generation

```http
POST /api/stages/images/batch
```

Request:

```json
{
  "external_run_id": "dy_auto_run_id",
  "episode_id": "dy_auto_episode_id",
  "frames": [
    {
      "frame_id": "frame-001",
      "image_prompt": "...",
      "reference_urls": ["https://..."],
      "style_constraints": {},
      "duration": 5
    }
  ],
  "model_config": {
    "scene_key": "image_generation",
    "provider": "seedance",
    "model": "seedance-2.0",
    "api_key": "runtime-only",
    "base_url": "https://..."
  },
  "template_config": {}
}
```

Response:

```json
{
  "ok": true,
  "stage_task_id": "pixelle-stage-task-id",
  "assets": [
    {
      "frame_id": "frame-001",
      "asset_type": "image",
      "url": "http://...",
      "local_path": "output/...",
      "metadata": {}
    }
  ],
  "logs": []
}
```

### Batch Image-to-Video Generation

```http
POST /api/stages/videos/batch
```

Request:

```json
{
  "external_run_id": "dy_auto_run_id",
  "frames": [
    {
      "frame_id": "frame-001",
      "approved_image_url": "https://...",
      "video_prompt": "...",
      "reference_urls": ["https://..."],
      "duration": 5,
      "audio_mode": "tts"
    }
  ],
  "model_config": {
    "scene_key": "video_rendering",
    "provider": "seedance",
    "model": "doubao-seedance-2.0-260128",
    "api_key": "runtime-only",
    "base_url": "https://..."
  }
}
```

Response returns one video segment asset per frame.

### Final Composition

```http
POST /api/stages/compose
```

Request:

```json
{
  "external_run_id": "dy_auto_run_id",
  "segments": [
    {
      "frame_id": "frame-001",
      "video_url": "https://...",
      "duration": 5,
      "narration": "..."
    }
  ],
  "edit_manifest": {
    "subtitle_style": {},
    "bgm_policy": {},
    "intro_outro": {},
    "watermark": {},
    "output_spec": {
      "aspect_ratio": "9:16",
      "resolution": "1080x1920"
    }
  }
}
```

Response returns final video path, duration, cover path, and logs.

### Stage Task Status

```http
GET /api/stages/tasks/{stage_task_id}
```

Response:

```json
{
  "ok": true,
  "stage_task_id": "pixelle-stage-task-id",
  "status": "running",
  "progress": 60,
  "assets": [],
  "error": ""
}
```

## dy_auto Backend Interfaces

dy_auto should expose APIs for orchestration and review:

```http
POST /api/video-production/runs
GET  /api/video-production/runs/{run_id}
POST /api/video-production/runs/{run_id}/start-images
POST /api/video-production/runs/{run_id}/approve-images
POST /api/video-production/runs/{run_id}/start-videos
POST /api/video-production/runs/{run_id}/approve-videos
POST /api/video-production/runs/{run_id}/compose
POST /api/video-production/assets/{asset_id}/regenerate
POST /api/video-production/assets/{asset_id}/review
GET  /api/video-production/review-items
```

These routes can wrap existing series, episode, pipeline, audit, and video library behavior. Naming can be adjusted to match local router conventions during implementation.

## dy_auto Data Model

### `VideoProductionRun`

Represents one automated production attempt for an episode.

```text
id
series_id
episode_id
status
current_stage
pixelle_stage_task_id
storyboard_json
model_trace_json
edit_manifest_json
created_at
updated_at
completed_at
error_message
```

### `VideoProductionAsset`

Represents an intermediate or final production asset.

```text
id
run_id
episode_id
frame_id
asset_type: image | video_segment | final_video
stage: image_generation | video_rendering | composition
url
local_path
thumbnail_url
duration_seconds
version
metadata_json
status: generated | review_pending | approved | rejected | regenerating | failed
pixelle_task_id
created_at
updated_at
```

### `VideoReviewRecord`

Represents AI or human review for an asset.

```text
id
asset_id
run_id
review_type: ai | human
status: approved | rejected | needs_human
score
criteria_json
issues_json
reviewer_user_id
model_trace_json
comment
created_at
```

### Model Trace

`model_trace_json` records model identity without secrets:

```json
{
  "image_generation": {
    "model_id": "...",
    "provider": "seedance",
    "model_name": "...",
    "config_version": 3
  },
  "video_rendering": {
    "model_id": "...",
    "provider": "seedance",
    "model_name": "doubao-seedance-2.0-260128",
    "config_version": 3
  }
}
```

## Review Center Frontend

Add a dy_auto page:

```text
/ai-video-review
```

The page only handles AI video production review in v1.

Layout:

```text
left panel
  - pending human review
  - image review
  - video segment review
  - final video review
  - series / episode filters
  - status filters

center panel
  - asset list
  - thumbnail or video preview
  - series, episode, frame number
  - AI review status
  - failure reason
  - current production stage

right panel
  - large image or video player
  - storyboard frame data
  - prompt, narration, reference URLs
  - model trace summary
  - AI review report
  - human action buttons
```

Human actions:

- Approve.
- Regenerate this item.
- Reject and stop the episode.

Episode detail page should keep a lightweight production status strip:

```text
Storyboarding -> Images -> Image Review -> Video Segments -> Video Review -> Compose -> Complete
```

It should link to the review center rather than duplicating the full review UI.

Pipeline monitor should remain an execution monitor, not the main review workspace.

## Single-Item Regeneration

Image regeneration:

```text
failed image asset
  -> status = regenerating
  -> dy_auto sends one frame to /api/stages/images/batch
  -> new image asset version is saved
  -> AI review runs again
```

Video segment regeneration:

```text
failed video segment asset
  -> status = regenerating
  -> dy_auto uses approved image for that frame
  -> dy_auto sends one frame to /api/stages/videos/batch
  -> new video asset version is saved
  -> AI review runs again
```

Regeneration should preserve previous asset versions and review history for traceability.

## Model Configuration Delivery

dy_auto is the only authority for model configuration.

Rules:

- Users configure models only in dy_auto.
- dy_auto resolves runtime models by scene using `model_registry`.
- dy_auto sends runtime config to Pixelle-Video stage APIs.
- Pixelle-Video may hot-load transient stage config for execution, but it does not become a second model configuration UI.
- dy_auto may still update Pixelle-Video `config.yaml` for execution service settings, but user-facing model credentials should come from dy_auto.

Secret rules:

- API keys are sent only server-to-server.
- API keys are never returned to the dy_auto frontend.
- Logs store provider, model name, model id, and config version, not raw secrets.
- Pixelle-Video should redact runtime model config from task logs.

## Error Handling

dy_auto should classify failures:

| Failure | dy_auto behavior |
|---|---|
| Pixelle-Video unavailable | Keep run state, mark stage failed, allow retry. |
| Stage API timeout | Mark current stage failed with retry action. |
| Partial batch success | Save successful assets, mark failed frame assets as failed. |
| AI audit timeout | Mark assets as `needs_human`; do not auto-approve. |
| AI audit rejection | Mark asset `needs_human` or `rejected` based on confidence. |
| Human rejects item | Stop episode or keep blocked until regeneration. |
| Regeneration fails | Keep previous asset version and mark new attempt failed. |
| Final composition fails | Keep approved segment assets and allow compose retry. |

Pixelle-Video stage APIs should return structured errors:

```json
{
  "ok": false,
  "stage_task_id": "pixelle-stage-task-id",
  "error_code": "PROVIDER_TIMEOUT",
  "message": "Seedance task timed out",
  "frame_id": "frame-003",
  "retryable": true
}
```

## Rollout Plan

### Phase 0: Trust, Security, and Contract Gate

Phase 0 is mandatory before any staged generation work. It does not need to generate a final video. It must make the system safe, contract-stable, and no longer broken on the current episode start path.

Scope:

- Add Pixelle-Video stage API schemas.
- Add dy_auto Pixelle stage client.
- Define `VideoProductionRun`, `VideoProductionAsset`, `VideoReviewRecord`, and `RuntimeModelConfig` contracts.
- Fix `POST /api/pipeline/start` so `episode_id` plus missing `director_plan` loads `Episode.storyboard_json`.
- Preserve legacy explicit `director_plan` compatibility.
- Add or restore pipeline run query routes used by the frontend monitor.
- Recursively redact Pixelle config secrets, including `ai_models.scenes.*.api_key`.
- Require Pixelle API key authentication for any stage endpoint carrying runtime credentials.
- Fix Pixelle `/api/files` path resolution before allowed-root checks.
- Change audit gate semantics so missing config, provider failure, timeout, malformed output, and low confidence become `needs_human`, never auto-pass.
- Add Phase 0 tests for route compatibility, secret redaction, stage auth, file path safety, and audit failure semantics.

Exit criteria:

- Existing saved-storyboard pipeline regression passes.
- `GET /api/pixelle/config` cannot expose any configured model secret.
- Pixelle stage endpoints reject unauthenticated runtime credential payloads.
- Audit failure cannot advance a production gate.
- A mocked local run can create a production run and reach the image-stage submit boundary without paid providers.

### Phase 1: Image Stage Review Wedge

- Serialize dy_auto image model config into runtime Pixelle stage payloads.
- dy_auto calls Pixelle batch image stage.
- Image assets are saved in dy_auto.
- AI image review runs automatically.
- Review center displays image exceptions.

### Phase 2: Single-Image Regeneration and Latest-Version Gate

- Single-image regeneration works.
- Previous asset versions and review records remain visible.
- Video stage remains blocked until every frame has a latest approved image asset.

### Phase 3: Video Segment Stage Loop

- dy_auto calls Pixelle batch image-to-video stage only after images pass.
- Video segment assets are saved in dy_auto.
- AI video segment review runs automatically.
- Review center displays video segment exceptions.
- Single-segment regeneration works.

### Phase 4: Final Composition and Video Library

- dy_auto calls Pixelle final composition only after video segments pass.
- Final video is saved to dy_auto video library.
- Episode detail shows full production status.
- Optional final review gate runs.
- End-to-end mocked regression passes.

## Test Plan

Backend dy_auto:

- State machine transitions for every production state.
- Cannot start video stage before images are approved.
- Cannot compose before video segments are approved.
- AI review approval auto-advances the batch.
- AI review failure enters human review.
- Audit service failure enters human review.
- Human approval unblocks the batch.
- Human rejection blocks the episode.
- Single image regeneration creates a new asset version.
- Single video segment regeneration uses the approved image.
- Final composition writes `GeneratedVideo` and updates `Episode`.
- Pixelle outage does not lose run state.
- Runtime model payload contains no frontend-exposed secrets.
- Model trace stores provider/model/config version without API keys.

Pixelle-Video:

- Stage image API validates frame payloads.
- Stage video API validates approved image inputs.
- Stage compose API validates segment ordering and edit manifest.
- Stage task status API reports running/completed/failed.
- Seedance image/video stage can be selected through runtime model config.
- Logs redact API keys.
- Partial frame failure returns frame-level error metadata.

Frontend dy_auto:

- Review center lists pending image and video assets.
- Review center shows prompt, narration, reference URLs, and model trace.
- Approve action updates asset review state.
- Regenerate action changes asset state and shows new version.
- Reject action blocks the episode.
- Episode detail status strip reflects all production stages.
- No stage can be manually advanced while required assets are pending review.

Regression:

- Existing model center flows still work.
- Existing series style lock and storyboard generation still work.
- Existing Pixelle connectivity test still works.
- Existing video library still displays generated final videos.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Pixelle-Video stage APIs duplicate too much pipeline code | Reuse `FrameProcessor`, services, templates, and renderers internally. |
| dy_auto and Pixelle-Video diverge on model config format | Define a small runtime model payload and test it on both sides. |
| Intermediate asset URLs are not accessible to dy_auto or reviewers | dy_auto should copy or register assets into its own asset library after each stage. |
| Review center becomes too broad | Limit v1 to AI video production assets only. |
| Human review slows production | Use AI review auto-approval and send only exceptions to humans. |
| Single-item regeneration creates history confusion | Store `version` and keep prior review records. |
| API keys leak in Pixelle logs | Redact runtime config and test log-safe serialization. |

## Open Decisions Closed

- Review policy: AI review first, human review for exceptions.
- Review gate granularity: batch gates for image batch and video segment batch.
- Integration method: API orchestration.
- Pixelle-Video API changes: allowed; add stage APIs.
- Model config authority: dy_auto only.
- Asset ownership: dy_auto asset library.
- Human review entry: independent AI video review center.
- Review center scope: AI video production only.
- Failed item handling: single-item regeneration.
- Task state authority: dy_auto state machine.
- Chosen architecture: stage APIs plus dy_auto master state machine.

## Spec Self-Review

- Placeholder scan: no placeholder or unresolved TBD remains.
- Internal consistency: dy_auto owns business state, assets, reviews, and model config; Pixelle-Video owns stage execution.
- Scope check: the feature is large, but phased and centered on one integration architecture. It should become one implementation plan with four phases.
- Ambiguity check: first-version gates, ownership, API style, review policy, regeneration behavior, and non-goals are explicit.

## /autoplan Review Report

Review captured on 2026-05-25. Base branch detection fell back to local `master` because no `origin` remote exists. UI scope: yes. DX scope: yes. Loaded review methods: CEO, design, engineering, and developer experience. Codex CLI outside voice ran in read-only mode. Claude subagent voice was unavailable in this tool context, so consensus tables mark that voice as unavailable.

### Phase 1: CEO Review

#### Premise Challenge

| Premise | Verdict | Risk | Decision |
|---|---|---|---|
| dy_auto should be the orchestration layer. | Valid. dy_auto already owns Series, Episode, storyboard, model config, audit, and video library state. | If orchestration remains inside Pixelle, dy_auto cannot expose review gates or asset history. | Keep. |
| Pixelle-Video should remain the execution layer. | Valid, but only if stage APIs wrap existing Pixelle internals instead of duplicating pipeline logic. | Six-month regret is two video pipelines that diverge. | Keep with reuse requirement. |
| AI review first, human review only for exceptions. | Valid product direction. | Current audit code can auto-pass missing API keys or parse failures, which violates the premise. | Keep, but audit semantics must change before gates are trusted. |
| Runtime model config should flow from dy_auto to Pixelle. | Valid. | Existing Pixelle config bridge writes decrypted model keys to disk and `GET /api/pixelle/config` does not recursively redact `ai_models`. | Keep, but runtime credentials must be transient and redacted. |
| Single-item regeneration is enough for v1. | Valid. | Needs version invariants so old approved assets do not unblock the next stage accidentally. | Keep with explicit latest-version rules. |

Premise gate: accepted for review, with two hard constraints added: no persisted runtime secrets in Pixelle config, and no trusted review gate until audit failure semantics are corrected.

#### What Already Exists

| Sub-problem | Existing leverage |
|---|---|
| Series, episodes, style lock, storyboard | `server/app/db_models.py` has `Series.story_bible_json`, `Episode.storyboard_json`, character/scene reference fields, and `GeneratedVideo`. |
| Auto storyboard | `server/app/routers/director.py` has `/api/director/auto-plan` and already writes `Episode.storyboard_json`. |
| Pixelle bridge | `server/app/routers/pixelle.py` and `server/app/services/pixelle_client.py` provide proxy/config bridge and retrying HTTP client. |
| Current pipeline launch | `server/app/routers/pipeline.py` submits a full Pixelle async video job and writes `PipelineRun`/`GeneratedVideo`. |
| AI audit | `server/app/routers/audit.py` audits images through configured audit models and writes `AuditReport`. |
| Model center | `AIModel`, `model_registry`, and AI config UI already cover scenario-based model configuration. |
| Frontend anchors | `SeriesDetailPage.vue`, `PipelineMonitorPage.vue`, `AIConfigPage.vue`, `VideosPage.vue`, and navigation already provide the main user entry points. |
| Pixelle execution | Pixelle has `/api/video/generate/async`, `/api/image/generate`, `/api/tasks/{id}`, `FrameProcessor`, render services, and `AIModelRegistry`. |

#### Dream State Delta

```text
CURRENT
  dy_auto sends an opaque full-video job to Pixelle and waits/polls.

THIS PLAN
  dy_auto owns run state, assets, reviews, and gates.
  Pixelle exposes stage APIs for image, video segment, and final compose.

12-MONTH IDEAL
  dy_auto has observable, resumable production runs with stage metrics,
  cost traces, model traces, retry policies, reviewer SLAs, and provider
  fallback strategies, while Pixelle remains a stateless execution service.
```

#### Implementation Alternatives

| Approach | Effort | Risk | Pros | Cons | Decision |
|---|---:|---|---|---|---|
| Stage APIs plus dy_auto state machine. | High | Medium | Best visibility, review gates, regeneration, and asset history. | Requires new contracts on both projects. | Selected. |
| Keep Pixelle full pipeline, inspect outputs afterward. | Medium | High | Less Pixelle change. | Review gates are fake because bad assets are caught too late. | Rejected. |
| Embed Pixelle Python services directly inside dy_auto. | High | High | No HTTP boundary. | Tight coupling, shared dependency/runtime risk. | Rejected. |
| First vertical slice only: storyboard to image review. | Medium | Low | De-risks contracts before video/compose stages. | Slower to reach full automation. | Use as rollout Phase 1.5. |

#### Error & Rescue Registry

| Error | User-visible rescue |
|---|---|
| Pixelle unavailable | Run remains at current stage with retry action and clear Pixelle connection status. |
| Stage API partial success | Save successful assets, mark failed frame assets, allow single-item regeneration. |
| Audit model missing, times out, or returns malformed JSON | Mark asset `needs_human`; never auto-approve. |
| Runtime model config invalid | Block stage start with problem, cause, and fix: model scene, provider, missing field. |
| Human approves stale asset version | Reject action with stale-version message and reload latest asset. |
| Compose fails | Preserve approved video segments and expose compose retry. |
| Pixelle file URL inaccessible | Copy/register asset into dy_auto asset library and show repair action. |

#### NOT In Scope

| Item | Rationale |
|---|---|
| Douyin publishing loop | Product goal stops at reviewed final video library. |
| Generic review center | v1 review center should only cover AI video production assets. |
| Visual timeline editor | The chosen workflow is staged generation and review, not manual editing. |
| Multi-user reviewer permissions | Useful later, not needed for first controlled gate. |
| Cost budgets and model fallback chains | Important later, but would widen Phase 1 too much. |

#### CEO Failure Modes Registry

| Failure mode | Severity | Critical gap? | Fix |
|---|---|---:|---|
| Build new Pixelle stage code that duplicates existing pipeline internals. | High | Yes | Stage APIs must wrap `FrameProcessor`, existing render services, and composition paths. |
| Ship review gates while audit failures auto-pass. | High | Yes | Change audit result contract to `approved/rejected/needs_human` before enabling auto-advance. |
| Persist runtime credentials in Pixelle config. | Critical | Yes | Runtime stage payloads must be transient; recursive redaction is mandatory. |
| Attempt all phases at once. | Medium | No | Ship one vertical slice first: image stage, review, regeneration. |

#### CEO Dual Voices Consensus

| Dimension | Codex CLI | Claude subagent | Consensus |
|---|---|---|---|
| Premises valid? | Yes with security constraints | Unavailable | Single-model signal |
| Right problem to solve? | Yes | Unavailable | Single-model signal |
| Scope calibration correct? | Too broad unless vertical-sliced | Unavailable | Single-model signal |
| Alternatives explored? | Needs explicit vertical slice | Unavailable | Single-model signal |
| Competitive/market risks covered? | Mostly product-internal | Unavailable | Single-model signal |
| Six-month trajectory sound? | Sound if no duplicated pipeline | Unavailable | Single-model signal |

Phase 1 complete. Codex concerns: 4. Claude subagent: unavailable. Consensus: 0/6 confirmed, 6 single-model signals.

### Phase 2: Design Review

#### Design Scope Assessment

Initial completeness: 7/10. The plan defines the review center layout and the episode status strip, but it does not yet specify router/navigation placement, permissions, loading/empty/error states, stale asset conflict states, or accessibility behavior for approval controls.

#### Design Litmus Scorecard

| Pass | Score | Finding | Decision |
|---|---:|---|---|
| Information architecture | 8/10 | Left filters, asset list, and detail panel are the right structure. | Keep. |
| Interaction states | 5/10 | Missing loading, empty, partial batch, stale version, regenerating, and Pixelle offline states. | Add to implementation plan. |
| User journey | 7/10 | Review center is clear, but episode page needs a direct blocked-action explanation and queue counts. | Add status strip details. |
| AI slop risk | 7/10 | Plan exposes prompts/model trace, which helps. Needs side-by-side prior/current asset versions. | Add version comparison. |
| Design system alignment | 7/10 | Reuse existing admin shell and dense operational UI. | Keep. |
| Responsive/accessibility | 5/10 | No keyboard, focus, video controls, touch target, or small-screen strategy. | Add explicit requirements. |
| Unresolved decisions | 6/10 | Batch approve behavior and final-review gate UI are underspecified. | Resolve before implementation. |

#### Required UI States

| Area | States to specify |
|---|---|
| Review list | empty, loading, failed load, filtered empty, pending, needs human, regenerating, stale version, failed generation. |
| Asset preview | image missing, video transcoding, video load failure, unsupported asset type, old version selected. |
| Review action buttons | disabled while stale/regenerating, optimistic progress, success, validation error, conflict reload. |
| Episode status strip | queued, running stage, blocked by human review, failed with retry, completed. |
| Pipeline monitor | execution-only view with link to review center when blocked. |

#### Design Dual Voices Consensus

| Dimension | Codex CLI | Claude subagent | Consensus |
|---|---|---|---|
| Information hierarchy serves user? | Yes | Unavailable | Single-model signal |
| Missing states covered? | No | Unavailable | Single-model signal |
| Journey coherent? | Mostly | Unavailable | Single-model signal |
| UI specificity enough? | Partial | Unavailable | Single-model signal |
| Responsive/a11y covered? | No | Unavailable | Single-model signal |
| Implementation ambiguity low? | No | Unavailable | Single-model signal |

Phase 2 complete. Codex concerns: 3. Claude subagent: unavailable. Consensus: 0/6 confirmed, 6 single-model signals.

### Phase 3: Engineering Review

#### Scope Challenge

This plan is architecturally feasible, but it is a real cross-repo feature and should not be treated as a small extension to the existing `pipeline.py`. The critical path is:

```text
dy_auto
  VideoProductionRun state machine
    -> VideoProductionAsset versions
    -> VideoReviewRecord gates
    -> PixelleStageClient
        -> Pixelle /api/stages/*
            -> Stage task manager
            -> FrameProcessor/render services
            -> output file service
```

The current dy_auto pipeline route still requires `director_plan`, while `SeriesDetailPage.vue` calls auto-plan and then starts the pipeline without passing that returned storyboard. That makes the current generation flow fragile before the new staged system begins. Fixing that contract belongs in the first implementation phase.

#### Architecture Findings

| Finding | Severity | Fix |
|---|---|---|
| Existing `PipelineRun.layers_json` cannot represent per-frame assets, review history, or versioned regeneration. | High | Add `VideoProductionRun`, `VideoProductionAsset`, and `VideoReviewRecord` tables early. |
| Pixelle task state is in-memory and only typed as `video_generation`. | High | Add typed stage task types or a stage task wrapper with persisted enough metadata for dy_auto reconciliation. |
| Runtime model config contract mismatches Pixelle provider naming. | High | Add a `RuntimeModelConfig` adapter: dy_auto provider/model -> Pixelle internal provider/id. |
| Existing full pipeline blocks HTTP request while polling. | Medium | Stage start endpoints should return immediately; a worker or polling endpoint should advance state. |
| Single `regenerating_item` run status cannot represent parallel asset-level regeneration. | Medium | Store regeneration at asset level and compute run stage from latest required assets. |

#### Security Findings

| Finding | Severity | Fix |
|---|---|---|
| `GET /api/pixelle/config` redacts only `llm` and `comfyui`, not serialized `ai_models` secrets. | Critical | Implement recursive redaction for keys matching `api_key`, `api_secret`, `secret`, `token`, `authorization`. |
| `PUT /api/pixelle/config` writes decrypted AI model API keys into Pixelle `config.yaml`. | Critical | Prefer transient stage runtime config; if disk bridge remains, never expose it and encrypt/redact logs. |
| Pixelle `/api/files/{file_path}` uses unresolved path checks and may allow traversal. | High | Resolve requested path and allowed roots before `relative_to` checks. |
| Pixelle middleware allows all requests when `PIXELLE_API_KEY` is unset. | Medium | Require API key for any stage endpoint carrying runtime credentials. |
| Review and model traces could leak prompts or credentials if logged raw. | Medium | Define safe trace schema and log redaction tests. |

#### Code Quality Findings

| Finding | Severity | Fix |
|---|---|---|
| API names are coherent but `approve-images` and `approve-videos` sound batch-only while review happens per asset. | Medium | Use batch gate endpoints plus asset-level review endpoints; document exact semantics. |
| `model_config.provider` uses business names such as `seedance`, while Pixelle renderers use `volcengine`. | Medium | Normalize provider naming in one adapter instead of branching through handlers. |
| New stage orchestration should not live inside current thin `pipeline.py`. | Medium | Add `video_production.py` router and `video_production_service.py`; keep old pipeline compatibility as a wrapper. |

#### Test Diagram

| New path | Coverage type | Existing? | Gap decision |
|---|---|---:|---|
| Create production run from series/episode/storyboard | Backend unit/integration | No | Add. |
| Resolve dy_auto model config into transient Pixelle stage config | Backend unit | Partial via model registry | Add adapter tests and secret redaction tests. |
| Submit image batch to Pixelle stage API | dy_auto mocked integration + Pixelle API test | No | Add. |
| Save image assets with versions | Backend unit | No | Add. |
| AI image audit approved -> image gate advances | Backend unit | Partial image audit exists | Add state transition tests. |
| AI image audit error -> human review | Backend unit | No; current code auto-passes some errors | Add and fix. |
| Human approve/reject/regenerate image | Backend integration + frontend component | No | Add. |
| Latest approved image required before video stage | Backend unit | No | Add invariant test. |
| Submit video segment batch to Pixelle stage API | dy_auto mocked integration + Pixelle API test | No | Add. |
| Save video segment assets and run audit | Backend unit/integration | No video audit route | Add. |
| Compose only after latest segment for every frame approved | Backend unit | No | Add. |
| Final video writes `GeneratedVideo` and `Episode.video_url` | Backend integration | Partial in old pipeline | Add staged-flow test. |
| Review center route/nav/page renders pending items | Frontend unit | No | Add. |
| Review actions handle loading/error/stale/regenerating states | Frontend unit | No | Add. |
| Pixelle stage tasks expose status/progress/assets/errors | Pixelle API unit | No | Add. |
| Pixelle file endpoint rejects traversal | Pixelle security test | No | Add. |

#### Performance Review

| Risk | Impact | Fix |
|---|---|---|
| Synchronous HTTP polling ties up request workers. | Long generations can exhaust web workers. | Background stage worker or explicit submit/poll API. |
| Batch asset queries can become N+1 on review center. | Slow review list with many frames. | List endpoint should return denormalized asset/review summary with pagination. |
| Copying large videos into dy_auto synchronously can block API. | Slow finalization. | Register remote URL first, copy asynchronously where needed. |
| Repeated model config resolution per frame. | Extra DB/secrets decrypt work. | Resolve once per stage and store non-secret trace. |

#### Eng Failure Modes Registry

| Failure mode | Severity | Critical gap? | Fix |
|---|---|---:|---|
| Stage starts without approved latest asset versions. | High | Yes | Enforce transition guards in service layer. |
| Audit service failure auto-approves. | High | Yes | `needs_human` on every audit exception or malformed response. |
| Runtime secrets leak through config API or logs. | Critical | Yes | Transient payload, recursive redaction, tests. |
| Pixelle file traversal exposes local files. | High | Yes | Resolve paths and test traversal cases. |
| Pixelle restarts lose stage task memory. | Medium | No | dy_auto owns state; Pixelle task loss should become retryable stage failure. |

#### Eng Dual Voices Consensus

| Dimension | Codex CLI | Claude subagent | Consensus |
|---|---|---|---|
| Architecture sound? | Yes with added tables and stage wrappers | Unavailable | Single-model signal |
| Test coverage sufficient? | No | Unavailable | Single-model signal |
| Performance risks addressed? | Partial | Unavailable | Single-model signal |
| Security threats covered? | No | Unavailable | Single-model signal |
| Error paths handled? | Partial | Unavailable | Single-model signal |
| Deployment risk manageable? | Yes if phased | Unavailable | Single-model signal |

Phase 3 complete. Codex concerns: 8. Claude subagent: unavailable. Consensus: 0/6 confirmed, 6 single-model signals.

### Phase 3.5: DX Review

#### Developer Persona

Primary developer: a full-stack AI-video engineer maintaining dy_auto and integrating Pixelle locally. They need predictable API contracts, clear model-scene mapping, reproducible local setup, and errors that say which service, stage, frame, and model failed.

#### Developer Journey Map

| Stage | Current plan support | Gap |
|---|---|---|
| Discover | Clear architecture summary. | Add exact endpoint list and ownership diagram to implementation plan. |
| Evaluate | Good goals/non-goals. | Add vertical-slice milestone and acceptance criteria. |
| Install | Not covered. | Add dy_auto + Pixelle local env prerequisites. |
| Hello world | Not covered. | Add mocked stage run under 5 minutes. |
| Integrate | Stage APIs listed. | Add schemas, examples, status values, error codes. |
| Debug | Error handling table exists. | Add trace IDs: `run_id`, `stage_task_id`, `frame_id`, `asset_id`. |
| Upgrade | Not covered. | Add migrations and compatibility with old `/api/pipeline/start`. |
| Scale | Partially covered. | Add pagination and background polling. |
| Migrate | Not covered. | Add migration plan from `PipelineRun` to staged runs. |

#### TTHW Assessment

Current expected time to first mocked staged run: 30-60 minutes because contracts, migrations, and Pixelle stage routes are not implemented. Target: under 5 minutes with a seeded series, locked style, mock Pixelle provider, and one command/test that produces image asset -> review item -> approve -> video segment -> compose.

#### DX Scorecard

| Dimension | Score | Finding |
|---|---:|---|
| Getting started | 4/10 | No hello-world flow for local dy_auto + Pixelle staged generation. |
| API design | 7/10 | Names are mostly guessable, but batch vs asset review semantics need precision. |
| Error messages | 5/10 | Error categories exist, but not problem/cause/fix/error-code contract. |
| Documentation | 6/10 | Spec is readable; examples need copy-paste payloads for all stages. |
| Upgrade/migration | 4/10 | Compatibility with old pipeline is stated but not planned deeply. |
| Dev environment | 5/10 | Two-repo setup and Pixelle path/env requirements need explicit checks. |
| Ecosystem | 6/10 | Reuses existing model center and Pixelle, but provider naming needs normalization docs. |
| Measurement | 4/10 | No TTHW, stage latency, audit exception rate, or regeneration metrics. |
| Overall | 5.1/10 | Good architecture direction; missing operational DX details. |

#### DX Implementation Checklist

- Add `/api/stages/*` OpenAPI examples in Pixelle.
- Add dy_auto stage client contract tests with mocked Pixelle responses.
- Add a seeded local mock provider path so a developer can run a complete staged flow without paid models.
- Add structured errors: `error_code`, `message`, `frame_id`, `asset_id`, `retryable`, `repair_action`.
- Add a compatibility note: old `/api/pipeline/start` remains but delegates to staged orchestration when `episode_id` exists.
- Add migration notes for new production tables.

#### DX Dual Voices Consensus

| Dimension | Codex CLI | Claude subagent | Consensus |
|---|---|---|---|
| Getting started under 5 min? | No | Unavailable | Single-model signal |
| API naming guessable? | Mostly | Unavailable | Single-model signal |
| Error messages actionable? | Partial | Unavailable | Single-model signal |
| Docs findable and complete? | Partial | Unavailable | Single-model signal |
| Upgrade path safe? | No | Unavailable | Single-model signal |
| Dev environment friction-free? | No | Unavailable | Single-model signal |

Phase 3.5 complete. DX overall: 5.1/10. TTHW: 30-60 min -> target under 5 min.

### Cross-Phase Themes

| Theme | Phases | Signal |
|---|---|---|
| Secrets must not leak through Pixelle config or logs. | CEO, Eng, DX | Critical and must be fixed before runtime model delivery. |
| Stage orchestration must be real state, not `layers_json`. | CEO, Eng | High-confidence architecture requirement. |
| Audit failures must route to human review. | CEO, Eng, Product | Core product promise depends on it. |
| First implementation should be a vertical slice. | CEO, Eng, DX | Reduces cross-repo risk and proves the contract. |
| Review center needs explicit operational states. | Design, Eng, DX | Prevents hidden production behavior. |

### Auto-Decided Changes To Apply To The Implementation Plan

| # | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|
| 1 | Add real `VideoProductionRun`, `VideoProductionAsset`, and `VideoReviewRecord` tables in Phase 1. | Mechanical | Completeness | Existing `PipelineRun.layers_json` cannot enforce review gates or asset versions. | Reusing only `PipelineRun`. |
| 2 | Fix Pixelle config redaction and avoid persisted runtime secrets before stage runtime config ships. | Mechanical | Explicit over clever | Secret leakage is a hard security boundary. | Relying on UI convention. |
| 3 | Change audit failures to `needs_human`, never auto-pass. | Mechanical | Completeness | The review gate promise fails otherwise. | Treating missing audit config as pass. |
| 4 | Add Pixelle file path traversal fix to Phase 1 security work. | Mechanical | Completeness | Generated asset display depends on safe file serving. | Deferring until later. |
| 5 | Add provider/runtime adapter tests for dy_auto -> Pixelle model config. | Mechanical | DRY | One adapter prevents duplicated provider mapping logic. | Per-route provider branching. |
| 6 | Start implementation with one vertical slice: image stage, image review, single-image regeneration. | Taste | Pragmatic | It proves the hardest contract before video/compose complexity. | Building all stages at once. |
| 7 | Add explicit review-center states and accessibility requirements. | Mechanical | Completeness | Hidden states create perceived black-box behavior. | Generic page layout only. |
| 8 | Add background stage orchestration rather than long request polling. | Mechanical | Pragmatic | Long-running HTTP requests are fragile for video generation. | Blocking inside request handlers. |
| 9 | Preserve old `/api/pipeline/start` compatibility but delegate to staged orchestration when possible. | Mechanical | Bias toward action | Keeps existing UI paths working while new flow lands. | Breaking old endpoint. |
| 10 | Require stage endpoints carrying runtime credentials to use Pixelle API key auth. | Mechanical | Completeness | Runtime model payloads include secrets. | Dev-mode unauthenticated stage calls. |

### Final Gate Recommendation

Approve the architecture with required revisions before implementation planning:

- Add a Phase 0 security/contracts step for secret redaction, Pixelle file path safety, API key enforcement, and audit failure semantics.
- Split rollout so the first vertical slice is storyboard -> image stage -> AI/human image review -> single-image regeneration.
- Define explicit state invariants: latest approved asset version per frame is required for next stage.
- Add developer hello-world and mock provider path so local integration can be verified quickly.

No user challenge is raised because no second independent voice was available to confirm a contradiction. The only taste choice to review is whether to ship the first vertical slice before video/compose. Recommendation: yes, vertical slice first.

## /plan-design-review Report

Review captured on 2026-05-25 for the AI video review and production transparency UI. The gstack designer binary was not available on this machine, so no generated PNG mockups were produced. A text/HTML wireframe was generated instead at `C:\Users\HNXE\.gstack\projects\dy_auto\designs\ai-video-review-20260525\review-center-wireframe.html`.

### Design Scope Assessment

Initial design completeness: 6/10.

The plan already has the right product direction: a dedicated review center, a lightweight episode status strip, and a pipeline monitor that stays execution-focused. It is not yet implementation-ready because it does not define enough of what users see in blocked, partial, stale, regenerating, and failed states.

A 10/10 version of this plan specifies:

- The first-screen hierarchy for `/ai-video-review`.
- The exact navigation placement under the existing AI video section.
- The relationship between review center, episode detail, pipeline monitor, and expert-team console.
- All visible states for queue, asset detail, review actions, preview media, and production status.
- Desktop, tablet, and mobile layout behavior.
- Keyboard, focus, screen-reader, video-control, and contrast requirements.
- Copy rules for "not a black box" production visibility.

### DESIGN.md Status

No `DESIGN.md` exists. Implementation should follow existing local UI tokens and components, but this is now a design debt item. A future `DESIGN.md` should codify the admin-console design system rather than letting every feature infer it from existing Vue files.

### What Already Exists

| Existing pattern | Reuse decision |
|---|---|
| `web/src/styles/tokens.css` | Reuse OLED dark surface, cyan status accent, amber warning, danger/success colors, Fira Sans/Fira Code tokens. |
| `web/src/styles/components.css` | Reuse `btn-primary`, `btn-ghost`, `btn-danger`, badges, tab bar, inputs, and table styling. Avoid adding a new visual language. |
| `SeriesDetailPage.vue` | Reuse as the launch and episode status entry point, but add a clearer production status strip and blocked review link. |
| `PipelineMonitorPage.vue` | Keep execution telemetry here; add a prominent handoff when a run is blocked by review. |
| `AgencyConsolePage.vue` | Reuse the "transparent console" pattern for read-only expert/process visibility. |
| `navigation.js` | Add `AI Video Review` under the existing AI video category and map `/ai-video-review`. |

### NOT In Scope For Design

| Item | Rationale |
|---|---|
| Visual timeline editor | The product decision is staged generation and review, not manual timeline editing. |
| Full Pixelle-Video UI redesign | dy_auto should expose orchestration and review, not rebuild Pixelle's own execution panels. |
| Generic review center for all content | v1 must stay scoped to AI video production assets. |
| Reviewer role-management UI | Useful later, but not required to prove the review workflow. |
| Marketing/landing redesign | This is an operational app screen, not a conversion page. |

### Pass 1: Information Architecture

Rating before fix: 7/10. Rating after this supplement: 9/10.

The review center should be an operational workspace, not a dashboard mosaic. The first screen must answer three questions in order:

1. What needs human action now?
2. Which asset is selected and why was it blocked?
3. What action can safely unblock or stop the run?

Desktop information architecture:

```text
/ai-video-review

top bar
  title: AI Video Review
  subtitle: Human exceptions only
  queue counters: needs human, regenerating, failed, auto-approved
  service status: Pixelle, audit provider, current run polling

main workspace
  left rail: queue filters
    - Needs human
    - Images
    - Video segments
    - Final videos
    - Regenerating
    - Failed
    - Series / episode selectors

  center list: review queue
    - thumbnail / mini video frame
    - series, episode, frame
    - asset type, version, latest/stale marker
    - AI review reason and confidence
    - current production stage

  right detail: selected asset
    - large preview
    - prompt, narration, reference URLs
    - continuity notes
    - model trace without secrets
    - AI review report
    - version history
    - actions: approve latest, regenerate, reject and stop
```

Navigation flow:

```text
Series Detail
  -> Start production
  -> Status strip shows current gate
  -> If blocked, link to /ai-video-review?run_id=...

Pipeline Monitor
  -> Shows execution telemetry only
  -> If review blocked, link to the exact review item

AI Video Review
  -> Resolves or regenerates blocked assets
  -> Returns to series detail or current run
```

Implementation requirement: `/ai-video-review` must support deep links by `run_id`, `asset_id`, `series_id`, `episode_id`, and `status`, so pipeline and series pages can send users to the exact blocked item.

### Pass 2: Interaction State Coverage

Rating before fix: 5/10. Rating after this supplement: 9/10.

| Feature | Loading | Empty | Error | Success | Partial |
|---|---|---|---|---|---|
| Review queue | Skeleton rows with stable thumbnail boxes. | "No assets need human review" plus link back to active productions. | Inline retry with failed endpoint and timestamp. | Item disappears or moves to approved filter. | Show mixed batch counts: approved, needs human, failed. |
| Queue filters | Disabled with spinner while counts load. | Disabled filters show count 0, not hidden. | Counts replaced by warning marker. | Active filter keeps visible count. | Counts update independently from list. |
| Asset preview | Fixed-ratio placeholder, never layout shift. | "No preview available" with file path/url if present. | Show media load error and open/copy URL action. | Preview remains visible after action until list refresh. | Video transcoding or image copy state appears over preview. |
| Detail metadata | Label/value skeletons. | Missing fields show `Not provided`, not blank space. | Failed metadata section does not block preview. | Model trace and audit report visible. | If stale version selected, show latest-version banner. |
| Approve action | Button disabled with "Approving latest..." text. | Hidden if there is no selected item. | Conflict error asks user to reload latest item. | Toast/status line says stage gate re-evaluated. | If batch still has other blockers, show remaining count. |
| Regenerate action | Button disabled with "Regenerating..." text. | Hidden if selected asset is final-only and cannot regenerate. | Keep old version visible and show retry. | New version appears with version badge. | Old version stays accessible in history. |
| Reject and stop | Confirmation modal with run impact. | Hidden if no selected item. | Failed stop action keeps item selected. | Run status becomes blocked/stopped. | If multiple runs selected, action is not allowed. |
| Episode status strip | Determinate labels with current stage. | If no run, show "Not started" and primary action. | Failed stage shows retry and error reason. | Completed links to final video. | Blocked stage links to review center with item count. |
| Pipeline monitor handoff | Execution steps load as today. | If no staged run, show legacy pipeline state. | Polling errors show retry, not blank page. | Completed links to video library. | Review-blocked runs show "Action required in review center." |

### Pass 3: User Journey And Emotional Arc

Rating before fix: 7/10. Rating after this supplement: 9/10.

| Step | User does | User should feel | UI support |
|---|---|---|---|
| 1 | Starts production from series detail. | Confident that automation has begun. | Status strip immediately shows `Storyboarding` then `Images`. |
| 2 | Leaves production running. | Safe to leave and return. | Pipeline monitor and series detail show the same current gate. |
| 3 | AI review blocks one image. | Clear, not confused. | Series status says "Image review needs 1 human decision" with direct link. |
| 4 | Opens review center. | Oriented within 5 seconds. | Queue counters, selected blocker, and primary action are visible above the fold. |
| 5 | Inspects the asset. | Trusts the decision context. | Preview, AI reason, prompt, refs, model trace, and continuity notes are visible together. |
| 6 | Regenerates one item. | In control, not restarting the episode. | Old version remains visible; new version gets `v2 latest` badge. |
| 7 | Approves latest asset. | Understands what happens next. | Success state says remaining blockers or next stage. |
| 8 | Final video completes. | Can find output quickly. | Series detail and video library both show final video link. |

Time-horizon design:

- First 5 seconds: show blocked count, selected asset, and next action.
- First 5 minutes: let the user inspect why AI failed and recover without restarting.
- Long-term trust: preserve version history and model/audit traces so decisions are explainable later.

### Pass 4: AI Slop Risk

Rating before fix: 7/10. Rating after this supplement: 9/10.

Classifier: App UI. This should feel like a dense operations console, not a SaaS landing page or decorative dashboard.

Design constraints:

- No hero section.
- No generic feature-card grid.
- No decorative gradient orbs or marketing copy.
- Cards are allowed only for repeated queue items, detail panels, and modals.
- Prefer tables/lists, split panes, badges, tabs, fixed-ratio previews, and action bars.
- Use utility copy: "Needs human review", "Regenerating v3", "Latest version required", "Audit failed: face mismatch".
- Avoid centered everything; operational screens should align left and scan vertically.
- Keep border radius at existing component scale; do not increase radius for visual softness.
- Do not add ornamental icons; icons should only identify actions or statuses.

### Pass 5: Design System Alignment

Rating before fix: 6/10 because there is no `DESIGN.md`. Rating after this supplement: 8/10.

Implementation should align to existing app tokens:

- Surface: `--bg-void`, `--bg-deep`, `--bg-surface`, `--bg-elevated`.
- Accent: cyan for active/running, amber for human attention, red for blocking/failure, green for approved/completed.
- Typography: existing Fira Sans/Fira Code token stack.
- Components: reuse `btn-primary`, `btn-ghost`, `btn-danger`, `badge-*`, `tab-bar`, form labels, and table styling.
- Layout rhythm: page padding 24px desktop, 14-16px mobile, 8px panel radius for this operational workspace.

Design debt: create `DESIGN.md` later with the app shell, operational panel, queue list, badge, form, modal, and status strip patterns. Do not block this feature on that document, but avoid inventing new tokens.

### Pass 6: Responsive And Accessibility

Rating before fix: 5/10. Rating after this supplement: 9/10.

Responsive rules:

| Viewport | Layout |
|---|---|
| >= 1200px | Three-pane workspace: filters 260px, queue 420px, detail flexible. Preview stays above metadata/actions. |
| 768-1199px | Two-pane workspace: filters 220px and queue/detail stacked or tabbed in the main area. Selected asset detail appears below list. |
| < 768px | Single-column. Filters become horizontal chips or collapsible sheet. Queue comes first; detail opens as full-screen drawer. Actions become sticky bottom bar. |

Accessibility rules:

- All action buttons must be reachable by keyboard and show visible focus rings.
- Queue items use button/listbox semantics; selected item is announced.
- Preview region has `aria-label` and media controls remain native when video is shown.
- Approve/regenerate/reject actions must have accessible names including asset type and frame.
- Confirmation modal traps focus and returns focus to the originating button.
- Do not rely on color alone; statuses need text labels and icons or badges.
- Body text contrast must be at least 4.5:1; small secondary text must remain readable against dark panels.
- Touch targets must be at least 44px high on mobile.
- Reduced-motion users should not get pulsing or shimmer animations for long-running states.

### Pass 7: Unresolved Design Decisions

| Decision needed | Recommendation | If deferred |
|---|---|---|
| Is batch approval allowed? | No for v1. Require per-asset approval for human exceptions. | A user could approve a mixed batch without inspecting each failed item. |
| Does final video need human review in v1? | Optional final audit only; no mandatory final human gate unless AI flags it. | The flow may feel slower than necessary. |
| How are old/new versions compared? | Show a compact version rail in the detail panel with latest badge and prior review status. | Regeneration history becomes hard to trust. |
| Where does `/ai-video-review` live? | Add it under AI Video navigation as "AI Video Review"; also deep-link from series and pipeline. | Users will see blocked runs but not know where to fix them. |
| What happens when Pixelle is offline? | Review center remains readable; stage actions show disabled state and repair message. | Users may think assets/reviews disappeared. |
| What is the mobile pattern? | Detail opens as a full-screen drawer with sticky actions. | The three-pane design will collapse poorly on phones. |

### Design TODO Candidates

These are not added to `TODOS.md` because no project `TODOS.md` exists yet. Carry them into the implementation plan.

| What | Why | Recommendation |
|---|---|---|
| Create `DESIGN.md` for dy_auto admin screens. | Current design system exists only as tokens/components and inferred patterns. | Defer until after this feature lands, but record as design debt. |
| Add review-center mobile QA cases. | Three-pane workspaces usually fail first on small screens. | Include in frontend test plan. |
| Add keyboard workflow test for approve/regenerate/reject. | Review actions are high-risk and must work without mouse. | Include before shipping review center. |

### Design Completion Summary

| Pass | Before | After | Status |
|---|---:|---:|---|
| Information Architecture | 7/10 | 9/10 | Clear enough to implement. |
| Interaction States | 5/10 | 9/10 | State table added. |
| User Journey | 7/10 | 9/10 | Emotional arc and handoffs added. |
| AI Slop Risk | 7/10 | 9/10 | Operational app constraints added. |
| Design System Alignment | 6/10 | 8/10 | Existing tokens/components mapped; missing `DESIGN.md` remains. |
| Responsive & Accessibility | 5/10 | 9/10 | Viewport and a11y rules added. |
| Unresolved Decisions | 6/10 | 9/10 | Recommendations recorded for v1. |

Final design verdict: approved with implementation constraints. The review center should be built as a dense operational exception queue, not a broad dashboard or visual editor. The plan is now specific enough for implementation planning, with the remaining design debt limited to formalizing a reusable `DESIGN.md`.

## /plan-ceo-review Report

Review captured on 2026-05-25. Mode selected: HOLD SCOPE with strategic tightening. The plan is already ambitious enough; the CEO-level job is to make the wedge sharper, remove hidden trust risks, and prevent a two-pipeline mess.

### System Audit

| Area | Finding | Strategic implication |
|---|---|---|
| Git state | The spec is modified by `/autoplan` and `/plan-design-review`; many unrelated workspace files are dirty. | Implementation must be staged carefully and should not mix this feature with unrelated device/task changes. |
| Stash | `stash@{0}` exists on `master`: `fix: address 12 review findings`. | Before heavy implementation, confirm no stashed fix overlaps pipeline/security/model work. |
| ADRs | ADR-0002 merged Seedance into pipeline L4; ADR-0003 moved video generation to sync polling; ADR-0004 made Director a pipeline pre-step. | This new plan partially supersedes ADR-0003 and reshapes ADR-0002. Add a new ADR when implementation starts. |
| Design system | No `DESIGN.md`. | Acceptable for v1, but review-center implementation must reuse existing tokens/components and avoid inventing a new design language. |
| TODOs | No project `TODOS.md`; deferred work currently lives in specs. | Any deferred CEO/design debt must be carried into the implementation plan explicitly. |
| Landscape | Runway documents moderation and task failures as first-class API concerns ([moderation](https://docs.dev.runwayml.com/api-details/moderation), [task failures](https://docs.dev.runwayml.com/errors/task-failures/)); Adobe Firefly emphasizes Content Credentials and transparency for generated assets ([overview](https://helpx.adobe.com/firefly/using/content-credentials.html), [enterprise](https://www.adobe.com/products/firefly/enterprise.html)). | Asset-level provenance, moderation status, and review trace are not nice-to-have; they are table stakes for serious AI media workflows. |

### CEO Verdict

The plan is strategically correct if it is framed as:

```text
One sentence starts production.
Every generated asset is visible.
Every failed or risky asset is reviewable.
Every final video is traceable.
No stage advances in the dark.
```

The wrong framing is "integrate dy_auto with Pixelle-Video." That is too technical and will lead to plumbing work without a crisp product promise. The right framing is "dy_auto becomes the transparent control plane for automated AI video production."

### Premise Challenge

| Premise | CEO verdict | Tightening required |
|---|---|---|
| Users eventually want one sentence to produce content. | Correct. | The one sentence starts an orchestrated run only after model config, style lock, Pixelle health, and review gates are ready. |
| dy_auto should orchestrate and Pixelle should execute. | Correct. | Pixelle must not become a second source of model config, production state, or review truth. |
| Stage gates are needed before video and composition. | Correct. | Gates must be latest-version-aware; old approved assets cannot unblock a later stage. |
| AI review first, human review for exceptions. | Correct. | Audit unavailable, malformed, low confidence, or missing model config all become `needs_human`. |
| First implementation should be a vertical slice. | Correct. | The v1 launch wedge should be image stage plus review plus regeneration before video/compose. |
| Existing pipeline can stay compatible. | Correct. | Compatibility should delegate to staged orchestration when `episode_id` exists, not keep growing the legacy path. |

### Scope Decisions

Accepted as core scope:

- Staged Pixelle APIs for image, video segment, and composition.
- dy_auto-owned production state, assets, review records, model traces, and final video library.
- AI video review center as a dedicated exception queue.
- Single-item regeneration with version history.
- Runtime model config delivered from dy_auto to Pixelle.
- Backward-compatible `/api/pipeline/start` behavior.

Strategically mandatory additions before implementation:

- Add Phase 0: trust and contracts. This includes secret redaction, Pixelle file path safety, Pixelle API key enforcement for stage endpoints, audit failure semantics, and current pipeline route compatibility.
- Add a v1 launch wedge: storyboard -> image stage -> AI/human image review -> single-image regeneration. Do not start by building all stages equally.
- Add an acceptance metric: a mocked local run can reach "image assets reviewed" in under 5 minutes with no paid provider.
- Add a new ADR after approval: "dy_auto staged video production supersedes sync polling as the primary AI video orchestration path."

Explicitly not in scope:

| Deferred item | Reason |
|---|---|
| Douyin publishing | The product promise ends at reviewed final video. |
| Generic review center | It would blur the first wedge and slow implementation. |
| Advanced fallback/cost budgets | Valuable after the stage model is proven. |
| Multi-user reviewer permissions | Not required for the first controlled local workflow. |
| Formal Content Credentials export | Good future direction, but v1 can start with internal model/review trace. |

### Dream State Delta

```text
CURRENT
  A user can start a Pixelle-backed video run, but the middle is mostly opaque.
  Failures are hard to distinguish from slow generation.

THIS PLAN AFTER CEO TIGHTENING
  A user starts production from a series.
  dy_auto shows every stage, asset, model trace, audit result, blocker, and retry.
  Pixelle does execution work but does not own business truth.

12-MONTH IDEAL
  dy_auto is a video production control plane:
    - one-sentence campaign creation
    - series/character/style continuity
    - provider-agnostic model routing
    - asset provenance and moderation trace
    - review queues and recovery
    - final video library and publishing handoff
```

### Strategy Diagram

```text
Product promise
  "One sentence to reviewed video, no black box"
        |
        v
Trust primitives
  style lock + model config + asset versions + audit records
        |
        v
Execution boundary
  dy_auto state machine -> Pixelle stage API -> dy_auto review gate
        |
        v
Launch wedge
  image generation -> image review -> single-image regeneration
        |
        v
Expansion
  video segment review -> composition -> video library -> publishing later
```

### Architecture Review

The architecture is directionally strong because it restores ownership boundaries:

- dy_auto owns business intent, state, review, model config, and assets.
- Pixelle owns media execution and prompt/template/render internals.
- The HTTP boundary makes state and failure explicit.

CEO-level concern: stage APIs can accidentally duplicate Pixelle's existing pipeline. The implementation plan must say that Pixelle stage endpoints wrap existing `FrameProcessor`, render services, and composition services wherever possible. If new stage code bypasses those internals, this becomes a second production system.

### Error And Rescue Registry

| Codepath | Failure | Rescue action | User sees | Critical? |
|---|---|---|---|---|
| Start production | Style not locked | Block start and link to style lock | "Style lock required before automated production" | No |
| Start production | Model scene missing | Block start and link to model config | Missing scene/provider/model repair text | Yes |
| Start production | Pixelle unavailable | Create no stage task; preserve draft/run state | Pixelle offline with retry | Yes |
| Image batch | Partial frame failure | Save successes, mark failed frame, keep batch reviewable | Failed frame card with regenerate action | Yes |
| Image audit | Audit timeout/error/malformed response | Mark asset `needs_human` | Human review item with audit failure reason | Yes |
| Human approve | Asset version stale | Reject action and reload latest asset | "A newer version exists" | Yes |
| Regenerate | New generation fails | Keep previous version and failed attempt | Old asset remains; retry available | No |
| Video stage | Missing latest approved image | Block stage transition | Missing frame ids | Yes |
| Compose | Segment missing or stale | Block compose | Missing/stale segment list | Yes |
| Final writeback | GeneratedVideo save fails | Keep run in compose-completed/writeback-failed state | Retry final writeback | Yes |
| Config bridge | Secret appears in read API/logs | Recursive redaction and tests | No secret visible | Critical |
| File serving | Path traversal attempt | Reject request | 403/404 | Critical |

### Failure Modes Registry

| Codepath | Failure mode | Rescued? | Test? | User sees? | Logged? | Gap |
|---|---|---|---|---|---|---|
| Runtime model delivery | API key persisted to Pixelle config or returned by config API | Planned | Required | Silent if missed | Required | Critical until implemented |
| Review gate | Audit service fails but asset auto-approves | Planned | Required | Wrongly advances | Required | Critical until implemented |
| Versioning | Old approved asset unlocks next stage after regeneration | Planned | Required | Silent bad continuity | Required | Critical until implemented |
| Stage task | Pixelle restarts and loses in-memory task | Partially | Required | Retryable stage failure | Required | Needs explicit reconciliation |
| UI | Review blocked run has no deep link to item | Planned | Frontend required | User sees blocked but cannot fix fast | Optional | Product trust gap |
| Pipeline compatibility | Frontend starts pipeline without director plan and backend rejects | Known | Required | Start fails | Logged today | Must fix Phase 0 |
| Deployment | New tables deploy after code path uses them | Not yet | Migration test required | 500 errors | Required | Rollout gap |
| Performance | Long stage poll blocks request worker | Planned | Required | Slow/hung UI | Required | Must move to background/polling service |

### Data Flow With Shadow Paths

```text
happy path
  Episode.storyboard_json
    -> VideoProductionRun
    -> Pixelle image stage
    -> VideoProductionAsset(image v1)
    -> AI audit approved
    -> image gate passed

nil input
  no storyboard -> block run creation -> repair: auto-plan episode

empty input
  storyboard has zero frames -> block run creation -> repair: regenerate storyboard

upstream error
  Pixelle timeout -> run stage failed/retryable -> no asset loss

unsafe output
  audit error/low confidence -> asset needs_human -> review center
```

### Deployment Sequence

```text
1. Add migrations for production run/asset/review tables.
2. Add security fixes: redaction, Pixelle file path guard, API key enforcement.
3. Add backend state machine and mocked Pixelle stage client.
4. Add `/api/pipeline/start` compatibility delegation.
5. Add review center behind route/navigation flag or v1 hidden nav if needed.
6. Add Pixelle stage APIs wrapping existing execution internals.
7. Enable image-stage vertical slice.
8. Add video segment and compose stages after image slice passes mocked E2E.
```

Rollback flow:

```text
if staged production fails in rollout
  -> disable new review-center entry point
  -> keep new tables intact
  -> old video studio and Pixelle proxy remain available
  -> failed staged runs stay inspectable
  -> fix and resume/retry; do not delete asset history
```

### Observability Requirements

Day-one logs and metrics are part of scope:

- Every run has `run_id`, `series_id`, `episode_id`, `stage`, and `stage_task_id` in logs.
- Every asset action has `asset_id`, `frame_id`, `asset_type`, `version`, and actor/reviewer source.
- Metrics: stage duration, provider error rate, audit pass/fail/needs-human rate, regeneration count, stuck runs by stage, review queue age.
- Review center should expose stale/offline states without requiring developers to inspect logs.
- A runbook should exist for: Pixelle offline, audit provider unavailable, model config missing, stuck stage task, failed final writeback.

### CEO Section Review Summary

| Section | Issues | CEO decision |
|---|---:|---|
| Architecture | 1 | Keep architecture, require reuse of Pixelle internals. |
| Error/rescue | 5 | Add explicit rescue/user-visible behavior to implementation plan. |
| Security | 3 critical | Phase 0 security gate before staged runtime credentials. |
| Data/UX edge cases | 4 | Latest-version invariant and deep links are mandatory. |
| Code quality | 2 | New orchestration service/router, not a larger `pipeline.py`. |
| Tests | 6 gaps | Mocked local vertical slice becomes the acceptance gate. |
| Performance | 2 | No long blocking request polling for staged flow. |
| Observability | 5 gaps | Add structured logs, metrics, runbook fields. |
| Deployment | 4 risks | Migrations/security first, image slice second. |
| Long-term | 2 | New ADR and avoid second Pixelle pipeline. |
| Design/UX | 0 new | `/plan-design-review` already tightened the UI section. |

### Scope Expansion Opportunities Considered

| Opportunity | Decision | Rationale |
|---|---|---|
| Formal Content Credentials export for final videos | Defer | Useful for enterprise provenance later; internal trace is enough for v1. |
| Reviewer assignment/permissions | Defer | Adds workflow complexity before single-user review is proven. |
| Cost budget and provider fallback policies | Defer | Needs real usage data after staged pipeline exists. |
| Provider benchmark dashboard | Defer | Valuable later, but not needed to prove dy_auto/Pixelle control boundary. |

### CEO Completion Summary

```text
+====================================================================+
|              CEO PLAN REVIEW - COMPLETION SUMMARY                   |
+====================================================================+
| Mode selected        | HOLD SCOPE with strategic tightening          |
| System Audit         | dirty workspace, one stash, ADRs need update   |
| Step 0               | right problem, sharper product promise needed  |
| Section 1  (Arch)    | 1 major issue: avoid duplicate Pixelle pipeline|
| Section 2  (Errors)  | 11 error paths mapped, 6 critical gaps         |
| Section 3  (Security)| 3 critical issues carried into Phase 0         |
| Section 4  (Data/UX) | 4 edge cases: stale/latest/deep-link/offline   |
| Section 5  (Quality) | 2 issues: service split and provider adapter   |
| Section 6  (Tests)   | mocked vertical slice required                 |
| Section 7  (Perf)    | background orchestration required              |
| Section 8  (Observ)  | logs, metrics, queue age, runbooks required    |
| Section 9  (Deploy)  | migrations/security before feature enablement  |
| Section 10 (Future)  | reversibility 4/5 if old pipeline remains      |
| Section 11 (Design)  | already covered by /plan-design-review         |
+--------------------------------------------------------------------+
| NOT in scope         | written                                       |
| What already exists  | written in autoplan and design review         |
| Dream state delta    | written                                       |
| Error/rescue registry| 11 rows, 6 critical until implemented         |
| Failure modes        | 8 rows, 4 critical until implemented          |
| Scope proposals      | 4 considered, 0 accepted, 4 deferred          |
| Outside voice        | reused prior Codex CLI review from autoplan   |
| Diagrams produced    | strategy, data flow, deployment, rollback     |
| Unresolved decisions | none blocking implementation plan             |
+====================================================================+
```

Final CEO verdict: approve the plan for implementation planning only after the Phase 0 trust/security/contracts gate is explicitly included. This should not proceed as "build all the Pixelle integration"; it should proceed as a controlled launch wedge that proves transparent staged production with image generation, audit, human review, and single-item regeneration.

## /plan-eng-review Report

Review captured on 2026-05-25 for the dy_auto + Pixelle-Video staged production plan. This standalone engineering review uses the current repo state, previous ADRs, existing tests, the Pixelle-Video codebase at `D:\devWorkspace\Pixelle-Video`, and the prior `/autoplan`, `/plan-design-review`, and `/plan-ceo-review` sections in this document.

### Engineering Verdict

Status: `DONE_WITH_CONCERNS`.

The plan is feasible, but it is not implementation-ready as a full stage pipeline. Treat the next implementation as a constrained launch wedge:

```text
Phase 0: trust, security, contracts, current broken route compatibility
  -> Phase 1: storyboard -> image stage -> AI audit -> human review exception queue
  -> Phase 2: single-image regeneration with latest-version invariant
  -> Phase 3: video segment stage
  -> Phase 4: composition and final video library writeback
```

Do not start by building images, video segments, composition, review center, and provider routing in one pass. The current code already has enough drift between tests, frontend API clients, and backend routes that a big-bang implementation would create a second opaque pipeline instead of removing opacity.

### Step 0: Scope Challenge

#### What Already Exists

| Existing code or flow | Evidence | Reuse decision |
|---|---|---|
| Series style lock storage | `server/app/db_models.py:521`, `server/app/db_models.py:532`, `server/app/routers/series.py:496` | Reuse `Series.story_bible_json.style_lock`; do not add a new style-lock table. |
| Episode storyboard storage | `server/app/db_models.py:557`, `server/app/db_models.py:565`, `server/app/routers/director.py:184` | Reuse `Episode.storyboard_json` as the source of frame intent. |
| Embedded expert team context | `server/app/services/video_agency_team.py:1`, `server/app/routers/director.py:138` | Reuse as prompt/review context; do not build a second agent-team registry for v1. |
| AI model configuration | `server/app/db_models.py:641`, `server/app/services/model_registry.py` | Reuse as dy_auto authority; add a runtime adapter for Pixelle payloads. |
| Pixelle proxy and client | `server/app/routers/pixelle.py:18`, `server/app/services/pixelle_client.py:51` | Reuse transport and settings lookup; do not copy raw HTTP logic into every stage. |
| Legacy pipeline run and video output | `server/app/db_models.py:463`, `server/app/db_models.py:579`, `server/app/routers/pipeline.py:72` | Preserve compatibility, but delegate staged episode runs to the new service. |
| AI image audit route | `server/app/routers/audit.py:119` | Reuse call shape where possible, but change gate semantics before auto-advance. |
| Pixelle execution internals | Pixelle `FrameProcessor`, media services, renderers, task manager | Stage APIs must wrap existing execution internals, not fork a new media pipeline. |

#### Minimum Change Set

The minimum valuable version is not "full dy_auto + Pixelle integration." It is:

1. Fix current broken pipeline contract: `SeriesDetailPage.vue` saves a storyboard then calls `startPipeline` without `director_plan`, while backend still rejects that with `director_plan is required`.
2. Add explicit dy_auto production state tables for run, asset, and review records.
3. Add a Pixelle image-stage endpoint or adapter that can produce per-frame image assets.
4. Persist returned assets in dy_auto and run audit.
5. Route audit failure, low confidence, malformed response, or missing audit config to `needs_human`.
6. Show blocked assets in `/ai-video-review`.
7. Support single-image regeneration and enforce "latest approved version only" before any next stage.

Everything else can follow after this slice passes mocked local E2E.

#### Complexity Check

This plan necessarily touches more than 8 files and introduces more than 2 new services/classes. That is a smell only if the work is attempted as one PR. It is acceptable if split into Phase 0 plus the image-stage wedge.

Opinionated decision: reduce first implementation scope to Phase 0 + image-stage wedge. Keep video segment and compose contracts in the document, but do not implement them until image review and regeneration work end to end.

#### Search Check

| Pattern | Finding | Recommendation |
|---|---|---|
| FastAPI long-running work | FastAPI `BackgroundTasks` is useful for response-after side effects, but its own docs recommend bigger tools like Celery for heavy work that does not need the same process. | [Layer 1] For v1 local development, use a DB-backed in-process orchestrator that returns immediately and is restart-aware enough to mark stale runs retryable. Do not hold HTTP requests open. If this later runs multi-worker/staging, move orchestration to Celery/RQ/Arq. |
| SQLAlchemy version safety | SQLAlchemy supports `version_id_col` for optimistic stale-row detection during ORM flush. | [Layer 1] Add version or latest-token guards on `VideoProductionAsset` review/regeneration writes so old approvals cannot unlock later stages. |
| Test dependency override | Existing server tests already use pytest/FastAPI TestClient style. | [Layer 1] Keep using existing pytest fixtures and monkeypatching. Add contract tests rather than introducing a new test stack. |

#### TODOs Cross-Reference

No `TODOS.md` exists in the repo. Do not create one just for this review. The concrete deferred items are recorded below under "TODO Candidates".

### Architecture Review

1. `[P0] (confidence: 10/10) server/app/routers/pipeline.py:78 - Backend still rejects missing director_plan, while web/src/views/SeriesDetailPage.vue:167-168 intentionally saves an auto-plan then starts the pipeline without passing it.`

   Decision: fix this in Phase 0 before adding new staged APIs. `POST /api/pipeline/start` should load `Episode.storyboard_json` when `episode_id` exists and `director_plan` is absent, then either delegate to staged orchestration or preserve the legacy path for explicit director plans.

2. `[P0] (confidence: 9/10) server/app/routers/pixelle.py:56-68 and server/app/routers/pixelle.py:80-100 - Pixelle config display only redacts llm/comfyui keys, while _serialize_ai_models decrypts model keys into ai_models.scenes.`

   Decision: Phase 0 must include recursive secret redaction and a rule that runtime model credentials are transient. If the disk config bridge remains, it must never expose `ai_models.*.api_key` through `GET /api/pixelle/config`, logs, or task metadata.

3. `[P0] (confidence: 9/10) D:\devWorkspace\Pixelle-Video\api\middleware.py:8-14 - Pixelle allows every request when PIXELLE_API_KEY is unset.`

   Decision: stage endpoints that carry runtime credentials must require auth even if legacy endpoints stay dev-open. A stage API without an API key is not acceptable because dy_auto will send provider secrets.

4. `[P1] (confidence: 9/10) D:\devWorkspace\Pixelle-Video\api\routers\__init__.py:17-36 and D:\devWorkspace\Pixelle-Video\api\tasks\models.py:32-34 - Pixelle has no /api/stages router and only TaskType.VIDEO_GENERATION.`

   Decision: add explicit stage task types: `image_batch`, `video_batch`, `compose`. The status payload must include `external_run_id`, `stage`, `frame_id` or asset mapping, `progress`, `assets`, and structured errors.

5. `[P1] (confidence: 8/10) D:\devWorkspace\Pixelle-Video\pixelle_video\services\frame_processor.py:241-317 and seedance_render.py:48 - Provider/model routing is split between workflow lookup, provider names, and hardcoded Seedance/Kling IDs.`

   Decision: put dy_auto-to-Pixelle provider translation in one adapter. Do not branch per endpoint. Tests must prove `seedance` maps to Pixelle's current `volcengine`/Seedance internals and that runtime model id overrides are honored.

6. `[P1] (confidence: 8/10) planned VideoProductionAsset model - The plan says preserve versions, but does not yet define latest-version invariants at the database/service boundary.`

   Decision: model assets as immutable versions plus a computed/latest flag or unique active pointer. The transition to video stage must query latest approved image per frame, never "any approved image for this frame."

7. `[P1] (confidence: 8/10) server/app/routers/pipeline.py:40-68 - Current start route submits and polls Pixelle inside the request path for up to 1800 seconds.`

   Decision: staged production must return a `run_id` immediately and advance through a background orchestrator. HTTP request threads must not own video production lifecycle.

### Code Quality Review

1. `[P0] (confidence: 10/10) server/tests/test_series_style_lock_pipeline.py:173 - Existing test expects pipeline.SessionLocal and _run_all_layers, but current pipeline.py exposes neither.`

   Evidence: `pytest tests/test_series_style_lock_pipeline.py -q` from `server/` produced `2 passed, 1 failed`; failure is `AttributeError: module app.routers.pipeline has no attribute SessionLocal`.

   Decision: do not paper over the test. Either restore a background `_run_all_layers` compatibility path or replace the test with the new staged orchestrator contract. The behavioral intent is still correct: saved storyboard should drive generation and persistence.

2. `[P1] (confidence: 8/10) server/app/routers/audit.py:26-32 and server/app/routers/audit.py:101-115 - Audit returns pass on missing API key or unparsable model JSON.`

   Decision: introduce gate status separate from old boolean `pass_fail`: `approved`, `rejected`, `needs_human`, `error`. Legacy `AuditReport.pass_fail` can stay for old screens, but staged review logic must not use it alone.

3. `[P1] (confidence: 8/10) planned video_production router/service - If orchestration logic is placed inside pipeline.py, it will mix legacy L0-L5 compatibility, stage state machine, Pixelle client, audit gates, and review endpoints.`

   Decision: create `video_production_service.py` and a thin `video_production.py` router. `pipeline.py` stays compatibility glue and delegates when `episode_id` + saved storyboard are present.

4. `[P1] (confidence: 8/10) planned runtime model config - The same model payload will be needed by dy_auto unit tests, Pixelle API tests, and provider adapters.`

   Decision: define one Pydantic schema/DTO for `RuntimeModelConfig` and keep a shared JSON contract fixture in both repos. This prevents drift between dy_auto scene names and Pixelle provider names.

5. `[P2] (confidence: 7/10) planned review center APIs - The plan lists routes but not pagination/filter contracts.`

   Decision: define `GET /api/video-production/review-items` with stable filters: `run_id`, `series_id`, `episode_id`, `asset_id`, `stage`, `status`, `page`, `page_size`. The UI must not derive review queues from raw `layers_json`.

### Test Review

Current detected test stack:

| Area | Framework | Evidence |
|---|---|---|
| dy_auto backend | pytest | `server/pytest.ini`, `server/tests/*` |
| dy_auto frontend | Vitest + Vue Test Utils | `web/package.json`, `web/vitest.config.js`, `web/src/__tests__/*` |
| Pixelle backend | pytest | `D:\devWorkspace\Pixelle-Video\pyproject.toml`, `D:\devWorkspace\Pixelle-Video\tests/*` |

Targeted test run:

```text
cd server
pytest tests/test_series_style_lock_pipeline.py -q

Result: 2 passed, 1 failed.
Failure: test_pipeline_uses_saved_storyboard_and_persists_episode_and_video
Reason: pipeline.py has no SessionLocal, so the existing saved-storyboard pipeline contract is already broken.
```

#### Coverage Diagram

```text
CODE PATHS                                                     USER FLOWS
[+] Series style lock                                          [+] One sentence starts an episode
  +-- [GOOD] POST /series/{id}/style-lock tested                 +-- [PARTIAL] style lock + auto-plan exist
  +-- [GAP] reference generation provider failure variants        +-- [BROKEN] startPipeline omits director_plan, backend rejects
  +-- [GAP] missing reference asset stays visible after relock

[+] Director auto-plan                                          [+] Review blocked image
  +-- [GOOD] locked references injected into frames               +-- [GAP] user opens /ai-video-review by run_id
  +-- [GAP] malformed LLM frame shape edge cases                  +-- [GAP] preview load failure has visible recovery
  +-- [GAP] unknown character_id/scene_id rejected or repaired    +-- [GAP] approve latest asset re-evaluates gate

[!] Pipeline compatibility                                      [+] Single-image regeneration
  +-- [FAILING] saved storyboard -> generation                    +-- [GAP] old approved image cannot unblock video
  +-- [GAP] episode/video writeback after staged run              +-- [GAP] regenerated version rail shows prior decisions
  +-- [GAP] legacy explicit director_plan still works

[ ] VideoProductionRun state machine                            [+] Pixelle offline or slow
  +-- [GAP] create run -> image_batch_running                     +-- [GAP] run stays inspectable and retryable
  +-- [GAP] partial batch success                                 +-- [GAP] blocked UI explains provider/model/audit cause
  +-- [GAP] failed stage retry idempotency

[ ] VideoProductionAsset versions
  +-- [GAP] immutable version creation
  +-- [GAP] latest approved version invariant
  +-- [GAP] stale approval conflict

[ ] VideoReviewRecord gates
  +-- [GAP] AI approved advances
  +-- [GAP] AI low confidence -> needs_human
  +-- [GAP] AI timeout/error/malformed -> needs_human
  +-- [GAP] human approve/reject/regenerate audit trail

[ ] Pixelle stage APIs
  +-- [GAP] POST /api/stages/images/batch
  +-- [GAP] GET /api/stages/tasks/{id}
  +-- [GAP] auth required when runtime credentials are present
  +-- [GAP] file endpoint traversal regression

[ ] Runtime model config adapter
  +-- [GAP] dy_auto scene -> Pixelle provider/model mapping
  +-- [GAP] secret redaction in config response/log/task metadata
  +-- [GAP] Seedance/Kling hardcoded model override prevention

COVERAGE: 4/31 paths currently covered, 1 covered path failing.
QUALITY: good behavior tests exist for style lock and auto-plan; the production pipeline contract has no passing implementation test.
E2E REQUIRED: mocked local image-stage flow, review-center blocked-item flow, single-image regeneration flow.
EVAL REQUIRED: storyboard prompt quality and audit prompt/status quality.
```

#### Required Test Additions

| Priority | Test file | Type | Requirement |
|---|---|---|---|
| CRITICAL | `server/tests/test_video_production_state_machine.py` | Backend unit | Run can only advance from `image_review_pending` to `image_approved` when every required latest image asset is approved. |
| CRITICAL | `server/tests/test_pipeline_saved_storyboard_compat.py` | Backend regression | `POST /api/pipeline/start` with `episode_id` and no `director_plan` loads `Episode.storyboard_json` or delegates to staged orchestration. |
| CRITICAL | `server/tests/test_pixelle_config_security.py` | Backend security | `GET /api/pixelle/config` redacts nested `ai_models.scenes.*.api_key`. |
| CRITICAL | Pixelle `tests/test_stage_api_auth.py` | Pixelle security | `/api/stages/*` rejects requests carrying runtime credentials when API key auth is missing or wrong. |
| P1 | Pixelle `tests/test_stage_images_api.py` | Pixelle API | Batch image stage returns per-frame assets, structured errors, and task status. |
| P1 | `server/tests/test_runtime_model_config_adapter.py` | Backend unit | dy_auto scene/provider/model config maps to Pixelle's internal provider/model identifiers without duplicated branching. |
| P1 | `server/tests/test_video_review_records.py` | Backend unit | AI audit pass/fail/timeout/malformed response writes correct `VideoReviewRecord` status. |
| P1 | `server/tests/test_single_asset_regeneration.py` | Backend unit | Regeneration creates a new asset version, preserves previous review records, and blocks next stage until latest version is approved. |
| P1 | `web/src/__tests__/ai-video-review-page.test.js` | Frontend unit | Review queue shows loading, empty, blocked, stale-version, and Pixelle-offline states. |
| P1 | `web/src/__tests__/series-detail-video-production.test.js` | Frontend unit | Episode detail starts auto-plan/staged run and deep-links to review center when blocked. |
| P1 | `web/src/__tests__/pipeline-monitor-review-handoff.test.js` | Frontend unit | Pipeline monitor remains execution-only and links to exact review item when a run needs human action. |
| P1 | `server/tests/test_video_production_mocked_e2e.py` | Backend integration | Storyboard -> mocked Pixelle image asset -> AI audit -> human exception -> approve -> run reaches image-approved. |
| P2 | `server/tests/evals/test_storyboard_quality.py` | LLM eval | Auto-plan output keeps locked IDs, reference URLs, duration target, and continuity notes. |
| P2 | `server/tests/evals/test_audit_gate_quality.py` | LLM eval | Audit prompt returns parseable statuses and routes uncertainty to `needs_human`. |

### Performance Review

1. `[P1] (confidence: 9/10) server/app/routers/pipeline.py:18-19 and server/app/routers/pipeline.py:54-68 - Current Pixelle polling can occupy the request path for up to 30 minutes.`

   Decision: staged orchestration must return immediately and advance asynchronously. For local v1, a DB-backed in-process worker is acceptable. For staging/multi-worker, graduate to a real queue.

2. `[P1] (confidence: 8/10) planned review center list - Without pagination and indexes, asset/review lists will become slow once episodes generate many frames and versions.`

   Decision: add indexes on `VideoProductionRun(series_id, episode_id, status)`, `VideoProductionAsset(run_id, stage, frame_id, status, version)`, and `VideoReviewRecord(asset_id, created_at)`. Review list APIs must page and filter.

3. `[P1] (confidence: 8/10) planned asset copy/register step - Copying Pixelle media synchronously inside a request can block UI actions and retry badly on large videos.`

   Decision: copy/register media in the orchestrator, store `source_url`, `storage_url`, `size_bytes`, `checksum`, and `copy_status`, then show partial asset state in the review center.

4. `[P2] (confidence: 7/10) planned stage polling - Large batches can hammer Pixelle if every frame/stage polls independently.`

   Decision: poll per stage task with backoff and jitter. Add provider/run concurrency caps before enabling video batches.

### Failure Modes

| Codepath | Production failure | Test coverage required | Error handling required | User-visible behavior |
|---|---|---|---|---|
| Pipeline compatibility start | Saved storyboard missing or empty | Regression test | 400 with repair instruction | "Generate storyboard first" |
| Runtime model delivery | API key leaked in config response or Pixelle logs | Security test | Recursive redaction and log-safe serializer | No secret visible anywhere |
| Pixelle image stage | Partial frame failure | Mocked integration | Save successes, mark failed frames retryable | Failed frame card with regenerate action |
| AI audit | Provider timeout or malformed JSON | Unit + mocked integration | `needs_human`, never auto-pass | Review item shows audit failure reason |
| Human approval | User approves stale asset after regeneration | Concurrency test | Conflict/stale version guard | "Newer version exists, reload" |
| Next-stage transition | Old approved image unlocks video stage | State-machine test | Latest-approved invariant | Stage remains blocked with frame ids |
| Pixelle restart | In-memory stage task lost | Integration or service test | Mark stale task retryable after timeout | Run remains inspectable, retry available |
| Review center media | Asset URL 404 or Pixelle offline | Frontend unit | Preview error and copy/open URL action | No blank panel |
| File serving | Path traversal through `/api/files` | Pixelle security regression | Resolve path before allow-list check | 403, no file disclosure |

Critical gaps: 4 until implemented and tested: secret leakage, latest-version stage unlock, audit failure auto-pass, and current pipeline start regression.

### NOT In Scope

| Deferred work | Rationale |
|---|---|
| Generic review center for all AI assets | v1 must prove video production gates, not build a universal operations product. |
| Visual timeline editor | The selected workflow is automated staged production and exception review. |
| Douyin publishing loop | Product goal ends at reviewed final video library for this phase. |
| Multi-user reviewer assignment and permissions | Single-user/local review is enough to validate the gate model. |
| Full Pixelle-Video UI redesign | dy_auto should control orchestration; Pixelle remains execution internals. |
| Advanced fallback chains and cost budget dashboard | Valuable after real stage metrics exist. |
| Formal Content Credentials export | Keep internal provenance/model trace now; external credentials can follow later. |
| Real paid-provider E2E as merge gate | Use mocked local E2E first; run paid-provider smoke manually after config is available. |

### TODO Candidates

No `TODOS.md` was created. If a TODO file is introduced later, add these as explicit, contextual entries:

| What | Why | Depends on |
|---|---|---|
| Add a new ADR: staged video production supersedes sync polling for Pixelle-backed episode generation. | Existing ADR-0003 accepted synchronous polling; this plan reverses that for staged production. | Phase 0 architecture decision accepted. |
| Add a formal runtime model config contract fixture shared by dy_auto and Pixelle. | Prevents provider/model naming drift and duplicate mapping logic. | Runtime adapter schema. |
| Add review-center keyboard workflow QA. | Approve/reject/regenerate are high-risk actions and must work without mouse. | Review center UI exists. |
| Add paid-provider smoke checklist for Seedance/Kling/Pixelle staging. | Mocked E2E proves orchestration, not provider reality. | Local mocked E2E passing. |

### Diagrams To Add During Implementation

Add inline ASCII diagrams in these implementation areas:

| File area | Diagram |
|---|---|
| `server/app/db_models.py` near new production models | Run -> Asset versions -> Review records relationship and latest-version invariant. |
| `server/app/services/video_production_service.py` | State transition pipeline from storyboard to image-approved. |
| `server/app/services/pixelle_stage_client.py` | Request/response and retry flow for Pixelle stage tasks. |
| Pixelle stage router/service | Stage task lifecycle and how it wraps existing render internals. |
| Backend state-machine tests | Setup diagram showing frames, asset versions, review statuses, and expected stage result. |

### Worktree Parallelization Strategy

| Step | Modules touched | Depends on |
|---|---|---|
| Phase 0 security fixes | `server/app/routers`, Pixelle `api/middleware.py`, Pixelle `api/routers/files.py` | None |
| dy_auto production models and service | `server/app/db_models.py`, `server/app/services`, migrations/tests | Contract names frozen |
| Pixelle image-stage API | Pixelle `api/routers`, `api/tasks`, `pixelle_video/services` | Runtime model payload contract |
| Frontend review center and status strip | `web/src/views`, `web/src/api`, router/navigation/tests | dy_auto API response shapes |
| Runtime model adapter tests | `server/app/services`, Pixelle tests | Contract names frozen |
| Mocked local E2E | `server/tests`, Pixelle tests | Backend and Pixelle mocked endpoints |

Parallel lanes:

```text
Lane A: Phase 0 security fixes -> secret/path/auth tests
Lane B: dy_auto models/service -> state-machine tests
Lane C: Pixelle image-stage API -> Pixelle stage tests
Lane D: frontend review center -> frontend tests, starts after API shape is frozen
Lane E: mocked local E2E, starts after A + B + C merge
```

Conflict flags:

- Lane A and Lane B both touch `server/app/routers` if Phase 0 includes pipeline compatibility. Coordinate route ownership.
- Lane B and Lane D must share exact API response contracts before frontend work starts.
- Lane C and runtime model adapter work must share the same provider/model fixture.

### Implementation Gate Checklist

Before implementation starts:

1. Freeze DTO names for `VideoProductionRun`, `VideoProductionAsset`, `VideoReviewRecord`, `RuntimeModelConfig`, and Pixelle stage task payloads.
2. Fix or replace the currently failing saved-storyboard pipeline test.
3. Add recursive secret redaction tests before changing Pixelle runtime config delivery.
4. Decide whether Phase 0 uses a local in-process DB-backed orchestrator or introduces a real queue. Recommendation: local orchestrator now, real queue later.
5. Add one mocked local E2E acceptance target: storyboard -> image asset -> audit needs human -> human approve -> run reaches image-approved in under 5 minutes without paid providers.

### Completion Summary

| Section | Result |
|---|---|
| Step 0 Scope Challenge | Scope reduced to Phase 0 + image-stage wedge. |
| Architecture Review | 7 issues found, 3 P0. |
| Code Quality Review | 5 issues found, 1 current failing test. |
| Test Review | Coverage diagram produced, 27 gaps identified. |
| Performance Review | 4 issues found. |
| NOT in scope | Written. |
| What already exists | Written. |
| TODO candidates | 4 proposed inside this document; no `TODOS.md` created. |
| Failure modes | 4 critical gaps flagged. |
| Outside voice | Skipped; prior `/autoplan` already captured Codex outside voice for this same spec. |
| Parallelization | 5 lanes: 3 can start in parallel after contract freeze, frontend/E2E follow. |
| Lake Score | 8/10. Complete security, audit, versioning, and tests are required; paid-provider E2E deferred. |

Final engineering verdict: implementable only as a staged rollout. Phase 0 is mandatory. The first shippable slice is not "full video automation"; it is "transparent image-stage production with AI/human review, single-image regeneration, and no secret leakage."

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | ISSUES_OPEN | Required Phase 0 trust/security/contracts gate and image-stage launch wedge. |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | ISSUES_FOUND | Prior `/autoplan` outside voice found secret, contract, stage API, audit, and route risks. |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | ISSUES_OPEN | 16 issues, 4 critical gaps, 27 test gaps, 1 current failing regression test. |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | CLEAR_WITH_CONSTRAINTS | Review center must be an operational exception queue with explicit blocked/stale/offline states. |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | NOT_RUN | Not required before implementation planning, but useful before ship if setup becomes multi-repo. |

- **CODEX:** Prior outside voice from `/autoplan` agreed the main risks are secrets, stage contracts, audit semantics, and route drift.
- **CROSS-MODEL:** CEO, design, autoplan engineering, and this eng review all agree on Phase 0 plus image-stage wedge before full video/compose.
- **UNRESOLVED:** 0 conversational decisions. Implementation should follow the constrained wedge unless the product owner explicitly expands scope.
- **VERDICT:** CEO + DESIGN reviewed; ENG has open implementation constraints. Ready to write an implementation plan, not ready to code the full integration in one pass.

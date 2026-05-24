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

### Phase 1: Contracts and Configuration Delivery

- Add Pixelle-Video stage API schemas.
- Add dy_auto Pixelle stage client.
- Serialize dy_auto model config into runtime stage payloads.
- Keep implementation minimal or mocked where needed.
- Add secret redaction and API key handling tests.

### Phase 2: Image Stage Loop

- dy_auto calls Pixelle batch image stage.
- Image assets are saved in dy_auto.
- AI image review runs automatically.
- Review center displays image exceptions.
- Single-image regeneration works.

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

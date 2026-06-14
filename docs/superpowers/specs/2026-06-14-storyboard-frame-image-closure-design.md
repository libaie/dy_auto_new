# Storyboard Frame Image Closure Design

## Summary

Add a production-grade storyboard image flow. Each timed storyboard frame can create, review, and approve one image asset that acts as the frame's first/key image for downstream video generation.

This is not a standalone drawing toy. It is the missing bridge between:

```text
story planning -> timed storyboard prompts -> storyboard frame image -> image review -> image-to-video input -> final video
```

The first version should reuse the existing image creation workbench, image asset review gate, and image-to-video promotion bridge. It should not introduce a second image asset system.

## Product Decision

Use the recommended production-first interpretation:

- "分镜图" means a production first/key frame for each storyboard segment.
- It can also be displayed as a storyboard preview, but preview is a secondary benefit.
- Approved storyboard images must be usable by the video production stage.
- Unapproved storyboard images must not silently enter video generation.

## Approaches Considered

| Approach | What It Does | Pros | Cons | Decision |
|---|---|---|---|---|
| A. Manual jump to image workbench | Add links from storyboard frames to `ImageCreationPage` with prefilled prompt/context. | Fastest and low risk. | Not a business loop; users must manually track assets and promotion. | Reject as insufficient. |
| B. Storyboard image tasks | Add per-frame and batch actions that create `ImageCreationTask` records with `destination_role=storyboard_frame`. | Reuses existing model config, task sync, persistence, and review. | Still needs explicit downstream promotion. | Accept. |
| C. Closed production bridge | After approval, link/promote the selected asset back to the storyboard frame and production run so video generation can use it as first-frame input. | Full business closure; prevents video spend before visual approval. | Requires careful review gate and slot conflict handling. | Accept with B. |

Chosen design: **B + C**.

## Existing System Fit

Current reusable pieces:

- `ImageCreationTask` already has `series_id`, `episode_id`, `prompt`, `reference_images_json`, `destination_role`, and `destination_context_json`.
- `ImageCreationAsset` already supports `destination_role`, `destination_context_json`, `downstream_usage_json`, status, review fields, provider trace, checksum, and storage status.
- Allowed destination roles already include `storyboard_frame`, `storyboard_first_frame`, and `batch_story_images`.
- `promote_image_asset_to_video_asset` already enforces approved/review-passed assets before creating a `VideoProductionAsset`.
- `SeriesDetailPage.vue` already renders storyboard frames but only as text.
- `VideoProductionMonitorPage.vue` already starts the image stage from `draft/storyboard_ready`.

Main gaps:

- No API starts image creation tasks directly from storyboard frames.
- No API lists frame-linked image candidates in storyboard order.
- The series detail page does not show per-frame image status or generated images.
- The production image stage does not explicitly prefer an approved storyboard first-frame image when one exists.

## Scope

### In Scope

1. Generate one storyboard image task for a single frame.
2. Generate storyboard image tasks for all missing frames in an episode or run.
3. Store every generated task/asset with:
   - `destination_role = "storyboard_frame"`
   - `destination_context_json.series_id`
   - `destination_context_json.episode_id`
   - `destination_context_json.frame_id`
   - `destination_context_json.time_range`
   - optional `run_id` when created from production monitor
4. Reuse frame `image_prompt`, `negative_prompt`, `reference_urls`, style lock references, and timing metadata.
5. Show frame image status and latest image candidate beside each storyboard frame.
6. Allow review/approval using existing image creation review APIs.
7. Allow approved image assets to be promoted to the active production run/frame.
8. Make video generation prefer approved promoted storyboard images as first-frame/image-to-video source.

### Out Of Scope

- A drawing canvas or manual painting editor.
- A new media asset table.
- A new review center.
- Forced generation for every storyboard before every run.
- Multiple variants per frame as the default UX. Variant generation can reuse `count > 1` later.

## Backend Design

### Service

Add a small storyboard image orchestration service:

```text
storyboard_image_service.py
```

Responsibilities:

- Resolve storyboard frames from an episode or run.
- Build image creation payloads from frame data.
- Generate stable idempotency keys:
  - `storyboard-frame-image:{series_id}:{episode_id}:{frame_id}:{prompt_hash}:{reference_hash}:v1`
- Call existing `create_image_task`.
- List latest frame-linked tasks/assets by frame.
- Promote a reviewed asset through `promote_image_asset_to_video_asset` when `run_id` is present.

It should not talk directly to Pixelle. Existing image creation service owns provider execution.

### API

Add endpoints under an existing router or a focused router. Preferred shape:

```text
POST /api/storyboard-images/episodes/{episode_id}/frames/{frame_id}/tasks
POST /api/storyboard-images/episodes/{episode_id}/tasks:batch
GET  /api/storyboard-images/episodes/{episode_id}
POST /api/storyboard-images/assets/{asset_id}/promote
```

Request options:

- `series_id`
- `run_id` optional
- `force` optional; false should return existing task when idempotency matches
- `count` optional; default 1
- `size` optional; default model/strategy default

Named errors:

| Code | Trigger | Repair |
|---|---|---|
| `STORYBOARD_FRAME_NOT_FOUND` | Frame id is missing from episode/run storyboard. | Regenerate storyboard or refresh page. |
| `STORYBOARD_IMAGE_PROMPT_MISSING` | Frame has no usable image prompt. | Regenerate/refine storyboard prompt. |
| `STORYBOARD_IMAGE_REFERENCES_MISSING` | Real short frame lacks required references. | Regenerate style lock/storyboard references. |
| `STORYBOARD_IMAGE_REVIEW_REQUIRED` | Asset is not approved before promotion. | Complete image review. |
| `STORYBOARD_IMAGE_SLOT_CONFLICT` | Another approved asset already occupies the same run/frame/version. | Use a new version or replace intentionally. |

### Data Contract

The image task payload should use:

```json
{
  "mode": "text_to_image",
  "series_id": "...",
  "episode_id": "...",
  "prompt": "frame.image_prompt",
  "negative_prompt": "frame.negative_prompt",
  "reference_images": [
    {"type": "url", "url": "...", "role": "character"},
    {"type": "url", "url": "...", "role": "scene"}
  ],
  "destination_role": "storyboard_frame",
  "destination_context": {
    "series_id": "...",
    "episode_id": "...",
    "run_id": "...",
    "frame_id": "shot-001",
    "time_range": "0-2秒",
    "source": "storyboard_image"
  }
}
```

The asset payload returned to the frontend must include enough context for rendering and promotion:

- frame id
- time range
- task id/status
- asset id/status/version
- URL/thumbnail
- review gate status
- allowed actions
- downstream promoted flag

## Frontend Design

### Series Detail

Enhance the existing storyboard section:

- Show each frame as a compact row/card with:
  - time range
  - narration
  - image/video prompt
  - generated storyboard image thumbnail when present
  - status badge: `未生成`, `生成中`, `待审`, `已通过`, `已驳回`
  - actions: `生成分镜图`, `重新生成`, `打开图像工作台`
- Add top-level action: `生成缺失分镜图`.

This keeps the series page useful before a production run exists.

### Production Monitor

When a run exists:

- Show storyboard image readiness before `启动图片生成`.
- If frames are missing approved storyboard images, show a non-blocking warning for normal runs.
- For `real_short_e2e`, make missing approved references/images repairable and explicit before costly video generation.
- Add action to promote approved storyboard images into the run.

### Image Creation Page

No major redesign required. It already supports destination roles and promotion. It may need:

- Better prefilled context display for `storyboard_frame`.
- Filter by `destination_role=storyboard_frame`.
- Clear copy that approved assets can become video first frames.

## Video Stage Integration

The downstream rule should be deterministic:

1. If the run already has an approved `VideoProductionAsset` for the frame, use it.
2. Else, if the storyboard frame has a linked approved `ImageCreationAsset` for the same series/episode/frame and it is promoted, use it.
3. Else, use the existing image generation stage flow.

Do not bypass review. Do not use rejected or review-pending images.

For linked production runs, match by `production_segment_id`, `shot_id`, or normalized `frame_id` in that order.

## Error Handling

- Creating tasks is idempotent. Double-clicking `生成分镜图` should not create duplicate provider jobs.
- Batch creation returns per-frame results, not all-or-nothing.
- Provider/task failures stay visible per frame.
- Promotion uses existing stale-version and slot-conflict protections.
- If an image asset belongs to another series/episode/user scope, promotion is blocked.

## Testing Plan

Backend:

- Creating a single storyboard frame image task builds the expected image creation payload.
- Batch creation skips frames with existing matching tasks unless `force=true`.
- Batch creation returns per-frame errors for missing prompt or missing references.
- Listing storyboard images returns frames in storyboard order with latest task/asset status.
- Approving an image asset then promoting it creates a `VideoProductionAsset` for the matching run/frame.
- Review-pending or rejected assets cannot be promoted.
- Existing image creation tests continue to pass.
- Existing video production image stage tests continue to pass.

Frontend:

- Series detail shows per-frame image status and actions.
- `生成分镜图` calls the storyboard image task endpoint with frame id.
- `生成缺失分镜图` shows per-frame progress/results.
- Approved image thumbnail appears beside the correct time range.
- Production monitor warns when storyboard images are missing and allows promotion when approved.
- Mobile layout preserves thumbnail, time range, status, and actions without overlap.

Regression:

- Existing storyboard text display remains available.
- Existing standalone image creation workbench still works.
- Existing image-to-video production can run without storyboard images for legacy/normal runs.
- Real short flow still enforces references and review gates.

## Business Closure Audit

| Requirement | Closure |
|---|---|
| Storyboard text becomes visual evidence | Each frame can create a linked image task from its precise prompt. |
| Images are not orphaned | Assets carry `destination_role=storyboard_frame` and frame context. |
| Quality is reviewed | Existing AI/human review gates remain required. |
| Approved image feeds production | Promotion creates/reuses `VideoProductionAsset`. |
| Video stage avoids hidden bypass | Only approved/promoted assets are eligible. |
| Users can see status | Series detail and production monitor expose frame image state. |
| Provider spend is controlled | Existing image creation cost, idempotency, and task sync apply. |

## Self Review

- No new asset table is proposed.
- No provider-specific code path is proposed.
- The flow reuses existing image creation, review, and promotion boundaries.
- The MVP is focused on one approved image per frame.
- The design avoids making storyboard images mandatory for every legacy run.
- The design gives `real_short_e2e` a stronger preflight path without breaking normal production.
- The implementation scope is large enough for a real business loop but small enough to land without a media-platform rewrite.

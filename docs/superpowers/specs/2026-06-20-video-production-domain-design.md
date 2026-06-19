# Video Production Domain Design

Status: auto-approved.

## Goal

Move the `/api/video-production/*` HTTP surface into
`app.domains.video_production` while preserving the production run control
plane, review queues, worker steps, tree/cost/detail APIs, regeneration, and
stage execution routes.

## Domain Boundary

The new domain owns:

- `app.domains.video_production.video_production_router`
- `video_production_router.py`
- `/api/video-production/*`

The domain keeps the current route-level request models and helpers:

- `CreateRunRequest`
- `StartRunRequest`
- `OneSentenceVideoRequest`
- `ReviewAssetRequest`
- `ImageEditRequest`
- `RegenerateAssetRequest`
- `BulkReviewActionRequest`
- `MockWorkerStepRequest`
- `RealWorkerStepRequest`
- `_run_payload`
- `_asset_payload`
- `_provider_stage_task_payload`

The domain continues to delegate business behavior to shared services such as
`create_one_sentence_video`, `start_image_stage`, `sync_image_stage_results`,
`start_video_stage`, `sync_video_stage_results`, `start_compose_stage`,
`sync_compose_stage_results`, `retry_segment`, and
`apply_bulk_review_action`.

## Compatibility

Keep `app.routers.video_production` as a thin facade that aliases to
`app.domains.video_production.video_production_router` through `sys.modules`.
Existing tests and monkeypatches such as
`app.routers.video_production.edit_image_asset` must resolve to the same module
object while the facade exists.

## Security And Behavior

- Preserve `require_role("admin")` on all routes.
- Preserve route paths, route names, response shapes, and error mappings.
- Preserve background task helpers for one-sentence reference generation and
  real worker steps.
- Preserve review edit pending/error response behavior.
- Preserve service ownership of production state transitions.

## Exit Criteria

- `app.main` imports `video_production_router` from
  `app.domains.video_production`.
- `app.main` includes `video_production_router.router`, not
  `video_production.router`.
- Route/auth snapshots show endpoint modules under
  `app.domains.video_production.video_production_router`.
- `app.routers.video_production` remains a <=20 line facade with no
  `APIRouter`.
- Focused video production API, start-flow, worker, readiness, and mocked E2E
  tests pass.

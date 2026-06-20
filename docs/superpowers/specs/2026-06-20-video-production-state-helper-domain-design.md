# Video Production State Helper Domain Design

## Context

`app.services.video_production_state` owns video production run stage gates,
latest asset lookup, frame id selection, task trace writes, and run gate
recomputation. These helpers are part of the video production business domain,
but they currently live in the generic services folder.

## Approved Approach

Move the implementation to `app.domains.video_production.video_production_state`
and keep `app.services.video_production_state` as a temporary compatibility
facade. Update clean domain callers to use the domain path directly:

- `app.domains.video_production.production_review_service`
- `app.domains.ai_video_series.status_read_model`

Do not edit `video_production_service.py` or `video_production_readiness.py` in
this step because both have unrelated work in progress.

## Boundaries

- Preserve `IMAGE_READY_STATUS`, `VIDEO_READY_STATUS`, and
  `HUMAN_BLOCKING_ASSET_STATUSES`.
- Preserve `storyboard_frame_ids`, `production_segment_frame_ids`,
  `latest_assets_by_frame`, `missing_or_unapproved_frames`,
  `assert_can_start_images`, `assert_can_start_videos`, `assert_can_compose`,
  `record_stage_task`, and `recompute_run_gate` behavior.
- Preserve existing callers that import `app.services.video_production_state`.
- Document the legacy facade in the video production domain README with an
  explicit cleanup gate.

## Verification

- Add a boundary test proving spec and plan coverage for
  `app.domains.video_production.video_production_state`,
  `app.services.video_production_state`, `production_segment_frame_ids`, and
  `recompute_run_gate`.
- Prove the legacy import and domain import resolve to the same module object.
- Prove the legacy file is a thin facade and contains no local
  `def recompute_run_gate`.
- Prove clean domain callers import the state helper from the domain path.
- Run video production state-machine and bulk review behavior tests after
  migration.

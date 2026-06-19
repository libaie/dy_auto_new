# Video Production Tree Service Domain Design

## Context

`app.services.production_tree_service` builds the plan/run tree payload for
`/api/video-production/plans/{plan_id}/tree` and
`/api/video-production/runs/{run_id}/tree`. The router imports it directly, and
the tree payload uses video-production-specific plan, episode, scene, shot,
segment, asset, job, repair, and status semantics.

## Approved Approach

Move the implementation to
`app.domains.video_production.production_tree_service` and keep
`app.services.production_tree_service` as a temporary compatibility facade.
Update `video_production_router.py` to import `get_run_tree` from the domain
path. Since `production_status` already lives in the domain, update the moved
tree service to import status constants from
`app.domains.video_production.production_status`.

## Boundaries

- Preserve `get_run_tree(db, plan_id, page, page_size, status, run_id)` response
  shape and pagination behavior.
- Preserve `_plan_payload`, `_episode_payload`, `_scene_payload`,
  `_shot_payload`, `_segment_payload`, `_asset_payload`, `_job_payload`,
  `_effective_segment_status`, `_jobs_by_segment`, `_latest_assets_by_segment`,
  and `_repair_nodes` behavior.
- Preserve existing callers that import `app.services.production_tree_service`.
- Document the legacy facade in the video production domain README with an
  explicit cleanup gate.

## Verification

- Add a boundary test proving spec and plan coverage for
  `app.domains.video_production.production_tree_service`,
  `app.services.production_tree_service`, `get_run_tree`, and
  `_segment_payload`.
- Prove the legacy import and domain import resolve to the same module object.
- Prove the legacy file is a thin facade and contains no local
  `def get_run_tree`.
- Prove `video_production_router.py` imports `get_run_tree` from the domain
  path.
- Prove the moved tree service imports `production_status` from the domain path.
- Run video production tree API tests after migration.

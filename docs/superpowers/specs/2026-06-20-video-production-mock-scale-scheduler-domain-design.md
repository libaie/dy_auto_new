# Video Production Mock Scale Scheduler Domain Design

## Context

`app.services.mock_scale_scheduler_service` owns provider-free mock scale run
creation and scheduler advancement for long-form video production simulations.
It creates series, episodes, production plans, mock jobs, mock assets, and emits
production audit events. The router uses it for `/api/video-production/*`
mock-scale controls, so the implementation belongs with the video production
domain.

## Approved Approach

Move the implementation to
`app.domains.video_production.mock_scale_scheduler_service` and keep
`app.services.mock_scale_scheduler_service` as a temporary compatibility facade.
Update `video_production_router.py` to import `advance_mock_scheduler` from the
domain path directly. Leave `one_sentence_video_service.py` on the legacy path
for now because it has unrelated work in progress.

Inside the moved module, import already-migrated contracts from domain paths:

- `app.domains.video_production.production_status`
- `app.domains.video_production.video_production_run_types`

Keep queue and observability dependencies on their current paths because those
modules need separate migration decisions.

## Boundaries

- Preserve `create_mock_scale_run` and `advance_mock_scheduler` behavior.
- Preserve mock run constants such as `MOCK_JOB_STAGE`,
  `MOCK_PROVIDER_TASK_ID`, and `MOCK_ASSET_URL_PREFIX`.
- Preserve existing callers that import `app.services.mock_scale_scheduler_service`.
- Document the legacy facade in the video production domain README with an
  explicit cleanup gate.

## Verification

- Add a boundary test proving spec and plan coverage for
  `app.domains.video_production.mock_scale_scheduler_service`,
  `app.services.mock_scale_scheduler_service`, `create_mock_scale_run`, and
  `advance_mock_scheduler`.
- Prove the legacy import and domain import resolve to the same module object.
- Prove the legacy file is a thin facade and contains no local
  `def create_mock_scale_run`.
- Prove `video_production_router.py` imports `advance_mock_scheduler` from the
  domain path.
- Run mock scale scheduler behavior tests after migration.

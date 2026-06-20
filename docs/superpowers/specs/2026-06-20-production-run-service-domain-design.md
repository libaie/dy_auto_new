# Production Run Service Domain Design

## Context

`server/app/services/production_run_service.py` creates linked video production
runs, starts episode production, prepares text artifacts, retimes storyboards,
and emits production observability events. This is video production
orchestration and belongs in the video production domain.

## Decision

Move the implementation to
`app.domains.video_production.production_run_service`. Keep
`app.services.production_run_service` as a compatibility facade while series
routers, video production router, and tests still import the old path.

Most dependencies should import from their domains. The only retained service
dependency in this slice is `app.services.video_production_service`, because it
still owns run creation and image-stage start helpers used by production run
orchestration.

## Scope

- Preserve linked run creation, `start_episode_production`,
  `generate_episode_script_storyboard`, storyboard retiming, and text artifact
  preparation.
- Preserve the current target-duration retiming behavior.
- Remove `production_run_service.py` from the service implementation inventory.
- Add the retained `video_production_service` import to the domain service
  import inventory.
- Register the domain module and legacy facade in the video production README.

## Non-Goals

- Do not migrate `video_production_service.py` in this slice.
- Do not rewrite story planning, script pipeline, text artifact, or image stage
  start behavior.
- Do not remove the legacy service import path until downstream callers move.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/tests/test_one_sentence_video_run_types.py server/tests/test_video_production_cost_safety.py server/tests/test_series_planning_service.py server/tests/test_pipeline_saved_storyboard_compat.py -q
```

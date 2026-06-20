# Production Worker Service Domain Design

## Context

`server/app/services/production_worker_service.py` executes real provider worker
steps for linked video-production runs. It claims jobs, runs deferred agency
stage gates, submits provider stages, persists provider assets, and updates run
status after image, video, and compose jobs. This is video production domain
behavior.

## Decision

Move the implementation to
`app.domains.video_production.production_worker_service`. Keep
`app.services.production_worker_service` as a compatibility facade while the
video production router and tests still import or monkeypatch the old path.

Most dependencies should import from their domains. The only retained service
dependency in this slice is `app.services.video_production_service`, because
that mixed service has not moved yet and still owns stage payload helpers and
asset writeback helpers used by the worker.

## Scope

- Preserve `run_real_worker_step`, `execute_real_job`, `_job_spec`, deferred
  stage-gate handling, provider persistence, and run status updates.
- Preserve the current creative patch gate, text-only image model reference
  sanitization, and deferred gate timeout environment override.
- Remove `production_worker_service.py` from the service implementation
  inventory.
- Add the retained `video_production_service` import to the domain service
  import inventory.
- Register the domain module and legacy facade in the video production README.

## Non-Goals

- Do not migrate `video_production_service.py` in this slice.
- Do not rewrite worker orchestration, provider execution, creative patch gates,
  or stage-review semantics.
- Do not remove the legacy service import path until downstream callers move.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/tests/test_agency_repair_worker.py server/tests/test_video_production_real_worker_step.py server/tests/test_video_production_linked_stage_execution.py server/tests/test_video_production_creative_patch_gate.py -q
```

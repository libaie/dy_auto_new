# Production Queue Service Domain Design

Date: 2026-06-20

## Goal

Move production job queue business logic out of `app.services` and into the
`video_production` domain.

## Design

- Move `server/app/services/production_queue_service.py` to
  `server/app/domains/video_production/production_queue_service.py`.
- Keep `app.services.production_queue_service` as a module alias for existing
  tests, legacy service callers, and compatibility during the migration.
- Update domain modules to import queue helpers directly from
  `app.domains.video_production.production_queue_service`.
- Import production status constants from the domain status module.
- Remove `production_queue_service.py` from the remaining service
  implementation inventory.

## Non-Goals

- Do not migrate `production_worker_service.py`, `production_run_service.py`, or
  `video_production_service.py` in this slice.
- Do not change queue semantics, lease behavior, retry behavior, or job state
  transitions.

## Verification

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/tests/test_production_queue_service.py server/tests/test_agency_backtrack_policy.py server/tests/test_agency_debate_audit.py server/tests/test_provider_stage_executor.py -q
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
```

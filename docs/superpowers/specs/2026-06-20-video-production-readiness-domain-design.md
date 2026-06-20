# Video Production Readiness Domain Design

Date: 2026-06-20

## Goal

Move video production readiness gating logic out of `app.services` and into the
`video_production` domain.

## Design

- Move `server/app/services/video_production_readiness.py` to
  `server/app/domains/video_production/video_production_readiness.py`.
- Update `video_production_router.py` to import the domain readiness module
  directly.
- Keep `app.services.video_production_readiness` as a module alias for existing
  tests and legacy imports.
- Replace already-migrated helper imports with direct
  `app.domains.video_production` imports.
- Remove `video_production_readiness.py` from the remaining service
  implementation inventory.

## Non-Goals

- Do not migrate `production_queue_service.py`, `production_run_service.py`, or
  `production_worker_service.py` in this slice.
- Do not change readiness response shape or route behavior.

## Verification

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/tests/test_video_production_readiness.py server/tests/test_one_sentence_video.py -q
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
```

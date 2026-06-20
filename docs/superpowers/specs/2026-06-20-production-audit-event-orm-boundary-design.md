# Production Audit Event ORM Boundary Design

## Context

`ProductionAuditEvent` is the persistence model for production observability,
but its class body still lives in the monolithic `app.db_models` module.
The `production_observability` domain already owns redacted event writes.

## Decision

Move `ProductionAuditEvent` to `app.db.models.production_observability`.
Keep `app.db_models.ProductionAuditEvent` as a compatibility re-export.
Update the production observability service and AI video series model facade to
use the new model path. Leave wider agency, image, and video production
callers on the compatibility path for later focused slices.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_production_audit_event_orm_boundary.py server/tests/test_production_observability_domain_facade.py server/tests/test_video_production_observability_events.py server/tests/test_ai_video_series_orm_boundary.py -q
```

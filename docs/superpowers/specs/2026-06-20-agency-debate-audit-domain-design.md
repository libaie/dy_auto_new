# Agency Debate Audit Domain Design

Date: 2026-06-20

## Goal

Move agency debate audit business logic out of `app.services` and into the
`agency_operations` domain.

## Design

- Move `server/app/services/agency_debate_audit.py` to
  `server/app/domains/agency_operations/agency_debate_audit.py`.
- Keep `app.services.agency_debate_audit` as a module alias so existing imports
  and tests keep working.
- Replace already-migrated facade imports with direct domain imports for
  scorecard contracts and production status constants.
- Record the remaining dependencies on `agency_orchestrator` and
  `production_queue_service` in the domain-service import inventory until those
  services migrate.

## Non-Goals

- Do not migrate `agency_orchestrator.py` or `production_queue_service.py` in
  this slice.
- Do not change debate audit behavior, repair job creation, or audit payloads.

## Verification

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/tests/test_agency_debate_audit.py -q
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
```

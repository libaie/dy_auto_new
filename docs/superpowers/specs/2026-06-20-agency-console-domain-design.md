# Agency Console Domain Design

## Context

`server/app/services/agency_console.py` builds the read-only agency transparency
payload shown on series detail pages. It summarizes expert invocations,
decision logs, repair status, creative patch status, readiness, quality reports,
and current episode context. That is agency operations read-model behavior.

## Decision

Move the implementation to `app.domains.agency_operations.agency_console`.
Keep `app.services.agency_console` as a compatibility facade while series read
models and tests still import the old path.

The new domain module should import migrated agency helpers from
`app.domains.agency_operations`. It will temporarily keep service imports for
`agency_orchestrator` and `video_agency_team`, because those service modules
have not moved yet.

## Scope

- Preserve `build_agency_console_payload` and all payload fields.
- Preserve the current creative patch summary, creative patch list, style-lock
  trace decision log, and story-planning stage label behavior.
- Remove `agency_console.py` from the service implementation inventory.
- Add retained orchestrator/team imports to the domain service import
  inventory.
- Register the domain module and legacy facade in the agency operations README.

## Non-Goals

- Do not migrate `agency_orchestrator.py` or `video_agency_team.py` in this
  slice.
- Do not change agency console route shapes, authorization, or response fields.
- Do not remove the legacy service import path until downstream callers move.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/tests/test_agency_console.py server/tests/test_agency_invocation_models.py -q
```

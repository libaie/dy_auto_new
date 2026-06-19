# Video Production Cost Service Domain Design

Status: auto-approved.

## Context

`app.services.production_cost_service` owns video production budget checks,
production cost event recording, plan current-cost increments, and budget-based
plan/job blocking. This is video-production-specific write behavior but still
lives in the flat service folder.

## Decision

Move the implementation to
`app.domains.video_production.production_cost_service` and keep
`app.services.production_cost_service` as a thin `sys.modules` compatibility
facade.

Existing tests can continue using the legacy path until they are converted to
direct domain imports.

## Scope

In scope:

- Create `server/app/domains/video_production/production_cost_service.py` with
  the current implementation.
- Replace `server/app/services/production_cost_service.py` with a compatibility
  facade.
- Update `server/app/domains/video_production/README.md` to document cost event
  ownership, facade mapping, and cleanup gates.
- Add focused boundary tests proving old and new imports resolve to the same
  module object.

Out of scope:

- No behavior changes to budget checks, production cost event fields, plan
  current-cost increments, job blocking, plan blocking, or queue interactions.
- No migration of production queue/status helpers in this step.

## Architecture

The domain production cost service owns:

- `assert_budget_available`
- `record_cost_event`
- `pause_plan_for_budget`

The legacy service module imports the domain cost service module, replaces
itself in `sys.modules`, and updates globals so existing imports and monkeypatch
paths keep targeting the same module object.

## Testing

Add `server/tests/test_video_production_cost_service_facade.py` to verify:

- this spec and plan mention
  `app.domains.video_production.production_cost_service`,
  `app.services.production_cost_service`, `assert_budget_available`,
  `record_cost_event`, and `pause_plan_for_budget`;
- the domain production cost service file exists;
- the legacy service file is a thin facade with no copied implementation;
- old and new imports resolve to the same module object and expose identical key
  functions;
- the video production README records cost event ownership, facade mapping, and
  cleanup gate.

Run focused verification:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_cost_service_facade.py server/tests/test_production_cost_service.py -q
```

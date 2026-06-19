# Video Production Cost Summary Service Domain Design

Status: auto-approved.

## Context

`app.services.production_cost_summary_service` builds the video production run
cost payload used by the control-plane API. It summarizes actual cost events,
stage and provider/model breakdowns, and provider cost reservation totals. This
is video-production-specific read behavior but still lives in the flat service
folder.

## Decision

Move the implementation to
`app.domains.video_production.production_cost_summary_service`, update the
video production domain router to import it directly, and keep
`app.services.production_cost_summary_service` as a thin `sys.modules`
compatibility facade.

Existing tests can continue using the legacy path until they are converted to
direct domain imports.

## Scope

In scope:

- Create `server/app/domains/video_production/production_cost_summary_service.py`
  with the current implementation.
- Update the moved helper to import
  `app.domains.video_production.production_state_contract` directly.
- Replace `server/app/services/production_cost_summary_service.py` with a
  compatibility facade.
- Update `server/app/domains/video_production/video_production_router.py` to
  import `get_run_costs` from the domain helper.
- Update `server/app/domains/video_production/README.md` to document cost
  summary ownership, facade mapping, and cleanup gates.
- Add focused boundary tests proving old and new imports resolve to the same
  module object.

Out of scope:

- No behavior changes to actual cost totals, stage/provider grouping,
  reservation totals, unlinked-run fallback payloads, budget status, or unknown
  estimate reasons.
- No migration of provider cost reservation mutation logic in this step.

## Architecture

The domain production cost summary service owns:

- `_ZERO_RESERVATION_COSTS`
- `_ACTIVE_RESERVATION_STATUSES`
- `get_run_costs`

The legacy service module imports the domain cost summary module, replaces
itself in `sys.modules`, and updates globals so existing imports and monkeypatch
paths keep targeting the same module object.

## Testing

Add `server/tests/test_video_production_cost_summary_service_facade.py` to verify:

- this spec and plan mention
  `app.domains.video_production.production_cost_summary_service`,
  `app.services.production_cost_summary_service`, `_ZERO_RESERVATION_COSTS`,
  `_ACTIVE_RESERVATION_STATUSES`, and `get_run_costs`;
- the domain cost summary service file exists;
- the legacy service file is a thin facade with no copied implementation;
- old and new imports resolve to the same module object and expose identical key
  constants/functions;
- the moved implementation imports the domain state contract path directly;
- the video production router imports the domain cost summary helper directly;
- the video production README records cost summary ownership, facade mapping,
  and cleanup gate.

Run focused verification:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_cost_summary_service_facade.py server/tests/test_provider_cost_reservation_service.py -q
```

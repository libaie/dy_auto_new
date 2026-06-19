# Video Production Provider Cost Reservation Service Domain Design

Status: auto-approved.

## Context

`app.services.provider_cost_reservation_service` owns provider cost reservation
state for video production: active reserved totals, budget blocking, reservation
creation, submit/stale/settle/release transitions, expiration, and plan-level
locking. It already depends on video production state constants and repairable
errors, but still lives in the flat service folder.

## Decision

Move the implementation to
`app.domains.video_production.provider_cost_reservation_service` and keep
`app.services.provider_cost_reservation_service` as a thin `sys.modules`
compatibility facade.

Existing provider executor, agency repair/orchestration readers, and tests can
continue using the legacy path until those modules are migrated or intentionally
approved as cross-domain consumers.

## Scope

In scope:

- Create
  `server/app/domains/video_production/provider_cost_reservation_service.py`
  with the current implementation.
- Update the moved helper to import
  `app.domains.video_production.production_errors` and
  `app.domains.video_production.production_state_contract` directly.
- Replace `server/app/services/provider_cost_reservation_service.py` with a
  compatibility facade.
- Update `server/app/domains/video_production/README.md` to document provider
  cost reservation ownership, facade mapping, and cleanup gates.
- Add focused boundary tests proving old and new imports resolve to the same
  module object and expose identical lock dictionaries/functions.

Out of scope:

- No behavior changes to budget checks, lock behavior, reservation lifecycle
  transitions, expiration, plan current cost increments, or repairable error
  payloads.
- No migration of provider executor, agency operations, or agency repair
  consumers in this step.

## Architecture

The domain provider cost reservation service owns:

- `_ACTIVE_RESERVATION_STATUSES`
- `_PLAN_LOCKS`
- `active_reserved_cost`
- `create_cost_reservation`
- `mark_reservation_submitted`
- `mark_reservation_stale_needs_repair`
- `settle_reservation`
- `release_unsubmitted_reservation`
- `expire_unsubmitted_reservations`

The legacy service module imports the domain reservation module, replaces itself
in `sys.modules`, and updates globals so existing imports, monkeypatches, and
module-level lock state keep targeting the same module object.

## Testing

Add
`server/tests/test_video_production_provider_cost_reservation_service_facade.py`
to verify:

- this spec and plan mention
  `app.domains.video_production.provider_cost_reservation_service`,
  `app.services.provider_cost_reservation_service`,
  `_ACTIVE_RESERVATION_STATUSES`, `_PLAN_LOCKS`, `active_reserved_cost`,
  `create_cost_reservation`, `settle_reservation`, and
  `expire_unsubmitted_reservations`;
- the domain provider cost reservation service file exists;
- the legacy service file is a thin facade with no copied implementation;
- old and new imports resolve to the same module object and expose identical key
  lock dictionaries/functions;
- the moved implementation imports the domain production errors and state
  contract paths directly;
- the video production README records provider cost reservation ownership,
  facade mapping, and cleanup gate, including approved cross-domain consumers.

Run focused verification:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_provider_cost_reservation_service_facade.py server/tests/test_provider_cost_reservation_service.py server/tests/test_provider_stage_executor.py -q
```

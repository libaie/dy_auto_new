# Video Production State Contract Domain Design

Status: auto-approved.

## Context

`app.services.production_state_contract` defines provider task statuses, cost
reservation statuses, asset reviewable statuses, and transition validation for
video production. It is a pure domain contract, but still lives in the flat
service folder.

## Decision

Move the implementation to
`app.domains.video_production.production_state_contract` and keep
`app.services.production_state_contract` as a thin `sys.modules` compatibility
facade.

Existing provider, cost, review, and test modules can continue using the legacy
path until their own migrations happen.

## Scope

In scope:

- Create `server/app/domains/video_production/production_state_contract.py` with
  the current implementation.
- Replace `server/app/services/production_state_contract.py` with a
  compatibility facade.
- Update `server/app/domains/video_production/README.md` to document state
  contract ownership, facade mapping, and cleanup gates.
- Add focused boundary tests proving old and new imports resolve to the same
  module object.

Out of scope:

- No behavior changes to status constants, active/terminal sets, asset
  reviewability, or transition validation.
- No cleanup of legacy imports in provider, cost, review, worker, or test
  modules in this step.

## Architecture

The domain state contract owns:

- Provider task status constants and sets.
- Cost reservation status constants.
- `asset_is_reviewable`
- `provider_task_is_active`
- `validate_transition`

The legacy service module imports the domain state contract module, replaces
itself in `sys.modules`, and updates globals so existing imports and monkeypatches
keep targeting the same module object.

## Data Flow

Provider and cost services continue to import the contract through the old path,
but receive the domain-backed module object. Transition and status behavior
stays unchanged.

## Error Handling

This helper does not raise errors. It preserves boolean validation behavior.

## Testing

Add `server/tests/test_video_production_state_contract_facade.py` to verify:

- this spec and plan mention
  `app.domains.video_production.production_state_contract`,
  `app.services.production_state_contract`, `PROVIDER_TASK_RESERVED`,
  `COST_ACTIVE_UNSUBMITTED`, `asset_is_reviewable`,
  `provider_task_is_active`, and `validate_transition`;
- the domain contract file exists;
- the legacy service file is a thin facade with no copied implementation;
- old and new imports resolve to the same module object and expose identical key
  constants/functions;
- the video production README records contract ownership, facade mapping, and
  cleanup gate.

Run focused verification:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_state_contract_facade.py server/tests/test_video_production_boundary_models.py server/tests/test_provider_stage_executor.py server/tests/test_provider_cost_reservation_service.py -q
```

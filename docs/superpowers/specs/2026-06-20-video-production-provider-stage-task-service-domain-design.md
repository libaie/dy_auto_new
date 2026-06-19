# Video Production Provider Stage Task Service Domain Design

Status: auto-approved.

## Context

`app.services.provider_stage_task_service` owns provider stage task request
hashing, idempotency key construction, task reservation, task status updates,
and submit-claim behavior for video production. It already depends on the video
production state contract, which now lives in
`app.domains.video_production.production_state_contract`, but the task service
itself still lives in the flat service folder.

## Decision

Move the implementation to
`app.domains.video_production.provider_stage_task_service` and keep
`app.services.provider_stage_task_service` as a thin `sys.modules`
compatibility facade.

Existing provider executor and tests can continue using the legacy path until
their own domain migrations happen.

## Scope

In scope:

- Create `server/app/domains/video_production/provider_stage_task_service.py`
  with the current task helper implementation.
- Update the moved helper to import
  `app.domains.video_production.production_state_contract` directly.
- Replace `server/app/services/provider_stage_task_service.py` with a
  compatibility facade.
- Update `server/app/domains/video_production/README.md` to document task
  helper ownership, facade mapping, and cleanup gates.
- Add focused boundary tests proving old and new imports resolve to the same
  module object.

Out of scope:

- No behavior changes to request hashing, idempotency keys, task reservation,
  status transitions, database commits, or submit-claim behavior.
- No migration of `provider_stage_executor` or provider throttling tests in this
  step.

## Architecture

The domain provider stage task service owns:

- `request_hash`
- `provider_stage_idempotency_key`
- `get_or_create_stage_task`
- `set_task_status`
- `claim_stage_task_for_submit`

The legacy service module imports the domain task service module, replaces
itself in `sys.modules`, and updates globals so existing imports and monkeypatches
keep targeting the same module object.

## Data Flow

Provider executor code can still import
`app.services.provider_stage_task_service`, but receives the domain-backed
module object. The moved implementation imports transition constants and
validation from `app.domains.video_production.production_state_contract`.

## Error Handling

Existing behavior stays unchanged:

- request hash mismatches for reused idempotency keys raise `ValueError`;
- invalid provider task transitions raise `ValueError`;
- database integrity races are retried by looking up the existing task.

## Testing

Add `server/tests/test_video_production_provider_stage_task_service_facade.py`
to verify:

- this spec and plan mention
  `app.domains.video_production.provider_stage_task_service`,
  `app.services.provider_stage_task_service`, `request_hash`,
  `provider_stage_idempotency_key`, `get_or_create_stage_task`,
  `set_task_status`, and `claim_stage_task_for_submit`;
- the domain task service file exists;
- the legacy service file is a thin facade with no copied implementation;
- old and new imports resolve to the same module object and expose identical key
  functions;
- the moved implementation imports the domain state contract path directly;
- the video production README records task helper ownership, facade mapping, and
  cleanup gate.

Run focused verification:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_provider_stage_task_service_facade.py server/tests/test_provider_stage_executor.py server/tests/test_provider_throttle_and_backoff.py -q
```

# Video Production Action Result Domain Design

Status: auto-approved.

## Context

`app.services.production_action_result` defines the structured success/blocked
result contract used by video production workers, provider stage execution, and
repair execution. It depends on `ProductionErrorCode`, which now lives in the
video production domain, but the action result helper itself still lives in the
flat service folder.

## Decision

Move the implementation to
`app.domains.video_production.production_action_result` and keep
`app.services.production_action_result` as a thin `sys.modules` compatibility
facade.

The moved helper should import `ProductionErrorCode` from the domain error
helper. Existing service modules can keep the legacy action result path until
their own migrations happen.

## Scope

In scope:

- Create `server/app/domains/video_production/production_action_result.py` with
  the current implementation.
- Replace `server/app/services/production_action_result.py` with a
  compatibility facade.
- Update the moved helper to import `ProductionErrorCode` from
  `app.domains.video_production.production_errors`.
- Update `server/app/domains/video_production/README.md` to document action
  result ownership, facade mapping, and cleanup gates.
- Add focused boundary tests proving old and new imports resolve to the same
  module object.

Out of scope:

- No behavior changes to `ProductionActionResult.success`,
  `ProductionActionResult.blocked`, `_serialize_code`, or `to_http_detail`.
- No cleanup of legacy imports in worker/provider/agency services or existing
  tests in this step.

## Architecture

The domain action result helper owns:

- `ProductionActionResult`
- `_serialize_code`

The legacy service module imports the domain helper module, replaces itself in
`sys.modules`, and updates globals so existing imports and monkeypatches keep
targeting the same module object.

## Data Flow

Worker and provider code can continue returning `ProductionActionResult`
instances through the old import path. The class and its `to_http_detail`
serialization are backed by the domain module.

## Error Handling

The helper still serializes success and blocked results to the same HTTP detail
shape, including `code`, `error_code`, repair fields, retryability, affected
IDs, and data.

## Testing

Add `server/tests/test_video_production_action_result_facade.py` to verify:

- this spec and plan mention
  `app.domains.video_production.production_action_result`,
  `app.services.production_action_result`, `ProductionActionResult`, and
  `_serialize_code`;
- the domain helper file exists;
- the legacy helper file is a thin facade with no copied implementation;
- old and new imports resolve to the same module object and expose identical key
  types/functions;
- the moved helper imports domain production errors;
- the video production README records helper ownership, facade mapping, and
  cleanup gate.

Run focused verification:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_action_result_facade.py server/tests/test_video_production_boundary_models.py server/tests/test_provider_stage_executor.py -q
```

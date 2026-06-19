# Video Production Error Helper Domain Design

Status: auto-approved.

## Context

The video production domain owns `/api/video-production/*`, but the router still
imports `ProductionErrorCode`, `ProductionRepairableError`, and `to_http_detail`
from `app.services.production_errors`. That module defines the structured error
contract for video production orchestration and is used by many legacy service
modules that have not moved yet.

## Decision

Move the implementation to `app.domains.video_production.production_errors` and
keep `app.services.production_errors` as a thin `sys.modules` compatibility
facade.

The domain router should import the domain error helper directly. Existing
service modules can keep the legacy path until their own migrations happen.

## Scope

In scope:

- Create `server/app/domains/video_production/production_errors.py` with the
  current implementation.
- Replace `server/app/services/production_errors.py` with a compatibility
  facade.
- Update `server/app/domains/video_production/video_production_router.py` to
  import error types from the domain path.
- Update `server/app/domains/video_production/README.md` to document error
  helper ownership, facade mapping, and cleanup gates.
- Add focused boundary tests proving old and new imports resolve to the same
  module object.

Out of scope:

- No behavior changes to enum values, repairable error fields, HTTP detail
  payload shape, retry flags, affected IDs, or causes.
- No cleanup of legacy imports in production services or tests in this step.

## Architecture

The domain error helper owns:

- `ProductionErrorCode`
- `ProductionRepairableError`
- `to_http_detail`

The legacy service module imports the domain helper module, replaces itself in
`sys.modules`, and updates globals so existing imports and monkeypatches keep
targeting the same module object.

## Data Flow

Domain route handlers catch `ProductionRepairableError` and pass it to
`to_http_detail` exactly as before. Legacy service modules still raise the same
domain-backed error classes through the old import path.

## Error Handling

The migration preserves the error contract exactly. All existing `code` and
`error_code` payload fields remain unchanged.

## Testing

Add `server/tests/test_video_production_error_helper_facade.py` to verify:

- this spec and plan mention
  `app.domains.video_production.production_errors`,
  `app.services.production_errors`, `ProductionErrorCode`,
  `ProductionRepairableError`, and `to_http_detail`;
- the domain helper file exists;
- the legacy helper file is a thin facade with no copied implementation;
- old and new imports resolve to the same module object and expose identical key
  types/functions;
- the domain video production router imports the domain error helper path;
- the video production README records helper ownership, facade mapping, and
  cleanup gate.

Run focused verification:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_error_helper_facade.py server/tests/test_video_production_named_errors.py server/tests/test_video_production_boundary_models.py -q
```

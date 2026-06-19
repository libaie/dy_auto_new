# Video Production Run Types Domain Design

Status: auto-approved.

## Context

`app.services.video_production_run_types` defines the allowed video production
run modes and helper functions used to validate and classify real provider,
mock scale, and legacy episode runs. It is a pure video production domain
contract, but still lives in the flat service folder.

## Decision

Move the implementation to
`app.domains.video_production.video_production_run_types` and keep
`app.services.video_production_run_types` as a thin `sys.modules`
compatibility facade.

Domain-owned video production modules should import the domain path directly.
Existing service modules and tests can keep the legacy path until their own
cleanup gates are satisfied.

## Scope

In scope:

- Create `server/app/domains/video_production/video_production_run_types.py`
  with the current implementation.
- Replace `server/app/services/video_production_run_types.py` with a
  compatibility facade.
- Update `server/app/domains/video_production/video_production_router.py` and
  `server/app/domains/video_production/production_review_service.py` to import
  run type helpers from the domain path.
- Update `server/app/domains/video_production/README.md` to document run type
  ownership, facade mapping, and cleanup gates.
- Add focused boundary tests proving old and new imports resolve to the same
  module object and expose identical constants/functions.

Out of scope:

- No behavior changes to allowed run types, validation fallback, get/set helpers,
  assertion error messages, or real/mock classification.
- No migration of production run service, one sentence video service, worker,
  readiness, or tests in this step.

## Architecture

The domain run type contract owns:

- `REAL_SHORT_E2E`
- `MOCK_SERIES_SCALE`
- `LEGACY_EPISODE_RUN`
- `ALLOWED_RUN_TYPES`
- `REAL_PROVIDER_RUN_TYPES`
- `MOCK_RUN_TYPES`
- `validate_run_type`
- `get_run_type`
- `set_run_type`
- `assert_run_type`
- `is_real_provider_run`
- `is_mock_scale_run`

The legacy service module imports the domain run type module, replaces itself
in `sys.modules`, and updates globals so existing imports and monkeypatch paths
keep targeting the same module object.

## Testing

Add `server/tests/test_video_production_run_types_facade.py` to verify:

- this spec and plan mention
  `app.domains.video_production.video_production_run_types`,
  `app.services.video_production_run_types`, `REAL_SHORT_E2E`,
  `MOCK_SERIES_SCALE`, `LEGACY_EPISODE_RUN`, `validate_run_type`,
  `assert_run_type`, and `is_mock_scale_run`;
- the domain run type file exists;
- the legacy service file is a thin facade with no copied implementation;
- old and new imports resolve to the same module object and expose identical key
  constants/functions;
- video production router and production review helper import the domain run
  type path directly;
- the video production README records run type ownership, facade mapping, and
  cleanup gate.

Run focused verification:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_run_types_facade.py server/tests/test_video_production_run_type.py server/tests/test_production_bulk_review.py -q
```

# Video Production Review Service Domain Design

Status: auto-approved.

## Context

`app.services.production_review_service` owns video production bulk review
rules: supported actions, supported asset types, persisted-asset preconditions,
stale asset skipping, review record creation, and gate recomputation. It is
called by the video production domain router but still lives in the flat service
folder.

## Decision

Move the implementation to
`app.domains.video_production.production_review_service`, update the domain
router to import it directly, and keep
`app.services.production_review_service` as a thin `sys.modules` compatibility
facade.

Existing bulk review tests can continue using the legacy path until they are
converted to direct domain imports.

## Scope

In scope:

- Create `server/app/domains/video_production/production_review_service.py`
  with the current implementation.
- Update the moved helper to import
  `app.domains.video_production.production_state_contract` directly.
- Replace `server/app/services/production_review_service.py` with a
  compatibility facade.
- Update `server/app/domains/video_production/video_production_router.py` to
  import `apply_bulk_review_action` from the domain helper.
- Update `server/app/domains/video_production/README.md` to document review
  helper ownership, facade mapping, and cleanup gates.
- Add focused boundary tests proving old and new imports resolve to the same
  module object.

Out of scope:

- No behavior changes to supported actions, asset type rules, review record
  payloads, stale skipping, gate recomputation, or database commits.
- No migration of `video_production_state` or `video_production_run_types` in
  this step.

## Architecture

The domain production review service owns:

- `SUPPORTED_BULK_REVIEW_ACTIONS`
- `GATED_ASSET_TYPES`
- `SUPPORTED_BULK_ASSET_TYPES`
- `apply_bulk_review_action`

The legacy service module imports the domain review module, replaces itself in
`sys.modules`, and updates globals so existing imports and monkeypatches keep
targeting the same module object.

## Testing

Add `server/tests/test_video_production_review_service_facade.py` to verify:

- this spec and plan mention
  `app.domains.video_production.production_review_service`,
  `app.services.production_review_service`, `SUPPORTED_BULK_REVIEW_ACTIONS`,
  `SUPPORTED_BULK_ASSET_TYPES`, `GATED_ASSET_TYPES`, and
  `apply_bulk_review_action`;
- the domain review service file exists;
- the legacy service file is a thin facade with no copied implementation;
- old and new imports resolve to the same module object and expose identical key
  constants/functions;
- the moved implementation imports the domain state contract path directly;
- the video production router imports the domain review helper directly;
- the video production README records review helper ownership, facade mapping,
  and cleanup gate.

Run focused verification:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_review_service_facade.py server/tests/test_production_bulk_review.py -q
```

# Image Generation Error Helper Domain Design

Status: auto-approved.

## Context

Several image generation domain modules still import
`app.services.image_creation_errors` to build consistent image API error
payloads. The helper is small, image-specific, and shared across moved domain
services. Legacy image creation and storyboard modules still use the old path.

## Decision

Move the implementation to
`app.domains.image_generation.image_creation_errors` and keep
`app.services.image_creation_errors` as a thin `sys.modules` compatibility
facade.

Domain-owned modules should import the domain path directly. Legacy service
modules can keep the old facade until their own migrations happen.

## Scope

In scope:

- Create `server/app/domains/image_generation/image_creation_errors.py` with the
  current implementation.
- Replace `server/app/services/image_creation_errors.py` with a compatibility
  facade.
- Update image generation domain modules to import `image_error` from the domain
  path.
- Update `server/app/domains/image_generation/README.md` to document error
  helper ownership, facade mapping, and cleanup gates.
- Add focused boundary tests proving old and new helper imports resolve to the
  same module object.

Out of scope:

- No behavior changes to HTTP status, detail payload shape, retry flags,
  affected IDs, details, or rescue actions.
- No cleanup of legacy imports in `image_creation_service.py`,
  `storyboard_image_service.py`, existing API tests, or service tests in this
  step.

## Architecture

The domain error helper owns:

- `image_error`

The legacy service module imports the domain error helper module, replaces
itself in `sys.modules`, and updates globals so existing imports and monkeypatches
keep targeting the same module object.

## Data Flow

Domain modules call `image_error` to produce `fastapi.HTTPException` instances
with the same structured detail payload used by existing image APIs.

## Error Handling

Error behavior is unchanged by definition: this migration moves the helper
without changing the payload contract.

## Testing

Add `server/tests/test_image_generation_error_helper_facade.py` to verify:

- this spec and plan mention
  `app.domains.image_generation.image_creation_errors`,
  `app.services.image_creation_errors`, and `image_error`;
- the domain helper file exists;
- the legacy helper file is a thin facade with no copied implementation;
- old and new imports resolve to the same module object and expose identical
  `image_error`;
- domain-owned image generation modules import the domain error helper path;
- the image generation README records error helper ownership, facade mapping,
  and cleanup gate.

Run focused verification:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_error_helper_facade.py server/tests/test_image_creation_errors.py server/tests/test_image_ab_service.py server/tests/test_image_asset_bridge.py server/tests/test_image_selection_preview_service.py server/tests/test_image_production_strategy_service.py server/tests/test_image_production_recommendation_service.py -q
```

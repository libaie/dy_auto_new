# Video Production Asset Storage Guard Domain Design

Status: auto-approved.

## Context

`app.services.asset_storage_guard` owns video production asset persistence:
provider URL validation, local Pixelle output path checks, media magic checks,
checksum calculation, storage status updates, and repairable error mapping. It
is video-production-specific behavior but still lives in the flat service
folder.

## Decision

Move the implementation to
`app.domains.video_production.asset_storage_guard`, update the video production
domain router to import it directly, and keep `app.services.asset_storage_guard`
as a thin `sys.modules` compatibility facade.

Existing worker/service consumers and tests can continue using the legacy path
until those modules are migrated or intentionally retained as service-layer
consumers.

## Scope

In scope:

- Create `server/app/domains/video_production/asset_storage_guard.py` with the
  current implementation.
- Update the moved helper to import
  `app.domains.video_production.production_errors` directly.
- Replace `server/app/services/asset_storage_guard.py` with a compatibility
  facade.
- Update `server/app/domains/video_production/video_production_router.py` to
  import `persist_provider_asset` from the domain helper.
- Update `server/app/domains/video_production/README.md` to document storage
  guard ownership, facade mapping, and cleanup gates.
- Add focused boundary tests proving old and new imports resolve to the same
  module object and legacy monkeypatch paths remain viable.

Out of scope:

- No behavior changes to provider URL allow-listing, local/private host
  rejection, Pixelle root containment, media content checks, checksums, storage
  status updates, or repairable error payloads.
- No migration of production worker or video production service consumers in
  this step.

## Architecture

The domain asset storage guard owns:

- `ALLOWED_PROVIDER_SCHEMES`
- `ALLOWED_IMAGE_MAGIC`
- `ALLOWED_VIDEO_MAGIC`
- `persist_provider_asset`

The legacy service module imports the domain storage guard module, replaces
itself in `sys.modules`, and updates globals so existing imports and monkeypatch
paths keep targeting the same module object.

## Testing

Add `server/tests/test_video_production_asset_storage_guard_facade.py` to verify:

- this spec and plan mention
  `app.domains.video_production.asset_storage_guard`,
  `app.services.asset_storage_guard`, `ALLOWED_PROVIDER_SCHEMES`,
  `ALLOWED_IMAGE_MAGIC`, `ALLOWED_VIDEO_MAGIC`, and
  `persist_provider_asset`;
- the domain asset storage guard file exists;
- the legacy service file is a thin facade with no copied implementation;
- old and new imports resolve to the same module object and expose identical key
  constants/functions;
- the legacy package attribute preserves monkeypatch access to `httpx.stream`;
- the moved implementation imports the domain production errors path directly;
- the video production router imports the domain storage helper directly;
- the video production README records storage guard ownership, facade mapping,
  and cleanup gate.

Run focused verification:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_asset_storage_guard_facade.py server/tests/test_asset_storage_guard.py -q
```

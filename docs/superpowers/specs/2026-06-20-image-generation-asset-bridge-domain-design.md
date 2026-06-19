# Image Generation Asset Bridge Domain Design

Status: auto-approved.

## Context

The image generation domain owns the image production router, but the route
that promotes an image creation asset into a video production asset still calls
`app.services.image_asset_bridge_service`. That bridge is image-generation
business logic: it validates image review state, image asset scope, and video
asset slot conflicts before recording downstream usage.

## Decision

Move the implementation to
`app.domains.image_generation.image_asset_bridge_service` and keep
`app.services.image_asset_bridge_service` as a thin `sys.modules` compatibility
facade.

This lets the image production router use the domain path while preserving old
imports from storyboard image services and tests.

## Scope

In scope:

- Create `server/app/domains/image_generation/image_asset_bridge_service.py`
  with the current implementation.
- Replace `server/app/services/image_asset_bridge_service.py` with a
  compatibility facade.
- Update `server/app/domains/image_generation/image_production_router.py` to
  import `promote_image_asset_to_video_asset` and `video_asset_payload` from the
  domain path.
- Update `server/app/domains/image_generation/README.md` to document asset
  bridge ownership, facade mapping, and cleanup gates.
- Add focused boundary tests proving old and new asset bridge imports resolve to
  the same module object.

Out of scope:

- No behavior changes to review gate checks, allowed action checks, scope
  validation, slot conflict handling, metadata payloads, downstream usage
  updates, or commits.
- No cleanup of legacy imports in `storyboard_image_service.py` or existing
  asset bridge tests in this step.

## Architecture

The domain asset bridge owns:

- `promote_image_asset_to_video_asset`
- `video_asset_payload`
- `_metadata`
- `_validate_scope`
- `_scope_conflict`
- `_review_snapshot`

The legacy service module imports the domain asset bridge module, replaces
itself in `sys.modules`, and updates globals so existing imports and monkeypatches
keep targeting the same module object.

## Data Flow

The image production router calls the domain bridge to promote an approved image
asset into a `VideoProductionAsset`. The bridge still reads the image asset,
image task, and target video run through the same SQLAlchemy session, writes the
same video asset row or updates the existing row usage, commits, refreshes, and
returns the same ORM object.

## Error Handling

Error behavior is unchanged. Missing source assets, stale versions, review gate
blocks, disallowed actions, missing video runs, scope conflicts, and slot
conflicts continue to raise the same image errors.

## Testing

Add `server/tests/test_image_generation_asset_bridge_facade.py` to verify:

- this spec and plan mention
  `app.domains.image_generation.image_asset_bridge_service`,
  `app.services.image_asset_bridge_service`,
  `promote_image_asset_to_video_asset`, and `video_asset_payload`;
- the domain asset bridge file exists;
- the legacy service file is a thin facade with no copied implementation;
- old and new imports resolve to the same module object and expose identical
  key functions;
- the domain image production router imports the domain asset bridge path;
- the image generation README records asset bridge ownership, facade mapping,
  and cleanup gate.

Run focused verification:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_asset_bridge_facade.py server/tests/test_image_asset_bridge.py -q
```

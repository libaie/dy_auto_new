# Creative Library Reference Asset Service Domain Design

Status: auto-approved.

## Context

`app.domains.creative_library` already owns character and scene route boundaries, including reference image generation endpoints. The implementation for character and scene reference image generation still lives in `app.services.reference_asset_service`, which keeps a core creative-library behavior in the flat service folder.

## Decision

Move the implementation to `app.domains.creative_library.reference_asset_service` and keep `app.services.reference_asset_service` as a thin `sys.modules` compatibility facade.

The creative library domain owns the business rules for character and scene reference assets. The service can still call lower-level image creation helpers from `app.services.image_creation_service` until the image generation services are migrated separately.

## Scope

In scope:

- Create `server/app/domains/creative_library/reference_asset_service.py` with the current implementation.
- Replace `server/app/services/reference_asset_service.py` with a compatibility facade.
- Update domain-owned production modules to import the service from `app.domains.creative_library.reference_asset_service`.
- Update `server/app/domains/creative_library/README.md` to record service ownership, facade mapping, and cleanup gates.
- Add focused boundary tests proving old and new service imports resolve to the same module object.

Out of scope:

- No behavior changes to reference URL usability, TOS expiry checks, provider task reuse, project storage copy, prompt construction, visual style checks, or character/scene row updates.
- No changes to image creation provider logic.
- No cleanup of legacy imports in service modules whose domains have not moved yet.

## Architecture

The domain service owns:

- `ReferenceAssetError`
- `reference_url_is_usable`
- `generate_reference_url`
- `generate_character_reference_images`
- `generate_scene_reference_images`
- reference slot constants and reference task status constants

The legacy service module imports the domain service module, replaces itself in `sys.modules`, and updates globals so imports such as `from app.services import reference_asset_service` and `from app.services.reference_asset_service import ReferenceAssetError` keep working.

Domain modules that call this service use the domain path:

- `app.domains.creative_library.characters_router`
- `app.domains.creative_library.scenes_router`
- `app.domains.ai_video_series.style_lock`
- `app.domains.ai_video_series.read_models`

## Data Flow

Characters and scenes route handlers call the domain reference asset service. The service still builds prompts from character/scene rows, reuses valid existing references when possible, delegates image task creation/sync to the existing image creation service, stores project-managed references, and updates the owning ORM row.

## Error Handling

Error behavior is unchanged. Provider failures and unsupported model scenes still raise `ReferenceAssetError` with the existing codes and details, and route modules continue mapping those errors to HTTP responses.

## Testing

Add `server/tests/test_creative_library_reference_asset_service_facade.py` to verify:

- this spec and plan mention `app.domains.creative_library.reference_asset_service`, `app.services.reference_asset_service`, `ReferenceAssetError`, `generate_reference_url`, `generate_character_reference_images`, and `generate_scene_reference_images`;
- the domain service file exists;
- the legacy service file is a thin facade with no copied business implementation;
- old and new imports resolve to the same module object and expose identical key public functions/constants;
- domain-owned production modules import the domain service path;
- the creative library README records service ownership, facade mapping, and cleanup gate.

Run focused verification:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_creative_library_reference_asset_service_facade.py server/tests/test_creative_library_domain_boundary.py server/tests/test_reference_asset_service.py -q
```

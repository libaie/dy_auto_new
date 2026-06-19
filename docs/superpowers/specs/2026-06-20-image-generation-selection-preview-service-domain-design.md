# Image Generation Selection Preview Service Domain Design

Status: auto-approved.

## Context

`app.domains.image_generation` owns the image production routes, including `/api/image-production/selection-preview`. The selection preview implementation still lives in `app.services.image_selection_preview_service`, which keeps model selection, provider option validation, cost/capacity/review preview, request hashing, and preview persistence in the flat service folder.

## Decision

Move the implementation to `app.domains.image_generation.image_selection_preview_service` and keep `app.services.image_selection_preview_service` as a thin `sys.modules` compatibility facade.

This preserves old imports and tests while making the image generation domain own the selection preview business logic used by its route surface.

## Scope

In scope:

- Create `server/app/domains/image_generation/image_selection_preview_service.py` with the current implementation.
- Replace `server/app/services/image_selection_preview_service.py` with a compatibility facade.
- Update `server/app/domains/image_generation/image_production_router.py` to import `create_selection_preview` from the domain path.
- Update the moved service to import `strategy_payload` from `app.domains.image_generation.image_production_strategy_service`.
- Update `server/app/domains/image_generation/README.md` to document service ownership, facade mapping, and cleanup gates.
- Add focused boundary tests proving old and new service imports resolve to the same module object.

Out of scope:

- No behavior changes to model selection, provider option validation, fallback confirmation, cost/time estimate, capacity preview, review gate preview, request hash generation, preview TTL, or persistence shape.
- No changes to image creation task validation or selection preview drift checks.
- No cleanup of legacy imports in tests or service modules whose domains have not moved yet.

## Architecture

The domain service owns:

- `create_selection_preview`
- `_validate_provider_options`
- `_get_strategy`
- `_selected_model_payload`

The service continues to depend on lower-level policy runtime, model selection, image creation mode metadata, and preview hash helpers. The legacy service module imports the domain service module, replaces itself in `sys.modules`, and updates globals so existing imports and monkeypatches keep targeting the same module object.

## Data Flow

The image production router calls `create_selection_preview` from the domain service. The service resolves the active strategy, chooses a model, validates provider options, computes cost/capacity/review information, persists an `ImageSelectionPreview` row when a model is selected, and returns the same response payload as before.

## Error Handling

Error behavior is unchanged. Unsupported modes, missing strategies, inactive strategies, stale strategy versions, unsupported strategy modes, invalid provider options, and empty model selections continue to raise the same `image_error` codes.

## Testing

Add `server/tests/test_image_generation_selection_preview_service_facade.py` to verify:

- this spec and plan mention `app.domains.image_generation.image_selection_preview_service`, `app.services.image_selection_preview_service`, `create_selection_preview`, `_validate_provider_options`, and `ImageSelectionPreview`;
- the domain service file exists;
- the legacy service file is a thin facade with no copied implementation;
- old and new imports resolve to the same module object and expose identical key functions;
- the image production router imports the domain service path;
- the image generation README records service ownership, facade mapping, and cleanup gate.

Run focused verification:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_selection_preview_service_facade.py server/tests/test_image_generation_domain_boundary.py server/tests/test_image_selection_preview_service.py -q
```

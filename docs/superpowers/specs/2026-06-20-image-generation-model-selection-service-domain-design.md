# Image Generation Model Selection Service Domain Design

Status: auto-approved.

## Context

The image generation domain now owns image production strategy and selection preview services. `app.services.image_model_selection_service` still owns the lower-level model selection diagnostics used by selection preview and image creation, leaving one core image-generation decision service in the flat service folder.

## Decision

Move the implementation to `app.domains.image_generation.image_model_selection_service` and keep `app.services.image_model_selection_service` as a thin `sys.modules` compatibility facade.

This keeps old imports working while allowing the image generation domain to own model selection alongside strategy and preview logic.

## Scope

In scope:

- Create `server/app/domains/image_generation/image_model_selection_service.py` with the current implementation.
- Replace `server/app/services/image_model_selection_service.py` with a compatibility facade.
- Update `server/app/domains/image_generation/image_selection_preview_service.py` to import `resolve_image_model_selection` from the domain path.
- Update `server/app/domains/image_generation/README.md` to document service ownership, facade mapping, and cleanup gates.
- Add focused boundary tests proving old and new service imports resolve to the same module object.

Out of scope:

- No behavior changes to model ordering, capability checks, preferred model handling, fallback candidate generation, warnings, or rescue actions.
- No cleanup of legacy imports in `image_creation_service.py` or tests in this step.

## Architecture

The domain service owns:

- `resolve_image_model_selection`
- `_selected_model_payload`
- `_rejected_candidate`
- `_fallback_model_payload`
- `_fallback_model_ids`

The service continues to use shared `AIModel` and `ImageProductionStrategy` ORM models and `_model_supports_capability` from runtime model config. The legacy service module imports the domain service module, replaces itself in `sys.modules`, and updates globals so existing imports and monkeypatches keep targeting the same module object.

## Data Flow

Selection preview calls `resolve_image_model_selection` from the domain service. The service loads enabled and disabled image models, applies preferred/default/fallback strategy rules, computes rejected diagnostics, and returns the same selected model, fallback, warning, and rescue action payload.

## Error Handling

Error behavior is unchanged. This service returns diagnostics instead of raising route-level errors; callers keep deciding whether a missing selected model is recoverable or blocked.

## Testing

Add `server/tests/test_image_generation_model_selection_service_facade.py` to verify:

- this spec and plan mention `app.domains.image_generation.image_model_selection_service`, `app.services.image_model_selection_service`, `resolve_image_model_selection`, `_selected_model_payload`, and `_fallback_model_payload`;
- the domain service file exists;
- the legacy service file is a thin facade with no copied implementation;
- old and new imports resolve to the same module object and expose identical key functions;
- the domain selection preview service imports the domain model selection path;
- the image generation README records service ownership, facade mapping, and cleanup gate.

Run focused verification:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_model_selection_service_facade.py server/tests/test_image_model_selection_service.py server/tests/test_image_selection_preview_service.py -q
```

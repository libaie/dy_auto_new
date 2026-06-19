# Image Generation Selection Preview Hash Domain Design

Status: auto-approved.

## Context

The image generation domain now owns selection preview orchestration, model
selection, and strategy logic. `app.services.image_selection_preview_hash` still
owns the deterministic request hash helpers used by selection preview and image
creation, leaving a small but central image-generation helper in the flat
service folder.

## Decision

Move the implementation to
`app.domains.image_generation.image_selection_preview_hash` and keep
`app.services.image_selection_preview_hash` as a thin `sys.modules`
compatibility facade.

This keeps old imports working while letting domain-owned selection preview code
depend on another domain module instead of reaching back into `app.services`.

## Scope

In scope:

- Create `server/app/domains/image_generation/image_selection_preview_hash.py`
  with the current implementation.
- Replace `server/app/services/image_selection_preview_hash.py` with a
  compatibility facade.
- Update `server/app/domains/image_generation/image_selection_preview_service.py`
  to import `selection_preview_hash_inputs` and
  `selection_preview_request_hash` from the domain path.
- Update `server/app/domains/image_generation/README.md` to document helper
  ownership, facade mapping, and cleanup gates.
- Add focused boundary tests proving old and new helper imports resolve to the
  same module object.

Out of scope:

- No behavior changes to request hash inputs, normalization rules, SHA-256
  output, or JSON serialization.
- No cleanup of legacy imports in `image_creation_service.py`,
  `image_ab_test_service.py`, or tests in this step.

## Architecture

The domain helper owns:

- `selection_preview_hash_inputs`
- `selection_preview_request_hash`
- `_source_identity`
- `_reference_identities`

The legacy helper module imports the domain helper module, replaces itself in
`sys.modules`, and updates globals so existing imports and monkeypatches keep
targeting the same module object.

## Data Flow

Selection preview assembles normalized hash inputs in
`selection_preview_hash_inputs`, serializes the structure with sorted keys, and
returns the stable SHA-256 request hash through
`selection_preview_request_hash`. The migration changes only the module
boundary; callers keep passing the same payload, strategy, model, and provider
option values.

## Error Handling

Error behavior is unchanged. The helper does not raise route-level business
errors; callers keep validating payloads and provider options before hashing.

## Testing

Add `server/tests/test_image_generation_selection_preview_hash_facade.py` to
verify:

- this spec and plan mention
  `app.domains.image_generation.image_selection_preview_hash`,
  `app.services.image_selection_preview_hash`,
  `selection_preview_hash_inputs`, and
  `selection_preview_request_hash`;
- the domain helper file exists;
- the legacy helper file is a thin facade with no copied implementation;
- old and new imports resolve to the same module object and expose identical
  key functions;
- the domain selection preview service imports the domain helper path;
- the image generation README records helper ownership, facade mapping, and
  cleanup gate.

Run focused verification:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_selection_preview_hash_facade.py server/tests/test_image_generation_selection_preview_service_facade.py server/tests/test_image_selection_preview_service.py -q
```

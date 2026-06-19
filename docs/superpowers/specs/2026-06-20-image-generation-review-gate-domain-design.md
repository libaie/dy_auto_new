# Image Generation Review Gate Domain Design

Status: auto-approved.

## Context

The image generation asset bridge now lives in the image generation domain, but
it still imports `app.services.image_review_gate_service` for image asset review
gate checks. The review gate helper is image-generation-specific and small,
while old image creation and storyboard paths still rely on the legacy import.

## Decision

Move the implementation to
`app.domains.image_generation.image_review_gate_service` and keep
`app.services.image_review_gate_service` as a thin `sys.modules` compatibility
facade.

This lets domain-owned asset promotion use a domain helper without breaking
legacy callers.

## Scope

In scope:

- Create `server/app/domains/image_generation/image_review_gate_service.py` with
  the current implementation.
- Replace `server/app/services/image_review_gate_service.py` with a
  compatibility facade.
- Update `server/app/domains/image_generation/image_asset_bridge_service.py` to
  import `asset_review_gate`, `review_gate_passed`, and
  `review_gate_rescue_actions` from the domain path.
- Update `server/app/domains/image_generation/README.md` to document review gate
  ownership, facade mapping, and cleanup gates.
- Add focused boundary tests proving old and new review gate imports resolve to
  the same module object.

Out of scope:

- No behavior changes to default gate derivation, manual/AI review checks,
  blocked status handling, or rescue action payloads.
- No cleanup of legacy imports in `image_creation_service.py`,
  `storyboard_image_service.py`, or existing tests in this step.

## Architecture

The domain review gate service owns:

- `asset_review_gate`
- `review_gate_passed`
- `review_gate_rescue_actions`

The legacy service module imports the domain review gate service module,
replaces itself in `sys.modules`, and updates globals so existing imports and
monkeypatches keep targeting the same module object.

## Data Flow

Asset promotion calls the domain review gate helper to derive the current gate
from task request metadata and asset metadata, decide whether promotion may
proceed, and provide rescue actions when blocked.

## Error Handling

Error behavior is unchanged. The helper still returns dictionaries and booleans;
callers keep raising route-level image errors.

## Testing

Add `server/tests/test_image_generation_review_gate_facade.py` to verify:

- this spec and plan mention
  `app.domains.image_generation.image_review_gate_service`,
  `app.services.image_review_gate_service`, `asset_review_gate`,
  `review_gate_passed`, and `review_gate_rescue_actions`;
- the domain review gate service file exists;
- the legacy service file is a thin facade with no copied implementation;
- old and new imports resolve to the same module object and expose identical key
  functions;
- the domain asset bridge imports the domain review gate path;
- the image generation README records review gate ownership, facade mapping, and
  cleanup gate.

Run focused verification:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_review_gate_facade.py server/tests/test_image_asset_bridge.py server/tests/test_image_creation_strategy_snapshot.py -q
```

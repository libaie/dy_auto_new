# Image Generation Policy Runtime Domain Design

Status: auto-approved.

## Context

The image generation domain owns selection preview orchestration. That preview
calls `app.services.image_production_policy_runtime` for cost estimates,
capacity previews, and review gate previews, so domain-owned code still reaches
back into the flat service folder for core image-generation policy logic.

## Decision

Move the implementation to
`app.domains.image_generation.image_production_policy_runtime` and keep
`app.services.image_production_policy_runtime` as a thin `sys.modules`
compatibility facade.

This preserves existing image creation imports while letting selection preview
use a domain-owned policy runtime module.

## Scope

In scope:

- Create `server/app/domains/image_generation/image_production_policy_runtime.py`
  with the current implementation.
- Replace `server/app/services/image_production_policy_runtime.py` with a
  compatibility facade.
- Update `server/app/domains/image_generation/image_selection_preview_service.py`
  to import `estimate_image_cost`, `preview_image_capacity`, and
  `preview_review_gate` from the domain path.
- Update `server/app/domains/image_generation/README.md` to document policy
  runtime ownership, facade mapping, and cleanup gates.
- Add focused boundary tests proving old and new policy runtime imports resolve
  to the same module object.

Out of scope:

- No behavior changes to cost policy snapshots, model cost overrides,
  admission-control counting, queue depth estimates, or review gate decisions.
- No cleanup of legacy imports in `image_creation_service.py` or existing policy
  runtime tests in this step.

## Architecture

The domain policy runtime owns:

- `estimate_image_cost`
- `preview_image_capacity`
- `preview_review_gate`
- `_policy_snapshot`
- `_count_images`
- `DEFAULT_COST_POLICY`
- `DEFAULT_CAPACITY_POLICY`
- `DEFAULT_REVIEW_POLICY`

The legacy service module imports the domain policy runtime module, replaces
itself in `sys.modules`, and updates globals so existing imports and monkeypatches
keep targeting the same module object.

## Data Flow

Selection preview calls the domain policy runtime to assemble cost, capacity,
and review previews. The runtime still reads `ImageProductionPolicyVersion`,
`ImageProductionStrategy`, and active `ImageCreationTask` rows through the same
SQLAlchemy session and returns the same dictionaries to callers.

## Error Handling

Error behavior is unchanged. Missing policy versions still fall back to default
snapshots, invalid count payloads still normalize to one image, and callers keep
owning route-level validation and error responses.

## Testing

Add `server/tests/test_image_generation_policy_runtime_facade.py` to verify:

- this spec and plan mention
  `app.domains.image_generation.image_production_policy_runtime`,
  `app.services.image_production_policy_runtime`, `estimate_image_cost`,
  `preview_image_capacity`, and `preview_review_gate`;
- the domain policy runtime file exists;
- the legacy service file is a thin facade with no copied implementation;
- old and new imports resolve to the same module object and expose identical
  key functions/constants;
- the domain selection preview service imports the domain policy runtime path;
- the image generation README records policy runtime ownership, facade mapping,
  and cleanup gate.

Run focused verification:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_policy_runtime_facade.py server/tests/test_image_production_policy_runtime.py server/tests/test_image_selection_preview_service.py -q
```

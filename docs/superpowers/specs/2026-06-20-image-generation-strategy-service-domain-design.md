# Image Generation Strategy Service Domain Design

Status: auto-approved.

## Context

`app.domains.image_generation` owns the image creation and image production route boundaries. The strategy CRUD/versioning implementation still lives in `app.services.image_production_strategy_service`, so strategy business rules remain in the flat service folder even though the route surface has moved.

## Decision

Move the implementation to `app.domains.image_generation.image_production_strategy_service` and keep `app.services.image_production_strategy_service` as a thin `sys.modules` compatibility facade.

This keeps old imports and tests working while making the image generation domain own image production strategy behavior.

## Scope

In scope:

- Create `server/app/domains/image_generation/image_production_strategy_service.py` with the current strategy implementation.
- Replace `server/app/services/image_production_strategy_service.py` with a compatibility facade.
- Update `server/app/domains/image_generation/image_production_router.py` to import the strategy service from the domain path.
- Update `server/app/domains/image_generation/README.md` to document service ownership, facade mapping, and cleanup gates.
- Add focused boundary tests proving old and new imports resolve to the same module object.

Out of scope:

- No behavior changes to default strategy seeding, strategy validation, policy validation, version writes, status transitions, production events, or payload serialization.
- No changes to image selection preview, image creation, A/B test, or recommendation services in this step.
- No cleanup of legacy imports in tests or service modules whose domains have not moved yet.

## Architecture

The domain service owns:

- `DEFAULT_STRATEGIES`
- `VALID_DESTINATION_ROLES`
- `VALID_MODES`
- `seed_default_image_strategies`
- `list_strategies`
- `get_strategy`
- `create_strategy`
- `update_strategy`
- `set_strategy_status`
- `strategy_payload`

The legacy service module imports the domain service module, replaces itself in `sys.modules`, and updates globals so existing imports and monkeypatches keep targeting the same module object.

## Data Flow

The image production router calls the domain strategy service. The service still reads and writes `ImageProductionStrategy`, `ImageProductionStrategyVersion`, and `ImageProductionPolicyVersion`, records production events for status transitions, and returns the same strategy payload shape.

## Error Handling

Error behavior is unchanged. Invalid role/mode/policy/status inputs and optimistic version conflicts still raise the same `image_error` HTTP exceptions and error codes.

## Testing

Add `server/tests/test_image_generation_strategy_service_facade.py` to verify:

- this spec and plan mention `app.domains.image_generation.image_production_strategy_service`, `app.services.image_production_strategy_service`, `seed_default_image_strategies`, `create_strategy`, `update_strategy`, and `strategy_payload`;
- the domain service file exists;
- the legacy service file is a thin facade with no copied implementation;
- old and new imports resolve to the same module object and expose identical key public functions/constants;
- the image production router imports the domain service path;
- the image generation README records service ownership, facade mapping, and cleanup gate.

Run focused verification:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_strategy_service_facade.py server/tests/test_image_generation_domain_boundary.py server/tests/test_image_production_strategy_service.py -q
```

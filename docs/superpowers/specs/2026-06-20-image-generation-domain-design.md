# Image Generation Domain Design

Date: 2026-06-20

## Goal

Move image creation and image production route ownership out of the flat
`app.routers` folder and into `app.domains.image_generation`, without changing
public API behavior.

This is the next modularization slice after device, content, account, task, and
AI video series domains. It is intentionally limited to the route boundary first
because the image services already have extensive tests and several service files
have unrelated in-progress changes.

## Scope

The new domain owns:

- `/api/image-creation/*` route assembly;
- `/api/image-production/*` route assembly;
- image creation request schemas currently local to `app.routers.image_creation`;
- image production strategy, A/B, selection preview, and promotion request schemas
  currently local to `app.routers.image_production`;
- route-level helper functions such as `_auth_user_id`, `_metrics_by_strategy`,
  and `_strategy_payload_with_metric`.

The migration keeps these modules as compatibility facades:

- `app.routers.image_creation`;
- `app.routers.image_production`.

## Non-Goals

- Do not split `app.services.image_creation_service` in this slice.
- Do not split image production strategy, A/B, metrics, recommendation, or policy
  services in this slice.
- Do not move ORM model class bodies.
- Do not rename public API paths or route functions.
- Do not change authentication dependencies or response payloads.
- Do not wire `app.main` directly to the domain router while `main.py` has
  unrelated mixed WIP. That wiring is a later isolated-index step.

## Target Structure

```text
server/app/domains/image_generation/
  __init__.py
  README.md
  image_creation_router.py
  image_production_router.py
```

The first route migration keeps the copied router modules behavior-equivalent.
Service extraction can happen later behind the same domain boundary.

## Compatibility Strategy

Legacy imports remain valid by replacing the old router modules with module
aliases:

```python
from app.domains.image_generation import image_creation_router as _image_creation_router
sys.modules[__name__] = _image_creation_router
globals().update(_image_creation_router.__dict__)
```

This keeps old monkeypatch/import paths working while tests and production
startup continue to use `app.routers.image_creation` and
`app.routers.image_production`.

## Tests

The migration adds:

- route/auth snapshot tests for `/api/image-creation/*` and
  `/api/image-production/*`;
- domain boundary tests for metadata, README, facade thickness, and route
  registration;
- router facade tests proving legacy imports and domain imports resolve to the
  same module objects.

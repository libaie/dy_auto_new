# Selector Management Domain Design

Date: 2026-06-20

## Goal

Move admin selector-management route ownership out of the flat `app.routers`
folder and into `app.domains.selector_management` without changing public API
behavior.

This domain owns the admin workflow for UI selectors: listing, CRUD, toggling,
template image listing/upload/delete, selector revision broadcasts, and admin
cache update notifications.

## Scope

The new domain owns:

- `/api/selectors/*` route assembly;
- selector request schemas currently local to `app.routers.selectors`;
- route-local template image upload/delete endpoints;
- websocket notification payloads for `selectors_updated` and
  `selectors_changed`.

The migration keeps `app.routers.selectors` as a compatibility facade.

## Non-Goals

- Do not move device-facing `/api/device/selectors`; that stays in
  `device_operations`.
- Selector CRUD, revision tracking, and device selector filtering now live in
  `app.domains.selector_management.selector_service`;
  `app.services.selector_service` remains as a temporary compatibility facade.
- Do not split or move `template_service` in this slice.
- Do not move selector ORM model bodies.
- Do not change route paths, route ordering, auth dependencies, response shapes,
  websocket payloads, or upload validation behavior.

## Target Structure

```text
server/app/domains/selector_management/
  __init__.py
  README.md
  selector_service.py
  selectors_router.py
```

This began as a route-boundary migration. Selector CRUD and device selector
filtering now live in the selector management domain through `SelectorService`,
while later work can still split template image handlers and realtime
notification helpers after the domain import boundary is stable.

## Compatibility Strategy

Legacy imports stay valid through a module alias:

```python
from app.domains.selector_management import selectors_router as _selectors_router
sys.modules[__name__] = _selectors_router
globals().update(_selectors_router.__dict__)
```

This also keeps any future monkeypatches against `app.routers.selectors.*`
working during the alias phase.

The selector service follows the same compatibility rule:

- `app.services.selector_service` ->
  `app.domains.selector_management.selector_service`.
- Keep the facade until the selector management README cleanup gate passes,
  including `rg "app\.services\.selector_service" server/app server/tests`
  showing only compatibility tests, migration docs, seed helpers, or callers
  from domains that have not moved yet.

## Tests

The migration adds:

- route/auth snapshot tests for `/api/selectors/*`;
- boundary tests for metadata, README, facade thickness, route registration, and
  device selector non-ownership;
- facade identity tests proving old and new imports resolve to the same module
  object while compatibility is active.

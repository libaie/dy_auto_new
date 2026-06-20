# Selector Service Domain Design

Date: 2026-06-20

## Goal

Move selector CRUD, selector revision tracking, device-facing selector filtering,
and selector serialization out of the flat `app.services` folder and into
`app.domains.selector_management` without changing API or device behavior.

This makes selector management a business-owned domain instead of a route module
that depends on a generic service bucket.

## Approved Approach

Move `server/app/services/selector_service.py` to
`server/app/domains/selector_management/selector_service.py`.

Keep `app.services.selector_service` as a temporary `sys.modules` compatibility
facade. The selector management router imports the domain service directly.
Device operations and seed scripts can continue to import the legacy path until
their domains are migrated.

## Boundaries

- Preserve `SelectorService`, `selector_service`, `_get_revision`,
  `_set_revision`, `_bump_revision`, `_aspect_tag`, `_profile_priority`,
  `_to_dict`, and `_to_device_dict`.
- Preserve monotonic selector revision behavior backed by `SystemSetting`.
- Preserve device selector candidate filtering by screen resolution and aspect
  ratio.
- Preserve selector CRUD commits, refreshes, response dictionaries, and disabled
  selector filtering.
- Preserve `/api/device/selectors` ownership in `device_operations`.
- Do not move `template_service` in this slice.
- Do not change route paths, auth dependencies, route ordering, websocket
  payloads, upload validation, or seed behavior.

## Target Structure

```text
server/app/domains/selector_management/
  __init__.py
  README.md
  selector_service.py
  selectors_router.py

server/app/services/
  selector_service.py  # compatibility facade
```

## Compatibility Strategy

Legacy imports stay valid through a module alias:

```python
import sys

from app.domains.selector_management import selector_service as _domain_module

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

The legacy and domain imports must resolve to the same module object so existing
tests, seed helpers, and device operations keep importing the same singleton and
helper functions.

## Documentation Updates

Update the selector management README and same-day selector management design
and plan to register:

- `app.services.selector_service` ->
  `app.domains.selector_management.selector_service`;
- the selector service cleanup gate;
- the direct domain import from `selectors_router.py`.

## Verification

- Add a boundary test proving the new spec and plan mention
  `app.domains.selector_management.selector_service`,
  `app.services.selector_service`, `SelectorService`, `selector_service`, and
  `_bump_revision`.
- Prove the domain service file exists.
- Prove the legacy file is a thin facade with no local `class SelectorService`
  and no local `selector_service = SelectorService()`.
- Prove legacy and domain imports resolve to the same module object and expose
  the same singleton and helper functions.
- Prove `selectors_router.py` imports the domain service directly while
  `template_service` remains unchanged for this slice.
- Prove device selector routes still live in `device_operations` and can remain
  on the legacy selector service facade.
- Run selector service, selector management route/facade, selector API, and
  device selector tests after migration.

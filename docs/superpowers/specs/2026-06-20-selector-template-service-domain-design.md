# Selector Template Service Domain Design

Date: 2026-06-20

## Goal

Move template image listing, caching, path lookup, save, and delete logic out of
the flat `app.services` folder and into `app.domains.selector_management`
without changing admin selector template APIs or device template downloads.

This completes the selector management service ownership pair after moving
`selector_service`: selector CRUD and selector template images now live in the
same business domain.

## Approved Approach

Move `server/app/services/template_service.py` to
`server/app/domains/selector_management/template_service.py`.

Keep `app.services.template_service` as a temporary `sys.modules` compatibility
facade. The selector management router imports the domain template service
directly. Device operations can continue to import the legacy path until that
domain is ready for a separate migration.

## Boundaries

- Preserve `TemplateService`, `template_service`, `TEMPLATE_DIR`,
  `ALLOWED_EXTENSIONS`, `_aspect_tag`, `_same_aspect_dirs`,
  `_ensure_resolution_dir`, and `_safe_resolve`.
- Preserve template file storage under `server/app/template_images`.
- Preserve default and same-aspect-ratio fallback listing behavior.
- Preserve MD5 cache behavior and cache invalidation on save/delete.
- Preserve path traversal protection in lookup, save, and delete paths.
- Preserve `/api/selectors/templates*` route behavior in selector management.
- Preserve `/api/device/templates*` ownership in `device_operations`.
- Do not move `prompt_template_service` in this slice.
- Do not change upload validation, allowed file extensions, route ordering,
  response shapes, or device auth behavior.

## Target Structure

```text
server/app/domains/selector_management/
  __init__.py
  README.md
  selector_service.py
  selectors_router.py
  template_service.py

server/app/services/
  template_service.py  # compatibility facade
```

## Compatibility Strategy

Legacy imports stay valid through a module alias:

```python
import sys

from app.domains.selector_management import template_service as _domain_module

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

The legacy and domain imports must resolve to the same module object so tests,
device routes, and monkeypatches keep touching the same singleton and helper
functions.

## Path Stability

Moving the module changes `__file__`, so the implementation must not keep the old
`Path(__file__).resolve().parent.parent / "template_images"` expression. The
domain implementation must compute:

```python
TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "template_images"
```

For `server/app/domains/selector_management/template_service.py`, `parents[2]`
is `server/app`, preserving the existing storage directory.

## Documentation Updates

Update the selector management README and same-day selector management design
and plan to register:

- `app.services.template_service` ->
  `app.domains.selector_management.template_service`;
- the template service cleanup gate;
- the direct domain import from `selectors_router.py`;
- the storage invariant that template images remain under
  `server/app/template_images`.

## Verification

- Add a boundary test proving the new spec and plan mention
  `app.domains.selector_management.template_service`,
  `app.services.template_service`, `TemplateService`, `template_service`, and
  `TEMPLATE_DIR`.
- Prove the domain service file exists.
- Prove the legacy file is a thin facade with no local `class TemplateService`
  and no local `template_service = TemplateService()`.
- Prove legacy and domain imports resolve to the same module object and expose
  the same singleton and helper functions.
- Prove `TEMPLATE_DIR` still points at `server/app/template_images`.
- Prove `selectors_router.py` imports the domain template service directly.
- Prove device template routes still live in `device_operations` and can remain
  on the legacy facade.
- Run selector template API, device template upload/download, selector
  management route/facade, and device endpoint tests after migration.

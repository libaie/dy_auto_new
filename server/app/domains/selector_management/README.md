# Selector Management Domain

This domain owns admin UI selector management routes.

## Owned Routes

- `/api/selectors/*`

## Not Owned

- `/api/device/selectors` stays in `device_operations`.

## Current Modules

- `selectors_router.py` owns selector CRUD, selector toggling, template image
  list/upload/delete, selector revision broadcasts, and admin cache update
  notifications.
- `selector_service.py` owns `SelectorService`, `selector_service`, selector
  CRUD, revision counter updates, device selector filtering, and selector
  serialization.
- `template_service.py` owns `TemplateService`, `template_service`,
  resolution-aware image listing, MD5 caching, template path lookup, save, and
  delete operations. It preserves storage under `server/app/template_images`.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.selectors` | `app.domains.selector_management.selectors_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |
| `app.services.selector_service` | `app.domains.selector_management.selector_service` | All selector service callers import the domain service directly or belong to domains that have not moved yet. |
| `app.services.template_service` | `app.domains.selector_management.template_service` | All template service callers import the domain service directly or belong to domains that have not moved yet. |

## Boundaries

- Keep device selector polling in `device_operations`.
- Keep selector CRUD and device selector filtering in
  `app.domains.selector_management.selector_service`.
- Keep template image file operations in
  `app.domains.selector_management.template_service`.
- Keep template files stored under `server/app/template_images`.
- Preserve websocket payloads `selectors_updated` and `selectors_changed`.
- Preserve route ordering so `/templates/*` paths are not shadowed by
  `/{action_name}`.

## Compatibility Cleanup Gates

Do not remove the legacy router facade until all of these are true:

- `app.main` imports the selector router from `app.domains.selector_management`.
- Route/auth snapshots pass against the domain endpoint module.
- Legacy and domain imports resolve to the same module object during the alias
  phase.
- Existing selector API, selector service, and device selector tests pass.
- Import inventory shows no unapproved production imports of
  `app.routers.selectors`.

Do not remove the legacy selector service facade until all of these are true:

- `rg "app\.services\.selector_service" server/app server/tests` returns only
  compatibility tests, migration docs, seed helpers, or modules whose domains
  have not moved yet.
- `test_selector_service_domain_facade.py` has been replaced with tests for
  direct domain imports.
- Domain-owned selector management modules import
  `app.domains.selector_management.selector_service` directly.
- Direct domain selector service coverage proves `SelectorService`,
  `selector_service`, and `_bump_revision` behavior without legacy imports.

Do not remove the legacy template service facade until all of these are true:

- `rg "app\.services\.template_service" server/app server/tests` returns only
  compatibility tests, migration docs, or modules whose domains have not moved
  yet.
- `test_selector_template_service_domain_facade.py` has been replaced with
  tests for direct domain imports.
- Domain-owned selector management modules import
  `app.domains.selector_management.template_service` directly.
- Direct domain template service coverage proves `TemplateService`,
  `template_service`, and `TEMPLATE_DIR` behavior without legacy imports.

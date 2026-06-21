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
- `app.db.models.selector_management` owns the `UISelector` ORM class body.
- `template_service.py` owns `TemplateService`, `template_service`,
  resolution-aware image listing, MD5 caching, template path lookup, save, and
  delete operations. It preserves storage under `server/app/template_images`.

## Canonical Imports

The retired router, service, and ORM import packages have been removed. Runtime code, tests, scripts, and new docs must import domain modules directly and use `app.db.models` / `app.db.models.<domain>` for ORM models.

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

## Legacy Import Guard

The cleanup gate is complete. Keep the retired import-path and AST inventory tests passing so removed paths stay unavailable.

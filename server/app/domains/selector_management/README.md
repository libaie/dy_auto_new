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

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.selectors` | `app.domains.selector_management.selectors_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |

## Boundaries

- Keep device selector polling in `device_operations`.
- Keep selector and template service bodies in `app.services.*`.
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

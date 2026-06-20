# Identity Access Domain

This domain owns admin and device authentication routes.

## Owned Routes

- `/api/auth/*`

## Not Owned

- Shared JWT and role dependencies stay in `app.deps`.
- Device secret verification stays with device-facing infrastructure and
  `device_operations`.
- `User` ORM lives in `app.db.models.identity_access`; `Device` remains in
  `app.db_models` until the device/account graph moves.

## Current Modules

- `auth_router.py` owns admin login, device login, admin-only user registration,
  user listing, and route-local brute-force login protection state.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.auth` | `app.domains.identity_access.auth_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |
| `app.db_models.User` | `app.db.models.identity_access.User` | Keep as a compatibility re-export until production imports use the domain model path. |

## Boundaries

- Keep shared token creation and verification helpers in `app.deps`.
- Keep device operations separate from identity access.
- Preserve route paths, route names, auth dependencies, response shapes,
  password hashing, token payloads, trusted-proxy IP behavior, and rate-limit
  behavior.
- Preserve `_failed_attempts` compatibility because tests and old callers may
  reset or inspect rate-limit state via `app.routers.auth`.

## Compatibility Cleanup Gates

Do not remove the legacy router facade until all of these are true:

- `app.main` imports the auth router from `app.domains.identity_access`.
- Route/auth snapshots pass against the domain endpoint module.
- Legacy and domain imports resolve to the same module object during the alias
  phase.
- Existing admin auth tests pass.
- Import inventory shows no unapproved production imports of `app.routers.auth`.

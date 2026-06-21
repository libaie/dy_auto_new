# Identity Access Domain

This domain owns admin and device authentication routes.

## Owned Routes

- `/api/auth/*`

## Not Owned

- Shared JWT and role dependencies stay in `app.deps`.
- Device secret verification stays with device-facing infrastructure and
  `device_operations`.
- `User` ORM lives in `app.db.models.identity_access`; `Device` remains in
  `app.db.models.device_operations`.

## Current Modules

- `auth_router.py` owns admin login, device login, admin-only user registration,
  user listing, and route-local brute-force login protection state.

## Canonical Imports

The retired router, service, and ORM import packages have been removed. Runtime code, tests, scripts, and new docs must import domain modules directly and use `app.db.models` / `app.db.models.<domain>` for ORM models.

## Boundaries

- Keep shared token creation and verification helpers in `app.deps`.
- Keep device operations separate from identity access.
- Preserve route paths, route names, auth dependencies, response shapes,
  password hashing, token payloads, trusted-proxy IP behavior, and rate-limit
  behavior.

## Legacy Import Guard

The cleanup gate is complete. Keep the retired import-path and AST inventory tests passing so removed paths stay unavailable.

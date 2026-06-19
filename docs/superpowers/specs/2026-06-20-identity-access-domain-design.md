# Identity Access Domain Design

Date: 2026-06-20

## Goal

Move authentication route ownership out of the flat `app.routers` folder and
into `app.domains.identity_access` without changing public API behavior.

This domain owns admin login, device login, admin-only user registration, user
listing, and the route-local brute-force login protection state.

## Scope

The new domain owns:

- `POST /api/auth/login`;
- `POST /api/auth/device-login`;
- `POST /api/auth/register`;
- `GET /api/auth/users`;
- route-local login failure tracking helpers and state.

The migration keeps `app.routers.auth` as a compatibility facade.

## Non-Goals

- Do not move shared JWT/token dependencies from `app.deps`.
- Do not move `User` or `Device` ORM model definitions.
- Do not change password hashing, token payloads, token expiry, role checks,
  rate-limit behavior, trusted-proxy IP selection, response shapes, route
  paths, route names, or auth dependencies.
- Do not move device-facing secret verification; device operations stay in
  `device_operations`.

## Target Structure

```text
server/app/domains/identity_access/
  __init__.py
  README.md
  auth_router.py
```

This is a route-boundary migration. Later work can split rate limiting, login
use cases, and user administration helpers after the domain import boundary is
stable.

## Compatibility Strategy

Legacy imports stay valid through a module alias:

```python
from app.domains.identity_access import auth_router as _auth_router
sys.modules[__name__] = _auth_router
globals().update(_auth_router.__dict__)
```

This is required because `server/tests/conftest.py` imports
`app.routers.auth._failed_attempts` to reset rate-limit state between tests.
The legacy module and domain module must resolve to the same object during the
compatibility phase.

## Tests

The migration adds:

- route/auth snapshot tests for `/api/auth/*`;
- boundary tests for metadata, README, facade thickness, route registration,
  main wiring, shared dependency non-ownership, and device-operation separation;
- facade identity tests proving old and new imports resolve to the same module
  object while compatibility is active, including `_failed_attempts` state.

Existing admin auth tests continue to cover login success/failure, expired
tokens, protected endpoint behavior, device-secret behavior, and login rate
limiting.

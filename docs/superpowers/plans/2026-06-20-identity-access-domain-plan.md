# Identity Access Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `app.domains.identity_access` and move authentication route ownership behind a compatibility-preserving domain module.

**Architecture:** Keep shared token dependencies in `app.deps` and move only the FastAPI authentication router boundary. Preserve `app.routers.auth` as a `sys.modules` alias because tests and possible runtime helpers access route-local rate-limit state through the legacy module path.

**Tech Stack:** FastAPI `APIRouter`, SQLAlchemy sessions, bcrypt, JWT helpers from `app.deps`, pytest route snapshots, Python module aliasing via `sys.modules`.

---

### Task 1: Boundary And Route Snapshot Tests

**Files:**
- Create: `server/tests/test_identity_access_auth_parity.py`
- Create: `server/tests/test_identity_access_domain_boundary.py`
- Create: `server/tests/test_identity_access_router_facade.py`
- Keep: `server/tests/test_admin_auth.py`

- [ ] **Step 1: Write the failing route/auth snapshot test**

```python
from fastapi.routing import APIRoute

from app.main import app


EXPECTED_IDENTITY_ACCESS_HTTP_ROUTES = [
    ("/api/auth/login", ("POST",), "login", "app.domains.identity_access.auth_router.login", ("get_db",)),
    ("/api/auth/device-login", ("POST",), "device_login", "app.domains.identity_access.auth_router.device_login", ("get_db",)),
    ("/api/auth/register", ("POST",), "register_user", "app.domains.identity_access.auth_router.register_user", ("checker", "get_db")),
    ("/api/auth/users", ("GET",), "list_users", "app.domains.identity_access.auth_router.list_users", ("checker", "get_db")),
]


def test_identity_access_route_table_snapshot():
    assert _identity_access_http_routes() == EXPECTED_IDENTITY_ACCESS_HTTP_ROUTES
```

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_identity_access_auth_parity.py -q`

Expected: FAIL because endpoints still come from `app.routers.auth`.

- [ ] **Step 2: Add boundary and facade tests**

The tests must assert:

- the spec and plan mention `app.domains.identity_access`, `auth_router.py`,
  `app.routers.auth`, `/api/auth`, `_failed_attempts`, `app.deps`, and
  `device_operations`;
- `app.domains.identity_access` exports `DOMAIN_NAME = "identity_access"` and
  `PUBLIC_ROUTE_PREFIX = "/api/auth"`;
- `server/app/domains/identity_access/README.md` documents the facade register
  and cleanup gates;
- `server/app/routers/auth.py` is a thin facade with no `APIRouter(`;
- `app.main` directly imports and includes `auth_router`;
- `device_operations` does not import `identity_access`;
- legacy and domain module imports resolve to the same object and share
  `_failed_attempts`.

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_identity_access_auth_parity.py server/tests/test_identity_access_domain_boundary.py server/tests/test_identity_access_router_facade.py server/tests/test_admin_auth.py -q`

Expected: FAIL until `app.domains.identity_access` and direct main wiring exist.

### Task 2: Domain Skeleton And Facade Register

**Files:**
- Create: `server/app/domains/identity_access/__init__.py`
- Create: `server/app/domains/identity_access/README.md`

- [ ] **Step 1: Add domain metadata**

```python
"""Identity access domain package."""

DOMAIN_NAME = "identity_access"
PUBLIC_ROUTE_PREFIX = "/api/auth"
```

- [ ] **Step 2: Add README boundary notes**

Document owned `/api/auth/*` routes, shared `app.deps` token helpers,
non-owned device operations, the `app.routers.auth` facade, rate-limit state
compatibility, and cleanup gates.

### Task 3: Router Move With Compatibility Facade

**Files:**
- Create: `server/app/domains/identity_access/auth_router.py`
- Modify: `server/app/routers/auth.py`

- [ ] **Step 1: Copy the router implementation**

Copy the current contents of `server/app/routers/auth.py` to
`server/app/domains/identity_access/auth_router.py` without changing route
behavior.

- [ ] **Step 2: Replace legacy router with a module alias**

```python
"""Compatibility facade for identity access routes.

The implementation now lives in app.domains.identity_access.auth_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.identity_access import auth_router as _auth_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _auth_router
globals().update(_auth_router.__dict__)
```

- [ ] **Step 3: Run focused tests**

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_identity_access_auth_parity.py server/tests/test_identity_access_domain_boundary.py server/tests/test_identity_access_router_facade.py server/tests/test_admin_auth.py -q`

Expected: Auth parity still fails until `app.main` wires the domain router
directly; facade tests and existing admin auth behavior should pass.

- [ ] **Step 4: Commit**

Run: `git commit -m "refactor: move identity access router into domain"`

### Task 4: Direct App Wiring

**Files:**
- Modify: `server/app/main.py`
- Modify: `server/tests/test_identity_access_domain_boundary.py`

- [ ] **Step 1: Wire app main to the domain router**

Replace the legacy `auth` router import/include with:

```python
from app.domains.identity_access import auth_router
app.include_router(auth_router.router)
```

- [ ] **Step 2: Keep legacy facade for old imports**

Do not remove `server/app/routers/auth.py` in this task.

- [ ] **Step 3: Run focused tests**

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_identity_access_auth_parity.py server/tests/test_identity_access_domain_boundary.py server/tests/test_identity_access_router_facade.py server/tests/test_admin_auth.py -q`

Expected: PASS.

- [ ] **Step 4: Commit**

Use an isolated Git index for `server/app/main.py` if the real worktree has
unrelated changes, then commit:

Run: `git commit -m "refactor: wire identity access router from domain"`

### Later Splits

- Split rate limiting and login/user administration use cases only after route
  ownership is stable.
- Keep shared token verification helpers in `app.deps` unless a separate
  security-infrastructure plan moves them.
- Keep device operation secret verification in `device_operations`.

### Verification

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_identity_access_auth_parity.py server/tests/test_identity_access_domain_boundary.py server/tests/test_identity_access_router_facade.py server/tests/test_admin_auth.py -q
```

Self-review checklist:

- Every `/api/auth/*` endpoint module is
  `app.domains.identity_access.auth_router`.
- `app.routers.auth` and `app.domains.identity_access.auth_router` are the same
  module object during the facade phase.
- `_failed_attempts` is shared between legacy and domain import paths.
- Device operations remain separate.
- No response shape, route path, route name, auth dependency, rate-limit
  behavior, trusted-proxy IP behavior, password hashing, or token payload
  changed.

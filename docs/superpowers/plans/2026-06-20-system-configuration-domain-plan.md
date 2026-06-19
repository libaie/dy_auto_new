# System Configuration Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `app.domains.system_configuration` and move admin settings route ownership behind a compatibility-preserving domain module.

**Architecture:** Keep `SystemSetting`, `SettingUpdate`, and all configuration consumers unchanged while moving only the FastAPI router boundary. Preserve `app.routers.settings` as a thin module alias until import inventory proves it can be removed.

**Tech Stack:** FastAPI `APIRouter`, SQLAlchemy sessions, pytest route snapshots, Python module aliasing via `sys.modules`.

---

### Task 1: Boundary And Route Snapshot Tests

**Files:**
- Create: `server/tests/test_system_configuration_auth_parity.py`
- Create: `server/tests/test_system_configuration_domain_boundary.py`
- Create: `server/tests/test_system_configuration_router_facade.py`
- Keep: `server/tests/test_settings_endpoints.py`

- [ ] **Step 1: Write the failing route/auth snapshot test**

```python
from fastapi.routing import APIRoute

from app.main import app


EXPECTED_SYSTEM_CONFIGURATION_HTTP_ROUTES = [
    ("/api/settings", ("GET",), "get_settings", "app.domains.system_configuration.settings_router.get_settings", ("get_db", "verify_admin_token")),
    ("/api/settings", ("PUT",), "update_settings", "app.domains.system_configuration.settings_router.update_settings", ("get_db", "checker")),
]


def test_system_configuration_route_table_snapshot():
    assert _system_configuration_http_routes() == EXPECTED_SYSTEM_CONFIGURATION_HTTP_ROUTES
```

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_system_configuration_auth_parity.py -q`

Expected: FAIL because endpoints still come from `app.routers.settings`.

- [ ] **Step 2: Add boundary and facade tests**

The tests must assert:

- the spec and plan mention `app.domains.system_configuration`,
  `settings_router.py`, `app.routers.settings`, `/api/settings`,
  `SystemSetting`, `SettingUpdate`, and `system_operations`;
- `app.domains.system_configuration` exports
  `DOMAIN_NAME = "system_configuration"` and
  `PUBLIC_ROUTE_PREFIX = "/api/settings"`;
- `server/app/domains/system_configuration/README.md` documents the facade
  register and cleanup gates;
- `server/app/routers/settings.py` is a thin facade with no `APIRouter(`;
- `app.main` directly imports and includes `settings_router`;
- `system_operations` does not import `system_configuration`;
- legacy and domain module imports resolve to the same object.

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_system_configuration_auth_parity.py server/tests/test_system_configuration_domain_boundary.py server/tests/test_system_configuration_router_facade.py server/tests/test_settings_endpoints.py -q`

Expected: FAIL until `app.domains.system_configuration` and direct main wiring
exist.

### Task 2: Domain Skeleton And Facade Register

**Files:**
- Create: `server/app/domains/system_configuration/__init__.py`
- Create: `server/app/domains/system_configuration/README.md`

- [ ] **Step 1: Add domain metadata**

```python
"""System configuration domain package."""

DOMAIN_NAME = "system_configuration"
PUBLIC_ROUTE_PREFIX = "/api/settings"
```

- [ ] **Step 2: Add README boundary notes**

Document owned `/api/settings` routes, non-owned health/status routes, the
`app.routers.settings` facade, stable model dependencies, and compatibility
cleanup gates.

### Task 3: Router Move With Compatibility Facade

**Files:**
- Create: `server/app/domains/system_configuration/settings_router.py`
- Modify: `server/app/routers/settings.py`

- [ ] **Step 1: Copy the router implementation**

Copy the current contents of `server/app/routers/settings.py` to
`server/app/domains/system_configuration/settings_router.py` without changing
route behavior.

- [ ] **Step 2: Replace legacy router with a module alias**

```python
"""Compatibility facade for system configuration routes.

The implementation now lives in app.domains.system_configuration.settings_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.system_configuration import settings_router as _settings_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _settings_router
globals().update(_settings_router.__dict__)
```

- [ ] **Step 3: Run focused tests**

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_system_configuration_auth_parity.py server/tests/test_system_configuration_domain_boundary.py server/tests/test_system_configuration_router_facade.py server/tests/test_settings_endpoints.py -q`

Expected: Auth parity still fails until `app.main` wires the domain router
directly; facade tests and existing settings endpoint behavior should pass.

- [ ] **Step 4: Commit**

Run: `git commit -m "refactor: move system configuration router into domain"`

### Task 4: Direct App Wiring

**Files:**
- Modify: `server/app/main.py`
- Modify: `server/tests/test_system_configuration_domain_boundary.py`

- [ ] **Step 1: Wire app main to the domain router**

Replace the legacy `settings` router import/include with:

```python
from app.domains.system_configuration import settings_router
app.include_router(settings_router.router)
```

- [ ] **Step 2: Keep legacy facade for old imports**

Do not remove `server/app/routers/settings.py` in this task.

- [ ] **Step 3: Run focused tests**

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_system_configuration_auth_parity.py server/tests/test_system_configuration_domain_boundary.py server/tests/test_system_configuration_router_facade.py server/tests/test_settings_endpoints.py -q`

Expected: PASS.

- [ ] **Step 4: Commit**

Use an isolated Git index for `server/app/main.py` if the real worktree has
unrelated changes, then commit:

Run: `git commit -m "refactor: wire system configuration router from domain"`

### Later Splits

- Split configuration read/write use cases only after route ownership is stable.
- Normalize AI/Pixelle/Seedance configuration consumers under separate plans.
- Keep health/status routes in `system_operations`.

### Verification

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_system_configuration_auth_parity.py server/tests/test_system_configuration_domain_boundary.py server/tests/test_system_configuration_router_facade.py server/tests/test_settings_endpoints.py -q
```

Self-review checklist:

- Every `/api/settings` endpoint module is
  `app.domains.system_configuration.settings_router`.
- `app.routers.settings` and
  `app.domains.system_configuration.settings_router` are the same module object
  during the facade phase.
- `system_operations` remains separate.
- No response shape, route path, route name, auth dependency, masking behavior,
  masked secret skip behavior, or missing-table fallback changed.

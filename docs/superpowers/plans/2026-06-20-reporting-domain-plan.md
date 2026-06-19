# Reporting Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `app.domains.reporting` and move admin stats route ownership behind a compatibility-preserving domain module.

**Architecture:** Keep `app.services.stats_service` unchanged and move only the FastAPI router boundary. Preserve `app.routers.stats` as a thin module alias until import inventory proves it can be removed.

**Tech Stack:** FastAPI `APIRouter`, pytest route snapshots, Python module aliasing via `sys.modules`.

---

### Task 1: Boundary And Route Snapshot

**Files:**
- Create: `server/tests/test_reporting_auth_parity.py`
- Create: `server/tests/test_reporting_domain_boundary.py`
- Create: `server/tests/test_reporting_router_facade.py`

- [ ] **Step 1: Write the failing route/auth snapshot test**

```python
from fastapi.routing import APIRoute

from app.main import app


EXPECTED_REPORTING_HTTP_ROUTES = [
    ("/api/stats/dashboard", ("GET",), "dashboard_summary", "app.domains.reporting.stats_router.dashboard_summary", ("get_db", "verify_admin_token")),
    ("/api/stats/daily", ("GET",), "daily_stats", "app.domains.reporting.stats_router.daily_stats", ("get_db", "verify_admin_token")),
    ("/api/stats/accounts/{account_id}", ("GET",), "account_stats", "app.domains.reporting.stats_router.account_stats", ("get_db", "verify_admin_token")),
    ("/api/stats/realtime", ("GET",), "realtime_stats", "app.domains.reporting.stats_router.realtime_stats", ("get_db", "verify_admin_token")),
]


def test_reporting_route_table_snapshot():
    assert _reporting_http_routes() == EXPECTED_REPORTING_HTTP_ROUTES


def _reporting_http_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/stats"):
            endpoint = f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
            dependency_names = tuple(
                getattr(dep.call, "__name__", repr(dep.call))
                for dep in route.dependant.dependencies
                if dep.call
            )
            routes.append((route.path, tuple(sorted(route.methods)), route.name, endpoint, dependency_names))
    return routes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_reporting_auth_parity.py -q`

Expected: FAIL because endpoints still come from `app.routers.stats` or the
test file is newly introduced before the domain move.

- [ ] **Step 3: Add boundary and facade failing tests**

The tests must assert:

- `docs/superpowers/specs/2026-06-20-reporting-domain-design.md` and this plan mention `app.domains.reporting`, `stats_router.py`, `app.routers.stats`, `/api/stats`, and `/api/device/stats/increment`.
- `app.domains.reporting` exports `DOMAIN_NAME = "reporting"` and `PUBLIC_ROUTE_PREFIX = "/api/stats"`.
- `server/app/domains/reporting/README.md` documents the facade register and cleanup gates.
- `server/app/routers/stats.py` is a thin facade with no `APIRouter(` construction.
- `app.main` directly imports and includes `stats_router`.
- Device stats increment stays under `device_operations`.
- Legacy and domain module imports resolve to the same object.

- [ ] **Step 4: Run tests to verify they fail**

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_reporting_auth_parity.py server/tests/test_reporting_domain_boundary.py server/tests/test_reporting_router_facade.py -q`

Expected: FAIL because `app.domains.reporting` and facade wiring do not exist.

### Task 2: Domain Skeleton And Facade Register

**Files:**
- Create: `server/app/domains/reporting/__init__.py`
- Create: `server/app/domains/reporting/README.md`

- [ ] **Step 1: Add domain metadata**

```python
"""Reporting domain package."""

DOMAIN_NAME = "reporting"
PUBLIC_ROUTE_PREFIX = "/api/stats"
```

- [ ] **Step 2: Add README boundary notes**

Document owned `/api/stats/*` routes, non-owned `/api/device/stats/increment`,
the `app.routers.stats` facade, stable service dependencies, and compatibility
cleanup gates.

- [ ] **Step 3: Run focused tests**

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_reporting_domain_boundary.py -q`

Expected: Some tests still fail until the router move and direct main wiring are
complete.

### Task 3: Router Move With Compatibility Facade

**Files:**
- Create: `server/app/domains/reporting/stats_router.py`
- Modify: `server/app/routers/stats.py`

- [ ] **Step 1: Copy the router implementation**

Copy the current contents of `server/app/routers/stats.py` to
`server/app/domains/reporting/stats_router.py` without changing route behavior.

- [ ] **Step 2: Replace legacy router with a module alias**

```python
"""Compatibility facade for reporting routes.

The implementation now lives in app.domains.reporting.stats_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.reporting import stats_router as _stats_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _stats_router
globals().update(_stats_router.__dict__)
```

- [ ] **Step 3: Run focused tests**

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_reporting_auth_parity.py server/tests/test_reporting_domain_boundary.py server/tests/test_reporting_router_facade.py server/tests/test_stats_api.py -q`

Expected: Auth parity still fails until `app.main` wires the domain router
directly; facade tests and API behavior should pass.

- [ ] **Step 4: Commit**

Run: `git commit -m "refactor: move reporting router into domain"`

### Task 4: Direct App Wiring

**Files:**
- Modify: `server/app/main.py`
- Modify: `server/tests/test_reporting_domain_boundary.py`

- [ ] **Step 1: Wire app main to the domain router**

Replace the legacy `stats` router import/include with:

```python
from app.domains.reporting import stats_router
app.include_router(stats_router.router)
```

- [ ] **Step 2: Keep legacy facade for old imports**

Do not remove `server/app/routers/stats.py` in this task.

- [ ] **Step 3: Run focused tests**

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_reporting_auth_parity.py server/tests/test_reporting_domain_boundary.py server/tests/test_reporting_router_facade.py server/tests/test_stats_api.py server/tests/test_stats_service.py server/tests/test_device_operations_polling_reporting.py -q`

Expected: PASS.

- [ ] **Step 4: Commit**

Use an isolated Git index for `server/app/main.py` if the real worktree has
unrelated changes, then commit:

Run: `git commit -m "refactor: wire reporting router from domain"`

### Later Splits

- Split dashboard read models only after route ownership is stable.
- Split daily stats and account quota query helpers only if the stats router
  gains more behavior.
- Keep `app.services.stats_service` stable until a separate service-split plan
  is approved.

### Verification

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_reporting_auth_parity.py server/tests/test_reporting_domain_boundary.py server/tests/test_reporting_router_facade.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_stats_api.py server/tests/test_stats_service.py server/tests/test_device_operations_polling_reporting.py -q
```

Self-review checklist:

- Every `/api/stats/*` endpoint module is `app.domains.reporting.stats_router`.
- `app.routers.stats` and `app.domains.reporting.stats_router` are the same
  module object during the facade phase.
- `/api/device/stats/increment` remains owned by `device_operations`.
- No response shape, route path, route name, or auth dependency changed.

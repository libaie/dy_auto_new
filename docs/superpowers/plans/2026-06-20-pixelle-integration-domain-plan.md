# Pixelle Integration Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `/api/pixelle/*` and `/api/pixelle-proxy/*` into `app.domains.pixelle_integration` while preserving legacy monkeypatch compatibility.

**Architecture:** This is a facade-first router migration. The current `app.routers.pixelle` code becomes `app.domains.pixelle_integration.pixelle_router`; the old module path becomes a `sys.modules` facade, and `app.main` imports the domain router directly for both `router` and `proxy_router`.

**Tech Stack:** FastAPI, pytest, httpx, PyYAML, SQLAlchemy sessions, existing Pixelle config and auth helpers.

---

## File Structure

- Create `server/app/domains/pixelle_integration/__init__.py`: domain metadata.
- Create `server/app/domains/pixelle_integration/README.md`: owned routes, non-owned services, facade, and cleanup gates.
- Create `server/app/domains/pixelle_integration/pixelle_router.py`: moved implementation from `server/app/routers/pixelle.py`.
- Modify `server/app/routers/pixelle.py`: compatibility facade pointing at the domain module.
- Modify `server/app/main.py`: import and include `pixelle_router.router` and `pixelle_router.proxy_router`.
- Create `server/tests/test_pixelle_integration_domain_boundary.py`: spec, README, facade, main wiring, and import smoke tests.
- Create `server/tests/test_pixelle_integration_router_facade.py`: legacy/domain module identity and router snapshots.
- Create `server/tests/test_pixelle_integration_auth_parity.py`: FastAPI route table snapshot.

The move preserves `PixelleConfigUpdate`, `_serialize_ai_models`,
`_redact_secrets`, `_get_proxy_client`, `_pixelle_headers`, `router`,
`proxy_router`, proxy header stripping, DB-backed Pixelle API key behavior, and
legacy `app.routers.pixelle` monkeypatch compatibility.

### Task 1: Write Spec, Plan, And Red Boundary Tests

**Files:**
- Create: `docs/superpowers/specs/2026-06-20-pixelle-integration-domain-design.md`
- Create: `docs/superpowers/plans/2026-06-20-pixelle-integration-domain-plan.md`
- Create: `server/tests/test_pixelle_integration_domain_boundary.py`
- Create: `server/tests/test_pixelle_integration_router_facade.py`
- Create: `server/tests/test_pixelle_integration_auth_parity.py`

- [ ] **Step 1: Write failing tests**

```python
EXPECTED_PIXELLE_ROUTES = [
    ("GET", "/api/pixelle/config", "get_pixelle_config"),
    ("PUT", "/api/pixelle/config", "update_pixelle_config"),
    ("GET", "/api/pixelle/template-preview/{size}/{filename}", "template_preview_image"),
    ("GET", "/api/pixelle/test-connection", "test_connection"),
]

EXPECTED_PIXELLE_PROXY_ROUTES = [
    ("DELETE", "/api/pixelle-proxy/{path:path}", "proxy_to_pixelle"),
    ("GET", "/api/pixelle-proxy/{path:path}", "proxy_to_pixelle"),
    ("PATCH", "/api/pixelle-proxy/{path:path}", "proxy_to_pixelle"),
    ("POST", "/api/pixelle-proxy/{path:path}", "proxy_to_pixelle"),
    ("PUT", "/api/pixelle-proxy/{path:path}", "proxy_to_pixelle"),
    ("DELETE", "/api/pixelle-proxy/", "proxy_root_to_pixelle"),
    ("GET", "/api/pixelle-proxy/", "proxy_root_to_pixelle"),
    ("PATCH", "/api/pixelle-proxy/", "proxy_root_to_pixelle"),
    ("POST", "/api/pixelle-proxy/", "proxy_root_to_pixelle"),
    ("PUT", "/api/pixelle-proxy/", "proxy_root_to_pixelle"),
]
```

The tests expect `app.domains.pixelle_integration.pixelle_router` to exist,
`app.routers.pixelle` to be a facade, and `app.main` to register both routers
from the domain.

- [ ] **Step 2: Run red tests**

Run from `server/`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pixelle_integration_domain_boundary.py tests/test_pixelle_integration_router_facade.py tests/test_pixelle_integration_auth_parity.py -q
```

Expected: FAIL because `app.domains.pixelle_integration` does not exist and
`app.main` still wires `app.routers.pixelle`.

### Task 2: Move Router Into Domain And Keep Facade

**Files:**
- Create: `server/app/domains/pixelle_integration/__init__.py`
- Create: `server/app/domains/pixelle_integration/README.md`
- Create: `server/app/domains/pixelle_integration/pixelle_router.py`
- Modify: `server/app/routers/pixelle.py`

- [ ] **Step 1: Create domain metadata**

```python
"""Pixelle integration domain package."""

DOMAIN_NAME = "pixelle_integration"
PUBLIC_ROUTE_PREFIX = "/api/pixelle"
PUBLIC_PROXY_PREFIX = "/api/pixelle-proxy"
```

- [ ] **Step 2: Move implementation**

Copy the full current implementation from `server/app/routers/pixelle.py` to
`server/app/domains/pixelle_integration/pixelle_router.py` without changing
route logic, proxy behavior, config serialization, or helper names.

- [ ] **Step 3: Replace legacy module with facade**

```python
"""Compatibility facade for Pixelle integration routes.

The implementation now lives in app.domains.pixelle_integration.pixelle_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.pixelle_integration import pixelle_router as _pixelle_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _pixelle_router
globals().update(_pixelle_router.__dict__)
```

### Task 3: Wire Main Directly To The Domain

**Files:**
- Modify: `server/app/main.py`

- [ ] **Step 1: Update main imports**

Add:

```python
from app.domains.pixelle_integration import pixelle_router
```

Remove `pixelle` from the `from app.routers import ...` import list.

- [ ] **Step 2: Update main include calls**

Replace:

```python
app.include_router(pixelle.router)
app.include_router(pixelle.proxy_router)
```

with:

```python
app.include_router(pixelle_router.router)
app.include_router(pixelle_router.proxy_router)
```

### Task 4: Verify And Commit

**Files:**
- All files above.

- [ ] **Step 1: Run focused tests**

Run from `server/`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pixelle_integration_domain_boundary.py tests/test_pixelle_integration_router_facade.py tests/test_pixelle_integration_auth_parity.py tests/test_pixelle_config_serialization.py tests/test_pixelle_config_security.py tests/test_video_studio_backend_closure.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Commit with isolated `main.py` staging**

Because `server/app/main.py` may contain unrelated local WIP, stage only the
Pixelle import/include changes through an isolated temporary index. Do not
stage unrelated `main.py` changes.

Commit message:

```powershell
git commit -m "refactor: move pixelle integration router into domain"
```

### Self-Review

- The spec covers ownership, non-ownership, compatibility, tests, and cleanup
  gates.
- The plan covers each file and exact verification commands.
- The migration preserves current Pixelle route behavior and monkeypatch paths.

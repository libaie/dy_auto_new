# Quality Audit Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `/api/audit/*` and route-local audit helpers into `app.domains.quality_audit` while preserving legacy monkeypatch compatibility.

**Architecture:** This is a facade-first router migration. The current `app.routers.audit` code becomes `app.domains.quality_audit.audit_router`; the old module path becomes a `sys.modules` facade, `app.main` imports the domain router directly, and production consumers import `_do_audit` from the domain module.

**Tech Stack:** FastAPI, pytest, SQLAlchemy `AuditReport`, existing audit gate and model registry services.

---

## File Structure

- Create `server/app/domains/quality_audit/__init__.py`: domain metadata.
- Create `server/app/domains/quality_audit/README.md`: owned routes, non-owned services, facade, and cleanup gates.
- Create `server/app/domains/quality_audit/audit_router.py`: moved implementation from `server/app/routers/audit.py`.
- Modify `server/app/routers/audit.py`: compatibility facade pointing at the domain module.
- Modify `server/app/main.py`: import and include `audit_router`.
- Modify `server/app/services/video_production_service.py`: import `_do_audit` from the domain module.
- Create `server/tests/test_quality_audit_domain_boundary.py`: spec, README, facade, service import, main wiring, and import smoke tests.
- Create `server/tests/test_quality_audit_router_facade.py`: legacy/domain module identity and router snapshot.
- Create `server/tests/test_quality_audit_auth_parity.py`: FastAPI route table snapshot.

The move preserves `AuditImageRequest`, `AuditReport`, `_do_audit`,
`_audit_openai_compatible`, text-only Bailian payloads, vision-enabled OpenAI
payloads, report listing behavior, and legacy `app.routers.audit` monkeypatch
compatibility.

### Task 1: Write Spec, Plan, And Red Boundary Tests

**Files:**
- Create: `docs/superpowers/specs/2026-06-20-quality-audit-domain-design.md`
- Create: `docs/superpowers/plans/2026-06-20-quality-audit-domain-plan.md`
- Create: `server/tests/test_quality_audit_domain_boundary.py`
- Create: `server/tests/test_quality_audit_router_facade.py`
- Create: `server/tests/test_quality_audit_auth_parity.py`

- [ ] **Step 1: Write failing tests**

```python
EXPECTED_QUALITY_AUDIT_ROUTES = [
    ("POST", "/api/audit/image", "audit_image"),
    ("GET", "/api/audit/reports/{target_type}/{target_id}", "list_reports"),
]
```

The tests expect `app.domains.quality_audit.audit_router` to exist,
`app.routers.audit` to be a facade, `app.main` to register the domain router,
and `video_production_service.py` to import `_do_audit` from the domain.

- [ ] **Step 2: Run red tests**

Run from `server/`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_quality_audit_domain_boundary.py tests/test_quality_audit_router_facade.py tests/test_quality_audit_auth_parity.py -q
```

Expected: FAIL because `app.domains.quality_audit` does not exist and
production wiring still uses `app.routers.audit`.

### Task 2: Move Router Into Domain And Keep Facade

**Files:**
- Create: `server/app/domains/quality_audit/__init__.py`
- Create: `server/app/domains/quality_audit/README.md`
- Create: `server/app/domains/quality_audit/audit_router.py`
- Modify: `server/app/routers/audit.py`

- [ ] **Step 1: Create domain metadata**

```python
"""Quality audit domain package."""

DOMAIN_NAME = "quality_audit"
PUBLIC_ROUTE_PREFIX = "/api/audit"
```

- [ ] **Step 2: Move implementation**

Copy the full current implementation from `server/app/routers/audit.py` to
`server/app/domains/quality_audit/audit_router.py` without changing route logic,
provider payloads, or helper behavior.

- [ ] **Step 3: Replace legacy module with facade**

```python
"""Compatibility facade for quality audit routes.

The implementation now lives in app.domains.quality_audit.audit_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.quality_audit import audit_router as _audit_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _audit_router
globals().update(_audit_router.__dict__)
```

### Task 3: Wire Main And Production Consumers Directly

**Files:**
- Modify: `server/app/main.py`
- Modify: `server/app/services/video_production_service.py`

- [ ] **Step 1: Update main imports**

Add:

```python
from app.domains.quality_audit import audit_router
```

Remove `audit` from the `from app.routers import ...` import list.

- [ ] **Step 2: Update main include**

Replace:

```python
app.include_router(audit.router)
```

with:

```python
app.include_router(audit_router.router)
```

- [ ] **Step 3: Update production `_do_audit` imports**

Replace:

```python
from app.routers.audit import _do_audit
```

with:

```python
from app.domains.quality_audit.audit_router import _do_audit
```

### Task 4: Verify And Commit

**Files:**
- All files above.

- [ ] **Step 1: Run focused tests**

Run from `server/`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_quality_audit_domain_boundary.py tests/test_quality_audit_router_facade.py tests/test_quality_audit_auth_parity.py tests/test_audit_router_payload.py tests/test_video_production_ai_audit_gate.py tests/test_video_production_final_gate.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Commit with isolated WIP-sensitive staging**

Because `server/app/main.py` and `server/app/services/video_production_service.py`
may contain unrelated local WIP, stage only the audit import/include changes for
those files through an isolated temporary index. Do not stage unrelated changes.

Commit message:

```powershell
git commit -m "refactor: move quality audit router into domain"
```

### Self-Review

- The spec covers ownership, non-ownership, compatibility, tests, and cleanup
  gates.
- The plan covers each file and exact verification commands.
- The migration preserves current audit route behavior and monkeypatch paths.

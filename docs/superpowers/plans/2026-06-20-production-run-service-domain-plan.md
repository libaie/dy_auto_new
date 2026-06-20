# Production Run Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move production run orchestration into `video_production` while preserving the legacy service import.

**Architecture:** `app.domains.video_production.production_run_service` owns linked run and episode production orchestration. `app.services.production_run_service` aliases the domain module until callers move to the domain path.

**Tech Stack:** Python, SQLAlchemy ORM, pytest.

---

### Task 1: Inventory Red

**Files:**
- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Remove `production_run_service.py` from the service implementation allowlist**

```python
EXPECTED_NON_FACADE_SERVICE_FILES = {
    "agency_console.py",
    "agency_orchestrator.py",
    "image_creation_service.py",
    "one_sentence_video_service.py",
    "video_agency_team.py",
}
```

Also remove the `"production_run_service.py": "video_production"` entry from
`EXPECTED_SERVICE_DOMAIN_TARGETS`.

- [ ] **Step 2: Verify red**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_service_implementation_inventory.py -q
```

Expected: FAIL with `production_run_service.py` as an extra non-facade service file.

### Task 2: Move Run Orchestration

**Files:**
- Create: `server/app/domains/video_production/production_run_service.py`
- Modify: `server/app/services/production_run_service.py`
- Modify: `server/tests/test_domain_service_import_inventory.py`
- Modify: `server/app/domains/video_production/README.md`
- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Move the implementation**

Move the current implementation from
`server/app/services/production_run_service.py` to
`server/app/domains/video_production/production_run_service.py`.

- [ ] **Step 2: Point migrated dependencies at domain paths**

Use domain imports for production errors, observability, production plan,
AI text artifacts, series planning, script pipeline, storyboard timing, and
run type helpers.

- [ ] **Step 3: Keep `video_production_service` as the only legacy service dependency**

Add this tuple to `EXPECTED_DOMAIN_SERVICE_IMPORTS`:

```python
("server/app/domains/video_production/production_run_service.py", "video_production_service"),
```

- [ ] **Step 4: Replace the legacy service with this facade**

```python
"""Compatibility facade for video production run orchestration."""

from __future__ import annotations

import sys

from app.domains.video_production import production_run_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_domain_module.__name__] = _domain_module
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
```

- [ ] **Step 5: Update README registration**

Add `production_run_service.py` to Current Modules and add this facade row:

```markdown
| `app.services.production_run_service` | `app.domains.video_production.production_run_service` | Keep while series routers, video production router, legacy tests, and `video_production_service` compatibility calls import run orchestration through `app.services`; remove after import inventory is clean. |
```

- [ ] **Step 6: Verify green**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/tests/test_one_sentence_video_run_types.py server/tests/test_video_production_cost_safety.py server/tests/test_series_planning_service.py server/tests/test_pipeline_saved_storyboard_compat.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit target files only**

```powershell
git add -f docs/superpowers/specs/2026-06-20-production-run-service-domain-design.md docs/superpowers/plans/2026-06-20-production-run-service-domain-plan.md server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/app/domains/video_production/production_run_service.py server/app/services/production_run_service.py server/app/domains/video_production/README.md
git commit --only docs/superpowers/specs/2026-06-20-production-run-service-domain-design.md docs/superpowers/plans/2026-06-20-production-run-service-domain-plan.md server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/app/domains/video_production/production_run_service.py server/app/services/production_run_service.py server/app/domains/video_production/README.md -m "refactor: move production run service into domain"
```

# Agency Console Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move agency console read models into `agency_operations` while preserving the legacy service import.

**Architecture:** `app.domains.agency_operations.agency_console` owns console payload construction. `app.services.agency_console` aliases the domain module until callers move to the domain path.

**Tech Stack:** Python, SQLAlchemy ORM, pytest.

---

### Task 1: Inventory Red

**Files:**
- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Remove `agency_console.py` from the service implementation allowlist**

```python
EXPECTED_NON_FACADE_SERVICE_FILES = {
    "agency_orchestrator.py",
    "one_sentence_video_service.py",
    "video_agency_team.py",
}
```

Also remove the `"agency_console.py": "agency_operations"` entry from
`EXPECTED_SERVICE_DOMAIN_TARGETS`.

- [ ] **Step 2: Verify red**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_service_implementation_inventory.py -q
```

Expected: FAIL with `agency_console.py` as an extra non-facade service file.

### Task 2: Move Console Read Model

**Files:**
- Create: `server/app/domains/agency_operations/agency_console.py`
- Modify: `server/app/services/agency_console.py`
- Modify: `server/tests/test_domain_service_import_inventory.py`
- Modify: `server/app/domains/agency_operations/README.md`
- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Move the implementation**

Move the current implementation from `server/app/services/agency_console.py` to
`server/app/domains/agency_operations/agency_console.py`.

- [ ] **Step 2: Point migrated dependencies at domain paths**

Use domain imports for `creative_patch_summary`, `list_experts`, and
`load_manifest`. Keep `agency_orchestrator` and `video_agency_team` as legacy
service imports until those modules move.

- [ ] **Step 3: Register retained legacy imports**

Add these tuples to `EXPECTED_DOMAIN_SERVICE_IMPORTS`:

```python
("server/app/domains/agency_operations/agency_console.py", "agency_orchestrator"),
("server/app/domains/agency_operations/agency_console.py", "video_agency_team"),
```

- [ ] **Step 4: Replace the legacy service with this facade**

```python
"""Compatibility facade for agency console read models."""

from __future__ import annotations

import sys

from app.domains.agency_operations import agency_console as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_domain_module.__name__] = _domain_module
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
```

- [ ] **Step 5: Update README registration**

Add `agency_console.py` to Current Modules and add this facade row:

```markdown
| `app.services.agency_console` | `app.domains.agency_operations.agency_console` | Keep while series read models and legacy tests import console payloads through `app.services`; remove after import inventory is clean. |
```

- [ ] **Step 6: Verify green**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/tests/test_agency_console.py server/tests/test_agency_invocation_models.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit target files only**

```powershell
git add -f docs/superpowers/specs/2026-06-20-agency-console-domain-design.md docs/superpowers/plans/2026-06-20-agency-console-domain-plan.md server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/app/domains/agency_operations/agency_console.py server/app/services/agency_console.py server/app/domains/agency_operations/README.md
git commit --only docs/superpowers/specs/2026-06-20-agency-console-domain-design.md docs/superpowers/plans/2026-06-20-agency-console-domain-plan.md server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/app/domains/agency_operations/agency_console.py server/app/services/agency_console.py server/app/domains/agency_operations/README.md -m "refactor: move agency console into domain"
```

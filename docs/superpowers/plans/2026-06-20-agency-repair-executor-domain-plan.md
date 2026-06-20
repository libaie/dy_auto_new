# Agency Repair Executor Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move agency repair execution into `agency_operations` while preserving the legacy service import.

**Architecture:** `app.domains.agency_operations.agency_repair_executor` owns repair job execution. `app.services.agency_repair_executor` aliases the domain module until production worker code moves to the domain path.

**Tech Stack:** Python, SQLAlchemy ORM, pytest.

---

### Task 1: Inventory Red

**Files:**
- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Remove `agency_repair_executor.py` from the service implementation allowlist**

```python
EXPECTED_NON_FACADE_SERVICE_FILES = {
    "agency_console.py",
    "agency_orchestrator.py",
    "agency_runtime.py",
    "ai_generator.py",
    "image_creation_service.py",
    "one_sentence_video_service.py",
    "production_run_service.py",
    "production_worker_service.py",
    "video_agency_team.py",
}
```

Also remove the `"agency_repair_executor.py": "agency_operations"` entry from
`EXPECTED_SERVICE_DOMAIN_TARGETS`.

- [ ] **Step 2: Verify red**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_service_implementation_inventory.py -q
```

Expected: FAIL with `agency_repair_executor.py` as an extra non-facade service file.

### Task 2: Move Executor

**Files:**
- Create: `server/app/domains/agency_operations/agency_repair_executor.py`
- Modify: `server/app/services/agency_repair_executor.py`
- Modify: `server/app/domains/agency_operations/README.md`
- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Move the implementation**

Move the current implementation from
`server/app/services/agency_repair_executor.py` to
`server/app/domains/agency_operations/agency_repair_executor.py`.

- [ ] **Step 2: Point domain imports at domain helpers**

Use these imports in the moved file:

```python
from app.domains.agency_operations.agency_repair_contracts import AUTO_REPAIR_STAGE
from app.domains.video_production.production_action_result import ProductionActionResult
from app.domains.video_production.production_queue_service import enqueue_job
from app.domains.video_production.production_status import (
    JOB_LEASED,
    JOB_QUEUED,
    JOB_RETRY_WAIT,
    JOB_RUNNING,
    SEGMENT_IMAGE_QUEUED,
)
```

- [ ] **Step 3: Replace the legacy service with this facade**

```python
"""Compatibility facade for agency repair execution."""

from __future__ import annotations

import sys

from app.domains.agency_operations import agency_repair_executor as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_domain_module.__name__] = _domain_module
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
```

- [ ] **Step 4: Update README registration**

Add `agency_repair_executor.py` to Current Modules and add this facade row:

```markdown
| `app.services.agency_repair_executor` | `app.domains.agency_operations.agency_repair_executor` | Keep while dirty production worker code imports repair execution from `app.services`; remove after import inventory is clean. |
```

- [ ] **Step 5: Verify green**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/tests/test_agency_repair_executor.py server/tests/test_agency_repair_worker.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit target files only**

```powershell
git add -f docs/superpowers/specs/2026-06-20-agency-repair-executor-domain-design.md docs/superpowers/plans/2026-06-20-agency-repair-executor-domain-plan.md server/tests/test_service_implementation_inventory.py server/app/domains/agency_operations/agency_repair_executor.py server/app/services/agency_repair_executor.py server/app/domains/agency_operations/README.md
git commit --only docs/superpowers/specs/2026-06-20-agency-repair-executor-domain-design.md docs/superpowers/plans/2026-06-20-agency-repair-executor-domain-plan.md server/tests/test_service_implementation_inventory.py server/app/domains/agency_operations/agency_repair_executor.py server/app/services/agency_repair_executor.py server/app/domains/agency_operations/README.md -m "refactor: move agency repair executor into domain"
```

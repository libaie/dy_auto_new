# Agency Orchestrator Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move staged agency review orchestration into `agency_operations` while preserving the legacy service import.

**Architecture:** `app.domains.agency_operations.agency_orchestrator` owns `STAGE_DAG` and `AgencyOrchestrator`. `app.services.agency_orchestrator` aliases the domain module until service callers move to the domain path.

**Tech Stack:** Python, SQLAlchemy ORM, pytest.

---

### Task 1: Inventory Red

**Files:**
- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Remove `agency_orchestrator.py` from the service implementation allowlist**

```python
EXPECTED_NON_FACADE_SERVICE_FILES = {
    "one_sentence_video_service.py",
    "video_agency_team.py",
}
```

Also remove the `"agency_orchestrator.py": "agency_operations"` entry from
`EXPECTED_SERVICE_DOMAIN_TARGETS`.

- [ ] **Step 2: Verify red**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_service_implementation_inventory.py -q
```

Expected: FAIL with `agency_orchestrator.py` as an extra non-facade service file.

### Task 2: Move Orchestrator

**Files:**
- Create: `server/app/domains/agency_operations/agency_orchestrator.py`
- Modify: `server/app/services/agency_orchestrator.py`
- Modify: domain callers that currently import `app.services.agency_orchestrator`
- Modify: `server/tests/test_domain_service_import_inventory.py`
- Modify: `server/app/domains/agency_operations/README.md`
- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Move the implementation**

Move the current implementation from `server/app/services/agency_orchestrator.py`
to `server/app/domains/agency_operations/agency_orchestrator.py`.

- [ ] **Step 2: Point migrated dependencies at domain paths**

Use domain imports for agency manifest, agency persistence, agency runtime, and
agency debate audit.

- [ ] **Step 3: Move domain callers to the new path**

Update domain files that import `AgencyOrchestrator`, `STAGE_DAG`, or
`_hash_context` from `app.services.agency_orchestrator` to import from
`app.domains.agency_operations.agency_orchestrator`.

- [ ] **Step 4: Replace the legacy service with this facade**

```python
"""Compatibility facade for agency orchestration."""

from __future__ import annotations

import sys

from app.domains.agency_operations import agency_orchestrator as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_domain_module.__name__] = _domain_module
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
```

- [ ] **Step 5: Verify green**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/tests/test_agency_orchestrator.py server/tests/test_agency_console.py server/tests/test_agency_multimodal_review.py server/tests/test_script_pipeline.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit target files only**

```powershell
git add -f docs/superpowers/specs/2026-06-20-agency-orchestrator-domain-design.md docs/superpowers/plans/2026-06-20-agency-orchestrator-domain-plan.md server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/app/domains/agency_operations/agency_orchestrator.py server/app/services/agency_orchestrator.py server/app/domains/agency_operations/README.md server/app/domains/director_planning/README.md server/app/domains/agency_operations/agency_console.py server/app/domains/agency_operations/agency_debate_audit.py server/app/domains/agency_operations/agency_multimodal_review.py server/app/domains/ai_video_series/style_lock.py server/app/domains/director_planning/director_router.py server/app/domains/script_pipeline/pipeline_router.py server/app/domains/script_pipeline/script_pipeline_service.py
git commit --only docs/superpowers/specs/2026-06-20-agency-orchestrator-domain-design.md docs/superpowers/plans/2026-06-20-agency-orchestrator-domain-plan.md server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/app/domains/agency_operations/agency_orchestrator.py server/app/services/agency_orchestrator.py server/app/domains/agency_operations/README.md server/app/domains/director_planning/README.md server/app/domains/agency_operations/agency_console.py server/app/domains/agency_operations/agency_debate_audit.py server/app/domains/agency_operations/agency_multimodal_review.py server/app/domains/ai_video_series/style_lock.py server/app/domains/director_planning/director_router.py server/app/domains/script_pipeline/pipeline_router.py server/app/domains/script_pipeline/script_pipeline_service.py -m "refactor: move agency orchestrator into domain"
```

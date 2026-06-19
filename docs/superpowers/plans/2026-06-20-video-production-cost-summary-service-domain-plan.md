# Video Production Cost Summary Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move video production cost summary read logic into the video
production domain while preserving old service imports.

**Architecture:** The implementation lives in
`app.domains.video_production.production_cost_summary_service`.
`app.services.production_cost_summary_service` becomes a `sys.modules` facade so
old callers and monkeypatches resolve to the same module object.

**Tech Stack:** Python, pytest.

---

## File Structure

- Create:
  `server/app/domains/video_production/production_cost_summary_service.py`
  - Owns `_ZERO_RESERVATION_COSTS`, `_ACTIVE_RESERVATION_STATUSES`, and
    `get_run_costs`.
- Modify: `server/app/services/production_cost_summary_service.py`
  - Becomes a thin compatibility facade.
- Modify: `server/app/domains/video_production/video_production_router.py`
  - Imports `get_run_costs` from the domain helper.
- Modify: `server/app/domains/video_production/README.md`
  - Documents cost summary service ownership, facade mapping, and cleanup
    gates.
- Create:
  `server/tests/test_video_production_cost_summary_service_facade.py`
  - Proves cost summary boundary and compatibility.

### Task 1: Red Boundary Test

**Files:**

- Create: `server/tests/test_video_production_cost_summary_service_facade.py`
- Create:
  `docs/superpowers/specs/2026-06-20-video-production-cost-summary-service-domain-design.md`
- Create:
  `docs/superpowers/plans/2026-06-20-video-production-cost-summary-service-domain-plan.md`

- [ ] **Step 1: Write the failing test**

Create tests asserting the domain cost summary file exists, the legacy module is
a facade, old and new imports are the same module object, the moved helper uses
the domain state contract import, the domain router imports the helper directly,
and README cleanup gates document the facade.

- [ ] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_cost_summary_service_facade.py -q
```

Expected: FAIL because the domain cost summary service does not exist yet, the
old service file still contains helper implementation, the router still imports
the legacy path, and README does not register the facade.

### Task 2: Move The Cost Summary Service

**Files:**

- Create:
  `server/app/domains/video_production/production_cost_summary_service.py`
- Modify: `server/app/services/production_cost_summary_service.py`
- Modify: `server/app/domains/video_production/video_production_router.py`

- [ ] **Step 1: Copy the implementation**

Copy the current contents of
`server/app/services/production_cost_summary_service.py` into
`server/app/domains/video_production/production_cost_summary_service.py`.

- [ ] **Step 2: Use domain state contract imports**

Change the moved implementation to import cost status constants from
`app.domains.video_production.production_state_contract`.

- [ ] **Step 3: Replace the legacy service with a facade**

Use this facade shape:

```python
"""Compatibility facade for video production cost summary helpers.

The implementation now lives in app.domains.video_production.production_cost_summary_service.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.video_production import production_cost_summary_service as _production_cost_summary_service

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _production_cost_summary_service
globals().update(_production_cost_summary_service.__dict__)
```

- [ ] **Step 4: Update domain router import**

Change `video_production_router.py` to import `get_run_costs` from
`app.domains.video_production.production_cost_summary_service`.

### Task 3: Update Docs

**Files:**

- Modify: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Update README**

Record `app.services.production_cost_summary_service` as a facade targeting
`app.domains.video_production.production_cost_summary_service`, and add a
cleanup gate requiring only compatibility tests, migration docs, or service
modules whose domains have not moved yet to reference the legacy path.

### Task 4: Verify And Commit

**Files:**

- All files listed above.

- [ ] **Step 1: Run the new boundary test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_cost_summary_service_facade.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run focused regression**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_cost_summary_service_facade.py server/tests/test_provider_cost_reservation_service.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Commit only touched files**

Use an isolated Git index if the working tree contains unrelated WIP. Commit
message:

```text
refactor: move production cost summary into domain
```

# Video Production State Contract Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move video production state constants and transition rules into the
video production domain while preserving old service imports.

**Architecture:** The implementation lives in
`app.domains.video_production.production_state_contract`.
`app.services.production_state_contract` becomes a `sys.modules` facade so old
callers and monkeypatches resolve to the same module object.

**Tech Stack:** Python, pytest.

---

## File Structure

- Create: `server/app/domains/video_production/production_state_contract.py`
  - Owns provider task constants such as `PROVIDER_TASK_RESERVED`, cost status
    constants such as `COST_ACTIVE_UNSUBMITTED`, `asset_is_reviewable`,
    `provider_task_is_active`, and `validate_transition`.
- Modify: `server/app/services/production_state_contract.py`
  - Becomes a thin compatibility facade.
- Modify: `server/app/domains/video_production/README.md`
  - Documents state contract ownership, facade mapping, and cleanup gates.
- Create: `server/tests/test_video_production_state_contract_facade.py`
  - Proves state contract boundary and compatibility.

### Task 1: Red Boundary Test

**Files:**

- Create: `server/tests/test_video_production_state_contract_facade.py`
- Create:
  `docs/superpowers/specs/2026-06-20-video-production-state-contract-domain-design.md`
- Create:
  `docs/superpowers/plans/2026-06-20-video-production-state-contract-domain-plan.md`

- [ ] **Step 1: Write the failing test**

Create tests asserting the domain contract file exists, the legacy module is a
facade, old and new imports are the same module object, and README cleanup gates
document the facade.

- [ ] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_state_contract_facade.py -q
```

Expected: FAIL because the domain contract does not exist yet, the old service
file still contains status constants and helper functions, and README does not
register the facade.

### Task 2: Move The State Contract

**Files:**

- Create: `server/app/domains/video_production/production_state_contract.py`
- Modify: `server/app/services/production_state_contract.py`

- [ ] **Step 1: Copy the implementation**

Copy the current contents of `server/app/services/production_state_contract.py`
into `server/app/domains/video_production/production_state_contract.py` without
changing behavior.

- [ ] **Step 2: Replace the legacy service with a facade**

Use this facade shape:

```python
"""Compatibility facade for video production state contract helpers.

The implementation now lives in app.domains.video_production.production_state_contract.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.video_production import production_state_contract as _production_state_contract

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _production_state_contract
globals().update(_production_state_contract.__dict__)
```

### Task 3: Update Docs

**Files:**

- Modify: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Update README**

Record `app.services.production_state_contract` as a facade targeting
`app.domains.video_production.production_state_contract`, and add a cleanup gate
requiring only compatibility tests, migration docs, or service modules whose
domains have not moved yet to reference the legacy path.

### Task 4: Verify And Commit

**Files:**

- All files listed above.

- [ ] **Step 1: Run the new boundary test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_state_contract_facade.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run focused regression**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_state_contract_facade.py server/tests/test_video_production_boundary_models.py server/tests/test_provider_stage_executor.py server/tests/test_provider_cost_reservation_service.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Commit only touched files**

Use an isolated Git index if the working tree contains unrelated WIP. Commit
message:

```text
refactor: move production state contract into domain
```

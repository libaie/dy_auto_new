# Video Production Status Contract Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move video production status constants into the video production
domain while preserving old service imports.

**Architecture:** The implementation lives in
`app.domains.video_production.production_status`.
`app.services.production_status` becomes a `sys.modules` facade so old callers
and monkeypatches resolve to the same module object.

**Tech Stack:** Python, pytest.

---

## File Structure

- Create: `server/app/domains/video_production/production_status.py`
  - Owns plan, job, segment, stage, continuity, and reference status constants.
  - Representative constants include `PLAN_DRAFT`, `JOB_QUEUED`,
    `SEGMENT_IMAGE_QUEUED`, `STAGE_IMAGE_GENERATION`,
    `CONTINUITY_NARRATIVE_CUT`, and `REFERENCE_CHARACTER_ANCHOR`.
- Modify: `server/app/services/production_status.py`
  - Becomes a thin compatibility facade.
- Modify: `server/app/domains/video_production/production_cost_service.py`
  - Imports status constants from the domain helper.
- Modify: `server/app/domains/video_production/README.md`
  - Documents production status ownership, facade mapping, and cleanup gates.
- Create: `server/tests/test_video_production_status_contract_facade.py`
  - Proves production status boundary and compatibility.

### Task 1: Red Boundary Test

**Files:**

- Create: `server/tests/test_video_production_status_contract_facade.py`
- Create:
  `docs/superpowers/specs/2026-06-20-video-production-status-contract-domain-design.md`
- Create:
  `docs/superpowers/plans/2026-06-20-video-production-status-contract-domain-plan.md`

- [ ] **Step 1: Write the failing test**

Create tests asserting the domain production status file exists, the legacy
module is a facade, old and new imports are the same module object, migrated
domain modules import the domain status path directly, and README cleanup gates
document the facade.

- [ ] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_status_contract_facade.py -q
```

Expected: FAIL because the domain production status file does not exist yet, the
old service file still contains constants, `production_cost_service.py` still
imports the legacy path, and README does not register the facade.

### Task 2: Move The Status Contract

**Files:**

- Create: `server/app/domains/video_production/production_status.py`
- Modify: `server/app/services/production_status.py`
- Modify: `server/app/domains/video_production/production_cost_service.py`

- [ ] **Step 1: Copy the implementation**

Copy the current contents of `server/app/services/production_status.py` into
`server/app/domains/video_production/production_status.py`.

- [ ] **Step 2: Replace the legacy service with a facade**

Use this facade shape:

```python
"""Compatibility facade for video production status constants.

The implementation now lives in app.domains.video_production.production_status.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.video_production import production_status as _production_status

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _production_status
globals().update(_production_status.__dict__)
```

- [ ] **Step 3: Update migrated domain consumers**

Change `server/app/domains/video_production/production_cost_service.py` to
import `JOB_BLOCKED`, `JOB_QUEUED`, `JOB_RETRY_WAIT`, and `PLAN_BLOCKED` from
`app.domains.video_production.production_status`.

### Task 3: Update Docs

**Files:**

- Modify: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Update README**

Record `app.services.production_status` as a facade targeting
`app.domains.video_production.production_status`, and add a cleanup gate
requiring only compatibility tests, migration docs, approved cross-domain
consumers, or service modules whose domains have not moved yet to reference the
legacy path.

### Task 4: Verify And Commit

**Files:**

- All files listed above.

- [ ] **Step 1: Run the new boundary test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_status_contract_facade.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run focused regression**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_status_contract_facade.py server/tests/test_production_cost_service.py server/tests/test_production_queue_service.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Commit only touched files**

Use an isolated Git index if the working tree contains unrelated WIP. Commit
message:

```text
refactor: move production status constants into domain
```

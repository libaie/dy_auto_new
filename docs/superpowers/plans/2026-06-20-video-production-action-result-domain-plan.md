# Video Production Action Result Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move video production action result serialization into the video
production domain while preserving old service imports.

**Architecture:** The implementation lives in
`app.domains.video_production.production_action_result`.
`app.services.production_action_result` becomes a `sys.modules` facade so old
callers and monkeypatches resolve to the same module object.

**Tech Stack:** Python, dataclasses, pytest.

---

## File Structure

- Create: `server/app/domains/video_production/production_action_result.py`
  - Owns `ProductionActionResult` and `_serialize_code`.
- Modify: `server/app/services/production_action_result.py`
  - Becomes a thin compatibility facade.
- Modify: moved domain helper
  - Imports `ProductionErrorCode` from
    `app.domains.video_production.production_errors`.
- Modify: `server/app/domains/video_production/README.md`
  - Documents action result ownership, facade mapping, and cleanup gates.
- Create: `server/tests/test_video_production_action_result_facade.py`
  - Proves action result boundary and compatibility.

### Task 1: Red Boundary Test

**Files:**

- Create: `server/tests/test_video_production_action_result_facade.py`
- Create:
  `docs/superpowers/specs/2026-06-20-video-production-action-result-domain-design.md`
- Create:
  `docs/superpowers/plans/2026-06-20-video-production-action-result-domain-plan.md`

- [ ] **Step 1: Write the failing test**

Create tests asserting the domain helper file exists, the legacy module is a
facade, old and new imports are the same module object, the moved helper imports
domain production errors, and README cleanup gates document the facade.

- [ ] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_action_result_facade.py -q
```

Expected: FAIL because the domain helper does not exist yet, the old helper file
still contains `ProductionActionResult`, and the helper still imports
`app.services.production_errors`.

### Task 2: Move The Action Result Helper

**Files:**

- Create: `server/app/domains/video_production/production_action_result.py`
- Modify: `server/app/services/production_action_result.py`

- [ ] **Step 1: Copy the implementation**

Copy the current contents of `server/app/services/production_action_result.py`
into `server/app/domains/video_production/production_action_result.py` without
changing behavior.

- [ ] **Step 2: Replace the legacy helper with a facade**

Use this facade shape:

```python
"""Compatibility facade for video production action result helpers.

The implementation now lives in app.domains.video_production.production_action_result.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.video_production import production_action_result as _production_action_result

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _production_action_result
globals().update(_production_action_result.__dict__)
```

### Task 3: Update Domain Import And Docs

**Files:**

- Modify: `server/app/domains/video_production/production_action_result.py`
- Modify: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Change moved helper import**

Replace `from app.services.production_errors import ProductionErrorCode` with
`from app.domains.video_production.production_errors import ProductionErrorCode`.

- [ ] **Step 2: Update README**

Record `app.services.production_action_result` as a facade targeting
`app.domains.video_production.production_action_result`, and add a cleanup gate
requiring only compatibility tests, migration docs, or service modules whose
domains have not moved yet to reference the legacy path.

### Task 4: Verify And Commit

**Files:**

- All files listed above.

- [ ] **Step 1: Run the new boundary test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_action_result_facade.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run focused regression**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_action_result_facade.py server/tests/test_video_production_boundary_models.py server/tests/test_provider_stage_executor.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Commit only touched files**

Use an isolated Git index if the working tree contains unrelated WIP. Commit
message:

```text
refactor: move production action result into domain
```

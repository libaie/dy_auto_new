# Video Production Error Helper Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move video production error contract helpers into the video production
domain while preserving old service imports.

**Architecture:** The implementation lives in
`app.domains.video_production.production_errors`.
`app.services.production_errors` becomes a `sys.modules` facade so old callers
and monkeypatches resolve to the same module object.

**Tech Stack:** Python, FastAPI-facing error payloads, pytest.

---

## File Structure

- Create: `server/app/domains/video_production/production_errors.py`
  - Owns `ProductionErrorCode`, `ProductionRepairableError`, and
    `to_http_detail`.
- Modify: `server/app/services/production_errors.py`
  - Becomes a thin compatibility facade.
- Modify: `server/app/domains/video_production/video_production_router.py`
  - Imports error helpers from the domain path.
- Modify: `server/app/domains/video_production/README.md`
  - Documents error helper ownership, facade mapping, and cleanup gates.
- Create: `server/tests/test_video_production_error_helper_facade.py`
  - Proves error helper boundary and compatibility.

### Task 1: Red Boundary Test

**Files:**

- Create: `server/tests/test_video_production_error_helper_facade.py`
- Create:
  `docs/superpowers/specs/2026-06-20-video-production-error-helper-domain-design.md`
- Create:
  `docs/superpowers/plans/2026-06-20-video-production-error-helper-domain-plan.md`

- [ ] **Step 1: Write the failing test**

Create tests asserting the domain helper file exists, the legacy module is a
facade, old and new imports are the same module object, the domain router
imports the domain path, and README cleanup gates document the facade.

- [ ] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_error_helper_facade.py -q
```

Expected: FAIL because the domain helper does not exist yet, the old service
file still contains `ProductionErrorCode`, and the domain router still imports
`app.services.production_errors`.

### Task 2: Move The Error Helper

**Files:**

- Create: `server/app/domains/video_production/production_errors.py`
- Modify: `server/app/services/production_errors.py`

- [ ] **Step 1: Copy the implementation**

Copy the current contents of `server/app/services/production_errors.py` into
`server/app/domains/video_production/production_errors.py` without changing
behavior.

- [ ] **Step 2: Replace the legacy service with a facade**

Use this facade shape:

```python
"""Compatibility facade for video production error helpers.

The implementation now lives in app.domains.video_production.production_errors.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.video_production import production_errors as _production_errors

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _production_errors
globals().update(_production_errors.__dict__)
```

### Task 3: Update Domain Import And Docs

**Files:**

- Modify: `server/app/domains/video_production/video_production_router.py`
- Modify: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Change router import**

Replace
`from app.services.production_errors import ProductionErrorCode, ProductionRepairableError, to_http_detail`
with
`from app.domains.video_production.production_errors import ProductionErrorCode, ProductionRepairableError, to_http_detail`.

- [ ] **Step 2: Update README**

Record `app.services.production_errors` as a facade targeting
`app.domains.video_production.production_errors`, and add a cleanup gate
requiring only compatibility tests, migration docs, or service modules whose
domains have not moved yet to reference the legacy path.

### Task 4: Verify And Commit

**Files:**

- All files listed above.

- [ ] **Step 1: Run the new boundary test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_error_helper_facade.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run focused regression**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_error_helper_facade.py server/tests/test_video_production_named_errors.py server/tests/test_video_production_boundary_models.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Commit only touched files**

Use an isolated Git index if the working tree contains unrelated WIP. Commit
message:

```text
refactor: move production error helper into domain
```

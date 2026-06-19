# Video Production Run Types Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move video production run type constants and helper functions into the
video production domain while preserving old service imports.

**Architecture:** The implementation lives in
`app.domains.video_production.video_production_run_types`.
`app.services.video_production_run_types` becomes a `sys.modules` facade so old
callers and monkeypatches resolve to the same module object.

**Tech Stack:** Python, pytest.

---

## File Structure

- Create: `server/app/domains/video_production/video_production_run_types.py`
  - Owns `REAL_SHORT_E2E`, `MOCK_SERIES_SCALE`, `LEGACY_EPISODE_RUN`,
    `ALLOWED_RUN_TYPES`, `REAL_PROVIDER_RUN_TYPES`, `MOCK_RUN_TYPES`,
    `validate_run_type`, `get_run_type`, `set_run_type`, `assert_run_type`,
    `is_real_provider_run`, and `is_mock_scale_run`.
- Modify: `server/app/services/video_production_run_types.py`
  - Becomes a thin compatibility facade.
- Modify: `server/app/domains/video_production/video_production_router.py`
  - Imports run type helpers from the domain contract.
- Modify: `server/app/domains/video_production/production_review_service.py`
  - Imports run type helpers from the domain contract.
- Modify: `server/app/domains/video_production/README.md`
  - Documents run type ownership, facade mapping, and cleanup gates.
- Create: `server/tests/test_video_production_run_types_facade.py`
  - Proves run type boundary and compatibility.

### Task 1: Red Boundary Test

**Files:**

- Create: `server/tests/test_video_production_run_types_facade.py`
- Create:
  `docs/superpowers/specs/2026-06-20-video-production-run-types-domain-design.md`
- Create:
  `docs/superpowers/plans/2026-06-20-video-production-run-types-domain-plan.md`

- [ ] **Step 1: Write the failing test**

Create tests asserting the domain run type file exists, the legacy module is a
facade, old and new imports are the same module object, migrated domain modules
import the domain run type path directly, and README cleanup gates document the
facade.

- [ ] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_run_types_facade.py -q
```

Expected: FAIL because the domain run type file does not exist yet, the old
service file still contains constants/functions, domain modules still import the
legacy path, and README does not register the facade.

### Task 2: Move The Run Type Contract

**Files:**

- Create: `server/app/domains/video_production/video_production_run_types.py`
- Modify: `server/app/services/video_production_run_types.py`
- Modify: `server/app/domains/video_production/video_production_router.py`
- Modify: `server/app/domains/video_production/production_review_service.py`

- [ ] **Step 1: Copy the implementation**

Copy the current contents of `server/app/services/video_production_run_types.py`
into `server/app/domains/video_production/video_production_run_types.py`.

- [ ] **Step 2: Replace the legacy service with a facade**

Use this facade shape:

```python
"""Compatibility facade for video production run type helpers.

The implementation now lives in app.domains.video_production.video_production_run_types.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.video_production import video_production_run_types as _video_production_run_types

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _video_production_run_types
globals().update(_video_production_run_types.__dict__)
```

- [ ] **Step 3: Update migrated domain consumers**

Change `video_production_router.py` and `production_review_service.py` to import
run type helpers from `app.domains.video_production.video_production_run_types`.

### Task 3: Update Docs

**Files:**

- Modify: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Update README**

Record `app.services.video_production_run_types` as a facade targeting
`app.domains.video_production.video_production_run_types`, and add a cleanup
gate requiring only compatibility tests, migration docs, or service modules
whose domains have not moved yet to reference the legacy path.

### Task 4: Verify And Commit

**Files:**

- All files listed above.

- [ ] **Step 1: Run the new boundary test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_run_types_facade.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run focused regression**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_run_types_facade.py server/tests/test_video_production_run_type.py server/tests/test_production_bulk_review.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Commit only touched files**

Use an isolated Git index if the working tree contains unrelated WIP. Commit
message:

```text
refactor: move video production run types into domain
```

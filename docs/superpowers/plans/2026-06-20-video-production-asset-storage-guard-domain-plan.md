# Video Production Asset Storage Guard Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move video production asset persistence guard logic into the video
production domain while preserving old service imports and monkeypatch paths.

**Architecture:** The implementation lives in
`app.domains.video_production.asset_storage_guard`.
`app.services.asset_storage_guard` becomes a `sys.modules` facade so old callers
and monkeypatches resolve to the same module object.

**Tech Stack:** Python, pytest.

---

## File Structure

- Create: `server/app/domains/video_production/asset_storage_guard.py`
  - Owns `ALLOWED_PROVIDER_SCHEMES`, `ALLOWED_IMAGE_MAGIC`,
    `ALLOWED_VIDEO_MAGIC`, and `persist_provider_asset`.
- Modify: `server/app/services/asset_storage_guard.py`
  - Becomes a thin compatibility facade.
- Modify: `server/app/domains/video_production/video_production_router.py`
  - Imports `persist_provider_asset` from the domain helper.
- Modify: `server/app/domains/video_production/README.md`
  - Documents asset storage guard ownership, facade mapping, and cleanup gates.
- Create:
  `server/tests/test_video_production_asset_storage_guard_facade.py`
  - Proves storage guard boundary and compatibility.

### Task 1: Red Boundary Test

**Files:**

- Create: `server/tests/test_video_production_asset_storage_guard_facade.py`
- Create:
  `docs/superpowers/specs/2026-06-20-video-production-asset-storage-guard-domain-design.md`
- Create:
  `docs/superpowers/plans/2026-06-20-video-production-asset-storage-guard-domain-plan.md`

- [ ] **Step 1: Write the failing test**

Create tests asserting the domain storage guard file exists, the legacy module
is a facade, old and new imports are the same module object, legacy monkeypatch
access to `httpx.stream` remains viable, the moved helper uses the domain
production errors import, the domain router imports the helper directly, and
README cleanup gates document the facade.

- [ ] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_asset_storage_guard_facade.py -q
```

Expected: FAIL because the domain storage guard does not exist yet, the old
service file still contains helper implementation, the router still imports the
legacy path, and README does not register the facade.

### Task 2: Move The Storage Guard

**Files:**

- Create: `server/app/domains/video_production/asset_storage_guard.py`
- Modify: `server/app/services/asset_storage_guard.py`
- Modify: `server/app/domains/video_production/video_production_router.py`

- [ ] **Step 1: Copy the implementation**

Copy the current contents of `server/app/services/asset_storage_guard.py` into
`server/app/domains/video_production/asset_storage_guard.py`.

- [ ] **Step 2: Use domain production error imports**

Change the moved implementation to import `ProductionErrorCode` and
`ProductionRepairableError` from
`app.domains.video_production.production_errors`.

- [ ] **Step 3: Replace the legacy service with a facade**

Use this facade shape:

```python
"""Compatibility facade for video production asset storage guard helpers.

The implementation now lives in app.domains.video_production.asset_storage_guard.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.video_production import asset_storage_guard as _asset_storage_guard

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _asset_storage_guard
globals().update(_asset_storage_guard.__dict__)
```

- [ ] **Step 4: Update domain router import**

Change `video_production_router.py` to import `persist_provider_asset` from
`app.domains.video_production.asset_storage_guard`.

### Task 3: Update Docs

**Files:**

- Modify: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Update README**

Record `app.services.asset_storage_guard` as a facade targeting
`app.domains.video_production.asset_storage_guard`, and add a cleanup gate
requiring only compatibility tests, migration docs, or service modules whose
domains have not moved yet to reference the legacy path.

### Task 4: Verify And Commit

**Files:**

- All files listed above.

- [ ] **Step 1: Run the new boundary test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_asset_storage_guard_facade.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run focused regression**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_asset_storage_guard_facade.py server/tests/test_asset_storage_guard.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Commit only touched files**

Use an isolated Git index if the working tree contains unrelated WIP. Commit
message:

```text
refactor: move asset storage guard into domain
```

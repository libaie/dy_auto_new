# Creative Library Reference Asset Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move character and scene reference asset generation into the creative library domain while preserving old service imports.

**Architecture:** The implementation lives in `app.domains.creative_library.reference_asset_service`. `app.services.reference_asset_service` becomes a `sys.modules` facade so old callers and monkeypatches resolve to the same module object.

**Tech Stack:** Python, SQLAlchemy ORM, FastAPI route modules, pytest.

---

## File Structure

- Create: `server/app/domains/creative_library/reference_asset_service.py`
  - Owns `ReferenceAssetError`, `reference_url_is_usable`, `generate_reference_url`, `generate_character_reference_images`, and `generate_scene_reference_images`.
- Modify: `server/app/services/reference_asset_service.py`
  - Becomes a thin compatibility facade.
- Modify: `server/app/domains/creative_library/characters_router.py`
  - Imports the reference asset service from the domain path.
- Modify: `server/app/domains/creative_library/scenes_router.py`
  - Imports the reference asset service from the domain path.
- Modify: `server/app/domains/ai_video_series/style_lock.py`
  - Imports the reference asset service from the domain path.
- Modify: `server/app/domains/ai_video_series/read_models.py`
  - Imports the reference URL helper from the domain path.
- Modify: `server/app/domains/creative_library/README.md`
  - Documents service ownership, facade mapping, and cleanup gates.
- Create: `server/tests/test_creative_library_reference_asset_service_facade.py`
  - Proves service boundary and compatibility.

### Task 1: Red Boundary Test

**Files:**

- Create: `server/tests/test_creative_library_reference_asset_service_facade.py`
- Create: `docs/superpowers/specs/2026-06-20-creative-library-reference-asset-service-domain-design.md`
- Create: `docs/superpowers/plans/2026-06-20-creative-library-reference-asset-service-domain-plan.md`

- [ ] **Step 1: Write the failing test**

Create tests asserting the domain service file exists, the legacy module is a facade, old and new imports are the same module object, domain-owned modules import the domain path, and README cleanup gates document the facade.

- [ ] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_creative_library_reference_asset_service_facade.py -q
```

Expected: FAIL because `server/app/domains/creative_library/reference_asset_service.py` does not exist yet, the old service file still contains `class ReferenceAssetError`, and domain-owned modules still import `app.services.reference_asset_service`.

### Task 2: Move The Service

**Files:**

- Create: `server/app/domains/creative_library/reference_asset_service.py`
- Modify: `server/app/services/reference_asset_service.py`

- [ ] **Step 1: Copy the implementation**

Copy the current contents of `server/app/services/reference_asset_service.py` into `server/app/domains/creative_library/reference_asset_service.py` without changing behavior.

- [ ] **Step 2: Replace the legacy service with a facade**

Use this facade shape:

```python
"""Compatibility facade for creative library reference asset services.

The implementation now lives in app.domains.creative_library.reference_asset_service.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.creative_library import reference_asset_service as _reference_asset_service

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _reference_asset_service
globals().update(_reference_asset_service.__dict__)
```

### Task 3: Update Domain Imports And Docs

**Files:**

- Modify: `server/app/domains/creative_library/characters_router.py`
- Modify: `server/app/domains/creative_library/scenes_router.py`
- Modify: `server/app/domains/ai_video_series/style_lock.py`
- Modify: `server/app/domains/ai_video_series/read_models.py`
- Modify: `server/app/domains/creative_library/README.md`

- [ ] **Step 1: Change domain imports**

Replace imports from `app.services.reference_asset_service` with `app.domains.creative_library.reference_asset_service` in the domain-owned modules listed above.

- [ ] **Step 2: Update README**

Record `app.services.reference_asset_service` as a facade targeting `app.domains.creative_library.reference_asset_service`, and add a cleanup gate requiring only compatibility tests, migration docs, or service modules whose domains have not moved yet to reference the legacy path.

### Task 4: Verify And Commit

**Files:**

- All files listed above.

- [ ] **Step 1: Run the new boundary test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_creative_library_reference_asset_service_facade.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run focused regression**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_creative_library_reference_asset_service_facade.py server/tests/test_creative_library_domain_boundary.py server/tests/test_reference_asset_service.py -q
```

Expected: all selected tests pass or any unrelated dirty test failures are reported.

- [ ] **Step 3: Commit only touched files**

Use an isolated Git index if the working tree contains unrelated WIP. Commit message:

```text
refactor: move reference asset service into domain
```

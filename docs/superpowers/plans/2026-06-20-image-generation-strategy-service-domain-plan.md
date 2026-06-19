# Image Generation Strategy Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move image production strategy CRUD/versioning into the image generation domain while preserving old service imports.

**Architecture:** The implementation lives in `app.domains.image_generation.image_production_strategy_service`. `app.services.image_production_strategy_service` becomes a `sys.modules` facade so old callers and monkeypatches resolve to the same module object.

**Tech Stack:** Python, SQLAlchemy ORM, FastAPI route modules, pytest.

---

## File Structure

- Create: `server/app/domains/image_generation/image_production_strategy_service.py`
  - Owns `seed_default_image_strategies`, `list_strategies`, `get_strategy`, `create_strategy`, `update_strategy`, `set_strategy_status`, `strategy_payload`, strategy validation, CRUD, versioning, and status changes.
- Modify: `server/app/services/image_production_strategy_service.py`
  - Becomes a thin compatibility facade.
- Modify: `server/app/domains/image_generation/image_production_router.py`
  - Imports the strategy service from the domain path.
- Modify: `server/app/domains/image_generation/README.md`
  - Documents service ownership, facade mapping, and cleanup gates.
- Create: `server/tests/test_image_generation_strategy_service_facade.py`
  - Proves service boundary and compatibility.

### Task 1: Red Boundary Test

**Files:**

- Create: `server/tests/test_image_generation_strategy_service_facade.py`
- Create: `docs/superpowers/specs/2026-06-20-image-generation-strategy-service-domain-design.md`
- Create: `docs/superpowers/plans/2026-06-20-image-generation-strategy-service-domain-plan.md`

- [ ] **Step 1: Write the failing test**

Create tests asserting the domain service file exists, the legacy module is a facade, old and new imports are the same module object, the image production router imports the domain path, and README cleanup gates document the facade.

- [ ] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_strategy_service_facade.py -q
```

Expected: FAIL because `server/app/domains/image_generation/image_production_strategy_service.py` does not exist yet, the old service file still contains the strategy functions, and the router still imports `app.services.image_production_strategy_service`.

### Task 2: Move The Service

**Files:**

- Create: `server/app/domains/image_generation/image_production_strategy_service.py`
- Modify: `server/app/services/image_production_strategy_service.py`

- [ ] **Step 1: Copy the implementation**

Copy the current contents of `server/app/services/image_production_strategy_service.py` into `server/app/domains/image_generation/image_production_strategy_service.py` without changing behavior.

- [ ] **Step 2: Replace the legacy service with a facade**

Use this facade shape:

```python
"""Compatibility facade for image generation strategy services.

The implementation now lives in app.domains.image_generation.image_production_strategy_service.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.image_generation import image_production_strategy_service as _image_production_strategy_service

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _image_production_strategy_service
globals().update(_image_production_strategy_service.__dict__)
```

### Task 3: Update Domain Imports And Docs

**Files:**

- Modify: `server/app/domains/image_generation/image_production_router.py`
- Modify: `server/app/domains/image_generation/README.md`

- [ ] **Step 1: Change the router import**

Replace `from app.services.image_production_strategy_service import ...` with `from app.domains.image_generation.image_production_strategy_service import ...`.

- [ ] **Step 2: Update README**

Record `app.services.image_production_strategy_service` as a facade targeting `app.domains.image_generation.image_production_strategy_service`, and add a cleanup gate requiring only compatibility tests, migration docs, or service modules whose domains have not moved yet to reference the legacy path.

### Task 4: Verify And Commit

**Files:**

- All files listed above.

- [ ] **Step 1: Run the new boundary test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_strategy_service_facade.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run focused regression**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_strategy_service_facade.py server/tests/test_image_generation_domain_boundary.py server/tests/test_image_production_strategy_service.py -q
```

Expected: all selected tests pass or any unrelated dirty test failures are reported.

- [ ] **Step 3: Commit only touched files**

Use an isolated Git index if the working tree contains unrelated WIP. Commit message:

```text
refactor: move image strategy service into domain
```

# Image Generation Policy Runtime Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move image production policy runtime previews into the image
generation domain while preserving old service imports.

**Architecture:** The implementation lives in
`app.domains.image_generation.image_production_policy_runtime`.
`app.services.image_production_policy_runtime` becomes a `sys.modules` facade so
old callers and monkeypatches resolve to the same module object.

**Tech Stack:** Python, SQLAlchemy ORM, pytest.

---

## File Structure

- Create: `server/app/domains/image_generation/image_production_policy_runtime.py`
  - Owns `estimate_image_cost`, `preview_image_capacity`,
    `preview_review_gate`, `_policy_snapshot`, `_count_images`, and default
    policy snapshots.
- Modify: `server/app/services/image_production_policy_runtime.py`
  - Becomes a thin compatibility facade.
- Modify: `server/app/domains/image_generation/image_selection_preview_service.py`
  - Imports policy runtime helpers from the domain path.
- Modify: `server/app/domains/image_generation/README.md`
  - Documents policy runtime ownership, facade mapping, and cleanup gates.
- Create: `server/tests/test_image_generation_policy_runtime_facade.py`
  - Proves policy runtime boundary and compatibility.

### Task 1: Red Boundary Test

**Files:**

- Create: `server/tests/test_image_generation_policy_runtime_facade.py`
- Create:
  `docs/superpowers/specs/2026-06-20-image-generation-policy-runtime-domain-design.md`
- Create:
  `docs/superpowers/plans/2026-06-20-image-generation-policy-runtime-domain-plan.md`

- [ ] **Step 1: Write the failing test**

Create tests asserting the domain policy runtime file exists, the legacy module
is a facade, old and new imports are the same module object, the domain
selection preview service imports the domain path, and README cleanup gates
document the facade.

- [ ] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_policy_runtime_facade.py -q
```

Expected: FAIL because
`server/app/domains/image_generation/image_production_policy_runtime.py` does
not exist yet, the old service file still contains `estimate_image_cost`, and
selection preview still imports `app.services.image_production_policy_runtime`.

### Task 2: Move The Policy Runtime

**Files:**

- Create: `server/app/domains/image_generation/image_production_policy_runtime.py`
- Modify: `server/app/services/image_production_policy_runtime.py`

- [ ] **Step 1: Copy the implementation**

Copy the current contents of
`server/app/services/image_production_policy_runtime.py` into
`server/app/domains/image_generation/image_production_policy_runtime.py` without
changing behavior.

- [ ] **Step 2: Replace the legacy service with a facade**

Use this facade shape:

```python
"""Compatibility facade for image generation policy runtime helpers.

The implementation now lives in app.domains.image_generation.image_production_policy_runtime.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.image_generation import image_production_policy_runtime as _image_production_policy_runtime

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _image_production_policy_runtime
globals().update(_image_production_policy_runtime.__dict__)
```

### Task 3: Update Domain Import And Docs

**Files:**

- Modify: `server/app/domains/image_generation/image_selection_preview_service.py`
- Modify: `server/app/domains/image_generation/README.md`

- [ ] **Step 1: Change selection preview import**

Replace
`from app.services.image_production_policy_runtime import estimate_image_cost, preview_image_capacity, preview_review_gate`
with
`from app.domains.image_generation.image_production_policy_runtime import estimate_image_cost, preview_image_capacity, preview_review_gate`.

- [ ] **Step 2: Update README**

Record `app.services.image_production_policy_runtime` as a facade targeting
`app.domains.image_generation.image_production_policy_runtime`, and add a
cleanup gate requiring only compatibility tests, migration docs, or service
modules whose domains have not moved yet to reference the legacy path.

### Task 4: Verify And Commit

**Files:**

- All files listed above.

- [ ] **Step 1: Run the new boundary test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_policy_runtime_facade.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run focused regression**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_policy_runtime_facade.py server/tests/test_image_production_policy_runtime.py server/tests/test_image_selection_preview_service.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Commit only touched files**

Use an isolated Git index if the working tree contains unrelated WIP. Commit
message:

```text
refactor: move image policy runtime into domain
```

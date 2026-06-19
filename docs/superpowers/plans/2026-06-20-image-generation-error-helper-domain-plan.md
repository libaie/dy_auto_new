# Image Generation Error Helper Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move image API error payload construction into the image generation
domain while preserving old service imports.

**Architecture:** The implementation lives in
`app.domains.image_generation.image_creation_errors`.
`app.services.image_creation_errors` becomes a `sys.modules` facade so old
callers and monkeypatches resolve to the same module object.

**Tech Stack:** Python, FastAPI, pytest.

---

## File Structure

- Create: `server/app/domains/image_generation/image_creation_errors.py`
  - Owns `image_error`.
- Modify: `server/app/services/image_creation_errors.py`
  - Becomes a thin compatibility facade.
- Modify: image generation domain modules
  - Import `image_error` from the domain path.
- Modify: `server/app/domains/image_generation/README.md`
  - Documents error helper ownership, facade mapping, and cleanup gates.
- Create: `server/tests/test_image_generation_error_helper_facade.py`
  - Proves error helper boundary and compatibility.

### Task 1: Red Boundary Test

**Files:**

- Create: `server/tests/test_image_generation_error_helper_facade.py`
- Create:
  `docs/superpowers/specs/2026-06-20-image-generation-error-helper-domain-design.md`
- Create:
  `docs/superpowers/plans/2026-06-20-image-generation-error-helper-domain-plan.md`

- [ ] **Step 1: Write the failing test**

Create tests asserting the domain helper file exists, the legacy module is a
facade, old and new imports are the same module object, domain modules import
the domain path, and README cleanup gates document the facade.

- [ ] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_error_helper_facade.py -q
```

Expected: FAIL because the domain helper does not exist yet, the old helper file
still contains `image_error`, and domain modules still import
`app.services.image_creation_errors`.

### Task 2: Move The Error Helper

**Files:**

- Create: `server/app/domains/image_generation/image_creation_errors.py`
- Modify: `server/app/services/image_creation_errors.py`

- [ ] **Step 1: Copy the implementation**

Copy the current contents of `server/app/services/image_creation_errors.py` into
`server/app/domains/image_generation/image_creation_errors.py` without changing
behavior.

- [ ] **Step 2: Replace the legacy helper with a facade**

Use this facade shape:

```python
"""Compatibility facade for image generation error helpers.

The implementation now lives in app.domains.image_generation.image_creation_errors.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.image_generation import image_creation_errors as _image_creation_errors

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _image_creation_errors
globals().update(_image_creation_errors.__dict__)
```

### Task 3: Update Domain Imports And Docs

**Files:**

- Modify: image generation domain modules that import
  `app.services.image_creation_errors`.
- Modify: `server/app/domains/image_generation/README.md`

- [ ] **Step 1: Change domain error imports**

Replace `from app.services.image_creation_errors import image_error` with
`from app.domains.image_generation.image_creation_errors import image_error` in
domain-owned modules.

- [ ] **Step 2: Update README**

Record `app.services.image_creation_errors` as a facade targeting
`app.domains.image_generation.image_creation_errors`, and add a cleanup gate
requiring only compatibility tests, migration docs, or service modules whose
domains have not moved yet to reference the legacy path.

### Task 4: Verify And Commit

**Files:**

- All files listed above.

- [ ] **Step 1: Run the new boundary test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_error_helper_facade.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run focused regression**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_error_helper_facade.py server/tests/test_image_creation_errors.py server/tests/test_image_ab_service.py server/tests/test_image_asset_bridge.py server/tests/test_image_selection_preview_service.py server/tests/test_image_production_strategy_service.py server/tests/test_image_production_recommendation_service.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Commit only touched files**

Use an isolated Git index if the working tree contains unrelated WIP. Commit
message:

```text
refactor: move image error helper into domain
```

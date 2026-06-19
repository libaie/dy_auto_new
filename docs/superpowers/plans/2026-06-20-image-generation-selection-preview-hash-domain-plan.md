# Image Generation Selection Preview Hash Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move selection preview request hashing into the image generation
domain while preserving old service imports.

**Architecture:** The implementation lives in
`app.domains.image_generation.image_selection_preview_hash`.
`app.services.image_selection_preview_hash` becomes a `sys.modules` facade so
old callers and monkeypatches resolve to the same module object.

**Tech Stack:** Python, pytest.

---

## File Structure

- Create: `server/app/domains/image_generation/image_selection_preview_hash.py`
  - Owns `selection_preview_hash_inputs`, `selection_preview_request_hash`,
    `_source_identity`, and `_reference_identities`.
- Modify: `server/app/services/image_selection_preview_hash.py`
  - Becomes a thin compatibility facade.
- Modify: `server/app/domains/image_generation/image_selection_preview_service.py`
  - Imports hash helpers from the domain path.
- Modify: `server/app/domains/image_generation/README.md`
  - Documents helper ownership, facade mapping, and cleanup gates.
- Create: `server/tests/test_image_generation_selection_preview_hash_facade.py`
  - Proves helper boundary and compatibility.

### Task 1: Red Boundary Test

**Files:**

- Create: `server/tests/test_image_generation_selection_preview_hash_facade.py`
- Create:
  `docs/superpowers/specs/2026-06-20-image-generation-selection-preview-hash-domain-design.md`
- Create:
  `docs/superpowers/plans/2026-06-20-image-generation-selection-preview-hash-domain-plan.md`

- [ ] **Step 1: Write the failing test**

Create tests asserting the domain helper file exists, the legacy module is a
facade, old and new imports are the same module object, the domain selection
preview service imports the domain path, and README cleanup gates document the
facade.

- [ ] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_selection_preview_hash_facade.py -q
```

Expected: FAIL because
`server/app/domains/image_generation/image_selection_preview_hash.py` does not
exist yet, the old helper file still contains `selection_preview_hash_inputs`,
and selection preview still imports `app.services.image_selection_preview_hash`.

### Task 2: Move The Helper

**Files:**

- Create: `server/app/domains/image_generation/image_selection_preview_hash.py`
- Modify: `server/app/services/image_selection_preview_hash.py`

- [ ] **Step 1: Copy the implementation**

Copy the current contents of
`server/app/services/image_selection_preview_hash.py` into
`server/app/domains/image_generation/image_selection_preview_hash.py` without
changing behavior.

- [ ] **Step 2: Replace the legacy helper with a facade**

Use this facade shape:

```python
"""Compatibility facade for image generation selection preview hash helpers.

The implementation now lives in app.domains.image_generation.image_selection_preview_hash.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.image_generation import image_selection_preview_hash as _image_selection_preview_hash

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _image_selection_preview_hash
globals().update(_image_selection_preview_hash.__dict__)
```

### Task 3: Update Domain Import And Docs

**Files:**

- Modify: `server/app/domains/image_generation/image_selection_preview_service.py`
- Modify: `server/app/domains/image_generation/README.md`

- [ ] **Step 1: Change selection preview import**

Replace
`from app.services.image_selection_preview_hash import selection_preview_hash_inputs, selection_preview_request_hash`
with
`from app.domains.image_generation.image_selection_preview_hash import selection_preview_hash_inputs, selection_preview_request_hash`.

- [ ] **Step 2: Update README**

Record `app.services.image_selection_preview_hash` as a facade targeting
`app.domains.image_generation.image_selection_preview_hash`, and add a cleanup
gate requiring only compatibility tests, migration docs, or service modules
whose domains have not moved yet to reference the legacy path.

### Task 4: Verify And Commit

**Files:**

- All files listed above.

- [ ] **Step 1: Run the new boundary test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_selection_preview_hash_facade.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run focused regression**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_selection_preview_hash_facade.py server/tests/test_image_generation_selection_preview_service_facade.py server/tests/test_image_selection_preview_service.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Commit only touched files**

Use an isolated Git index if the working tree contains unrelated WIP. Commit
message:

```text
refactor: move selection preview hash into domain
```

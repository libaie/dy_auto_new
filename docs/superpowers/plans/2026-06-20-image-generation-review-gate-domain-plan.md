# Image Generation Review Gate Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move image review gate helpers into the image generation domain while
preserving old service imports.

**Architecture:** The implementation lives in
`app.domains.image_generation.image_review_gate_service`.
`app.services.image_review_gate_service` becomes a `sys.modules` facade so old
callers and monkeypatches resolve to the same module object.

**Tech Stack:** Python, pytest.

---

## File Structure

- Create: `server/app/domains/image_generation/image_review_gate_service.py`
  - Owns `asset_review_gate`, `review_gate_passed`, and
    `review_gate_rescue_actions`.
- Modify: `server/app/services/image_review_gate_service.py`
  - Becomes a thin compatibility facade.
- Modify: `server/app/domains/image_generation/image_asset_bridge_service.py`
  - Imports review gate helpers from the domain path.
- Modify: `server/app/domains/image_generation/README.md`
  - Documents review gate ownership, facade mapping, and cleanup gates.
- Create: `server/tests/test_image_generation_review_gate_facade.py`
  - Proves review gate boundary and compatibility.

### Task 1: Red Boundary Test

**Files:**

- Create: `server/tests/test_image_generation_review_gate_facade.py`
- Create:
  `docs/superpowers/specs/2026-06-20-image-generation-review-gate-domain-design.md`
- Create:
  `docs/superpowers/plans/2026-06-20-image-generation-review-gate-domain-plan.md`

- [ ] **Step 1: Write the failing test**

Create tests asserting the domain review gate service file exists, the legacy
module is a facade, old and new imports are the same module object, the domain
asset bridge imports the domain path, and README cleanup gates document the
facade.

- [ ] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_review_gate_facade.py -q
```

Expected: FAIL because
`server/app/domains/image_generation/image_review_gate_service.py` does not
exist yet, the old service file still contains `asset_review_gate`, and the
domain asset bridge still imports `app.services.image_review_gate_service`.

### Task 2: Move The Review Gate Helper

**Files:**

- Create: `server/app/domains/image_generation/image_review_gate_service.py`
- Modify: `server/app/services/image_review_gate_service.py`

- [ ] **Step 1: Copy the implementation**

Copy the current contents of `server/app/services/image_review_gate_service.py`
into `server/app/domains/image_generation/image_review_gate_service.py` without
changing behavior.

- [ ] **Step 2: Replace the legacy service with a facade**

Use this facade shape:

```python
"""Compatibility facade for image generation review gate services.

The implementation now lives in app.domains.image_generation.image_review_gate_service.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.image_generation import image_review_gate_service as _image_review_gate_service

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _image_review_gate_service
globals().update(_image_review_gate_service.__dict__)
```

### Task 3: Update Domain Import And Docs

**Files:**

- Modify: `server/app/domains/image_generation/image_asset_bridge_service.py`
- Modify: `server/app/domains/image_generation/README.md`

- [ ] **Step 1: Change asset bridge import**

Replace
`from app.services.image_review_gate_service import asset_review_gate, review_gate_passed, review_gate_rescue_actions`
with
`from app.domains.image_generation.image_review_gate_service import asset_review_gate, review_gate_passed, review_gate_rescue_actions`.

- [ ] **Step 2: Update README**

Record `app.services.image_review_gate_service` as a facade targeting
`app.domains.image_generation.image_review_gate_service`, and add a cleanup gate
requiring only compatibility tests, migration docs, or service modules whose
domains have not moved yet to reference the legacy path.

### Task 4: Verify And Commit

**Files:**

- All files listed above.

- [ ] **Step 1: Run the new boundary test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_review_gate_facade.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run focused regression**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_review_gate_facade.py server/tests/test_image_asset_bridge.py server/tests/test_image_creation_strategy_snapshot.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Commit only touched files**

Use an isolated Git index if the working tree contains unrelated WIP. Commit
message:

```text
refactor: move image review gate into domain
```

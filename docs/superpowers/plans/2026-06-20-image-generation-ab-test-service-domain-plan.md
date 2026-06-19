# Image Generation A/B Test Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move image A/B test orchestration into the image generation domain
while preserving old service imports.

**Architecture:** The implementation lives in
`app.domains.image_generation.image_ab_test_service`.
`app.services.image_ab_test_service` becomes a `sys.modules` facade so old
callers and monkeypatches resolve to the same module object.

**Tech Stack:** Python, SQLAlchemy ORM, pytest.

---

## File Structure

- Create: `server/app/domains/image_generation/image_ab_test_service.py`
  - Owns `preview_ab_group`, `create_ab_group`, `refresh_ab_group`,
    `recommend_ab_winner`, `adopt_ab_winner`, `mark_ab_no_winner`,
    `serialize_ab_group`, and supporting helpers.
- Modify: `server/app/services/image_ab_test_service.py`
  - Becomes a thin compatibility facade.
- Modify: moved domain A/B service
  - Imports domain metrics, domain recommendation, and domain selection preview.
- Modify: `server/app/domains/image_generation/image_production_router.py`
  - Imports A/B helpers from the domain path.
- Modify: `server/app/domains/image_generation/README.md`
  - Documents A/B service ownership, facade mapping, and cleanup gates.
- Create: `server/tests/test_image_generation_ab_test_service_facade.py`
  - Proves A/B service boundary and compatibility.

### Task 1: Red Boundary Test

**Files:**

- Create: `server/tests/test_image_generation_ab_test_service_facade.py`
- Create:
  `docs/superpowers/specs/2026-06-20-image-generation-ab-test-service-domain-design.md`
- Create:
  `docs/superpowers/plans/2026-06-20-image-generation-ab-test-service-domain-plan.md`

- [ ] **Step 1: Write the failing test**

Create tests asserting the domain A/B service file exists, the legacy module is
a facade, old and new imports are the same module object, the moved service uses
domain collaborator imports, the domain image production router imports the
domain path, and README cleanup gates document the facade.

- [ ] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_ab_test_service_facade.py -q
```

Expected: FAIL because the domain A/B service does not exist yet, the old
service file still contains `preview_ab_group`, and the domain router still
imports `app.services.image_ab_test_service`.

### Task 2: Move The A/B Service

**Files:**

- Create: `server/app/domains/image_generation/image_ab_test_service.py`
- Modify: `server/app/services/image_ab_test_service.py`

- [ ] **Step 1: Copy the implementation**

Copy the current contents of `server/app/services/image_ab_test_service.py` into
`server/app/domains/image_generation/image_ab_test_service.py` without changing
behavior.

- [ ] **Step 2: Replace the legacy service with a facade**

Use this facade shape:

```python
"""Compatibility facade for image generation A/B test services.

The implementation now lives in app.domains.image_generation.image_ab_test_service.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.image_generation import image_ab_test_service as _image_ab_test_service

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _image_ab_test_service
globals().update(_image_ab_test_service.__dict__)
```

### Task 3: Update Domain Imports And Docs

**Files:**

- Modify: `server/app/domains/image_generation/image_ab_test_service.py`
- Modify: `server/app/domains/image_generation/image_production_router.py`
- Modify: `server/app/domains/image_generation/README.md`

- [ ] **Step 1: Change moved service collaborator imports**

Replace old metrics, recommendation, and selection preview imports with domain
paths:

```python
from app.domains.image_generation.image_production_metrics_service import refresh_image_strategy_metrics, strategy_metrics_payload
from app.domains.image_generation.image_production_recommendation_service import ab_winner_recommendation_payload
from app.domains.image_generation.image_selection_preview_service import create_selection_preview
```

- [ ] **Step 2: Change image production router import**

Replace `from app.services.image_ab_test_service import ...` with
`from app.domains.image_generation.image_ab_test_service import ...`.

- [ ] **Step 3: Update README**

Record `app.services.image_ab_test_service` as a facade targeting
`app.domains.image_generation.image_ab_test_service`, and add a cleanup gate
requiring only compatibility tests, migration docs, or service modules whose
domains have not moved yet to reference the legacy path.

### Task 4: Verify And Commit

**Files:**

- All files listed above.

- [ ] **Step 1: Run the new boundary test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_ab_test_service_facade.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run focused regression**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_ab_test_service_facade.py server/tests/test_image_ab_service.py server/tests/test_image_ab_api.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Commit only touched files**

Use an isolated Git index if the working tree contains unrelated WIP. Commit
message:

```text
refactor: move image ab test service into domain
```

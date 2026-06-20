# Storyboard Image Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move storyboard image task business logic into `app.domains.storyboard_images`.

**Architecture:** The domain service owns the implementation. The old `app.services.storyboard_image_service` path becomes a module alias for compatibility.

**Tech Stack:** Python stdlib, FastAPI, SQLAlchemy, pytest.

---

### Task 1: Red Import Inventory

**Files:**

- Modify: `server/tests/test_domain_service_import_inventory.py`

- [ ] **Step 1: Remove the router-to-service import from the allowlist**

```python
("server/app/domains/storyboard_images/storyboard_images_router.py", "storyboard_image_service"),
```

- [ ] **Step 2: Run red**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py -q
```

Expected: FAIL with `storyboard_images_router.py` still importing
`storyboard_image_service`.

### Task 2: Move Implementation

**Files:**

- Move: `server/app/services/storyboard_image_service.py` to `server/app/domains/storyboard_images/storyboard_image_service.py`
- Create: `server/app/services/storyboard_image_service.py`
- Modify: `server/app/domains/storyboard_images/storyboard_images_router.py`

- [ ] **Step 1: Move the implementation file**

```powershell
Move-Item -LiteralPath 'server/app/services/storyboard_image_service.py' -Destination 'server/app/domains/storyboard_images/storyboard_image_service.py'
```

- [ ] **Step 2: Import the domain service from the router**

```python
from app.domains.storyboard_images.storyboard_image_service import (
    create_missing_storyboard_image_tasks,
    create_storyboard_frame_image_task,
    list_storyboard_image_state,
    promote_storyboard_image_asset,
)
```

- [ ] **Step 3: Add the compatibility module alias**

```python
from __future__ import annotations

import sys

from app.domains.storyboard_images import storyboard_image_service as _impl

sys.modules[__name__] = _impl
```

### Task 3: Green Import Inventory

**Files:**

- Modify: `server/tests/test_domain_service_import_inventory.py`

- [ ] **Step 1: Record the remaining image creation dependency**

```python
("server/app/domains/storyboard_images/storyboard_image_service.py", "image_creation_service"),
```

- [ ] **Step 2: Run green**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py -q
```

Expected: PASS.

### Task 4: Commit

**Files:**

- Add: `docs/superpowers/specs/2026-06-20-storyboard-image-service-domain-design.md`
- Add: `docs/superpowers/plans/2026-06-20-storyboard-image-service-domain-plan.md`
- Add: `server/app/domains/storyboard_images/storyboard_image_service.py`
- Modify: `server/app/domains/storyboard_images/storyboard_images_router.py`
- Modify: `server/app/domains/storyboard_images/README.md`
- Add: `server/app/services/storyboard_image_service.py`
- Modify: `server/tests/test_domain_service_import_inventory.py`
- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Run final checks**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py -q
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
```

- [ ] **Step 2: Commit target files only**

```powershell
git add -f docs/superpowers/specs/2026-06-20-storyboard-image-service-domain-design.md docs/superpowers/plans/2026-06-20-storyboard-image-service-domain-plan.md server/app/domains/storyboard_images/storyboard_image_service.py server/app/domains/storyboard_images/storyboard_images_router.py server/app/domains/storyboard_images/README.md server/app/services/storyboard_image_service.py server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py
git commit --only docs/superpowers/specs/2026-06-20-storyboard-image-service-domain-design.md docs/superpowers/plans/2026-06-20-storyboard-image-service-domain-plan.md server/app/domains/storyboard_images/storyboard_image_service.py server/app/domains/storyboard_images/storyboard_images_router.py server/app/domains/storyboard_images/README.md server/app/services/storyboard_image_service.py server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py -m "refactor: move storyboard image service into domain"
```

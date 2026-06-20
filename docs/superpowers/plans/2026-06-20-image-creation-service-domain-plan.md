# Image Creation Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move image creation workflow helpers into `image_generation` while preserving the legacy service import.

**Architecture:** `app.domains.image_generation.image_creation_service` owns image creation task, asset, review, and provider workflow logic. `app.services.image_creation_service` aliases the domain module until callers move to the domain path.

**Tech Stack:** Python, SQLAlchemy ORM, httpx, pytest.

---

### Task 1: Inventory Red

**Files:**
- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Remove `image_creation_service.py` from the service implementation allowlist**

```python
EXPECTED_NON_FACADE_SERVICE_FILES = {
    "agency_console.py",
    "agency_orchestrator.py",
    "one_sentence_video_service.py",
    "video_agency_team.py",
}
```

Also remove the `"image_creation_service.py": "image_generation"` entry from
`EXPECTED_SERVICE_DOMAIN_TARGETS`.

- [ ] **Step 2: Verify red**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_service_implementation_inventory.py -q
```

Expected: FAIL with `image_creation_service.py` as an extra non-facade service file.

### Task 2: Move Image Creation Service

**Files:**
- Create: `server/app/domains/image_generation/image_creation_service.py`
- Modify: `server/app/services/image_creation_service.py`
- Modify: `server/app/domains/image_generation/README.md`
- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Move the implementation**

Move the current implementation from `server/app/services/image_creation_service.py`
to `server/app/domains/image_generation/image_creation_service.py`.

- [ ] **Step 2: Point migrated dependencies at domain paths**

Use domain imports for image errors, image storage, image model selection,
image cost, image policy preview, review gate, selection preview hashing,
runtime model config, and Pixelle stage client helpers.

- [ ] **Step 3: Replace the legacy service with this facade**

```python
"""Compatibility facade for image creation workflow helpers."""

from __future__ import annotations

import sys

from app.domains.image_generation import image_creation_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_domain_module.__name__] = _domain_module
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
```

- [ ] **Step 4: Update README registration**

Add `image_creation_service.py` to Current Modules and add this facade row:

```markdown
| `app.services.image_creation_service` | `app.domains.image_generation.image_creation_service` | Keep while image routers, image A/B services, storyboard images, review asset edits, reference assets, and legacy tests import or monkeypatch image creation through `app.services`; remove after import inventory is clean. |
```

- [ ] **Step 5: Verify green**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/tests/test_image_creation_api.py server/tests/test_image_creation_strategy_snapshot.py server/tests/test_image_asset_bridge.py server/tests/test_image_ab_service.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit target files only**

```powershell
git add -f docs/superpowers/specs/2026-06-20-image-creation-service-domain-design.md docs/superpowers/plans/2026-06-20-image-creation-service-domain-plan.md server/tests/test_service_implementation_inventory.py server/app/domains/image_generation/image_creation_service.py server/app/services/image_creation_service.py server/app/domains/image_generation/README.md
git commit --only docs/superpowers/specs/2026-06-20-image-creation-service-domain-design.md docs/superpowers/plans/2026-06-20-image-creation-service-domain-plan.md server/tests/test_service_implementation_inventory.py server/app/domains/image_generation/image_creation_service.py server/app/services/image_creation_service.py server/app/domains/image_generation/README.md -m "refactor: move image creation service into domain"
```

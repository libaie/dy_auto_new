# Video Production Review Asset Edit Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move review-time asset edit and void workflows into the video production domain while preserving legacy import and monkeypatch compatibility.

**Architecture:** `app.domains.video_production.review_asset_edit_service` becomes the implementation owner. `app.services.review_asset_edit_service` becomes a `sys.modules` alias facade, and `video_production_router.py` imports the domain helper directly.

**Tech Stack:** Python, FastAPI route modules, SQLAlchemy `Session`, pytest.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_video_production_review_asset_edit_facade.py`
- Read: `server/app/services/review_asset_edit_service.py`
- Read: `server/app/domains/video_production/video_production_router.py`
- Read: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-review-asset-edit-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-review-asset-edit-domain-plan.md"
DOMAIN_EDIT_PATH = REPO_ROOT / "server/app/domains/video_production/review_asset_edit_service.py"
LEGACY_EDIT_PATH = REPO_ROOT / "server/app/services/review_asset_edit_service.py"
ROUTER_PATH = REPO_ROOT / "server/app/domains/video_production/video_production_router.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_review_asset_edit_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.review_asset_edit_service",
        "app.services.review_asset_edit_service",
        "edit_image_asset",
        "void_asset_version",
    ]:
        assert term in spec
        assert term in plan
```

- [ ] **Step 2: Run test to verify it fails**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_review_asset_edit_facade.py -q`
Expected: FAIL because the domain module, router import, and README facade register do not exist yet.

### Task 2: Domain Migration

**Files:**
- Create: `server/app/domains/video_production/review_asset_edit_service.py`
- Modify: `server/app/services/review_asset_edit_service.py`
- Modify: `server/app/domains/video_production/video_production_router.py`
- Modify: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Move the implementation**

Move the existing review asset edit implementation unchanged into
`server/app/domains/video_production/review_asset_edit_service.py`.

- [ ] **Step 2: Replace the legacy module with a facade**

```python
import sys

from app.domains.video_production import review_asset_edit_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [ ] **Step 3: Update the router top-level import**

```python
from app.domains.video_production.review_asset_edit_service import (
    ReviewAssetEditError,
    edit_image_asset,
    void_asset_version,
)
```

- [ ] **Step 4: Document the facade register and cleanup gate**

Add `app.services.review_asset_edit_service` to the facade register with
`app.domains.video_production.review_asset_edit_service` as its target. Add a
cleanup gate requiring import inventory and direct domain coverage for
`edit_image_asset` and `void_asset_version`.

### Task 3: Verification And Commit

**Files:**
- Test: `server/tests/test_video_production_review_asset_edit_facade.py`
- Test: `server/tests/test_review_asset_edit_service.py`
- Test: `server/tests/test_video_production_api.py`

- [ ] **Step 1: Run the focused facade test**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_review_asset_edit_facade.py -q`
Expected: PASS.

- [ ] **Step 2: Run edit behavior tests**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_review_asset_edit_service.py -q`
Expected: PASS.

- [ ] **Step 3: Run the route/API smoke tests**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_api.py -q`
Expected: PASS.

- [ ] **Step 4: Commit only this migration**

Commit message: `refactor: move review asset edit service into domain`

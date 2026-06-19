# Video Production Tree Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move video production plan/run tree payload construction into the video production domain while preserving legacy import compatibility.

**Architecture:** `app.domains.video_production.production_tree_service` becomes the implementation owner. `app.services.production_tree_service` becomes a `sys.modules` alias facade, and `video_production_router.py` imports the domain tree builder directly.

**Tech Stack:** Python, FastAPI route modules, SQLAlchemy `Session`, pytest.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_video_production_tree_service_facade.py`
- Read: `server/app/services/production_tree_service.py`
- Read: `server/app/domains/video_production/video_production_router.py`
- Read: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-tree-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-tree-service-domain-plan.md"
DOMAIN_TREE_PATH = REPO_ROOT / "server/app/domains/video_production/production_tree_service.py"
LEGACY_TREE_PATH = REPO_ROOT / "server/app/services/production_tree_service.py"
ROUTER_PATH = REPO_ROOT / "server/app/domains/video_production/video_production_router.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_tree_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.production_tree_service",
        "app.services.production_tree_service",
        "get_run_tree",
        "_segment_payload",
    ]:
        assert term in spec
        assert term in plan
```

- [ ] **Step 2: Run test to verify it fails**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_tree_service_facade.py -q`
Expected: FAIL because the domain module, domain imports, and README facade register do not exist yet.

### Task 2: Domain Migration

**Files:**
- Move: `server/app/services/production_tree_service.py` to `server/app/domains/video_production/production_tree_service.py`
- Modify: `server/app/services/production_tree_service.py`
- Modify: `server/app/domains/video_production/video_production_router.py`
- Modify: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Move the implementation**

Move the existing tree builder implementation unchanged except for replacing
the status import:

```python
from app.domains.video_production.production_status import (
    ASSET_APPROVED,
    ASSET_FAILED,
    ASSET_GENERATING,
    ASSET_REJECTED,
    SEGMENT_FAILED_RETRYABLE,
)
```

- [ ] **Step 2: Replace the legacy module with a facade**

```python
import sys

from app.domains.video_production import production_tree_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [ ] **Step 3: Update the router top-level import**

```python
from app.domains.video_production.production_tree_service import get_run_tree
```

- [ ] **Step 4: Document the facade register and cleanup gate**

Add `app.services.production_tree_service` to the facade register with
`app.domains.video_production.production_tree_service` as its target. Add a
cleanup gate requiring import inventory and direct domain coverage for
`get_run_tree`.

### Task 3: Verification And Commit

**Files:**
- Test: `server/tests/test_video_production_tree_service_facade.py`
- Test: `server/tests/test_video_production_tree_api.py`
- Test: `server/tests/test_mock_scale_scheduler_service.py`

- [ ] **Step 1: Run the focused facade test**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_tree_service_facade.py -q`
Expected: PASS.

- [ ] **Step 2: Run tree behavior tests**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_tree_api.py server/tests/test_mock_scale_scheduler_service.py -q`
Expected: PASS.

- [ ] **Step 3: Run the domain aggregate import test set**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_tree_service_facade.py server/tests/test_video_production_retry_service_facade.py server/tests/test_video_production_status_contract_facade.py -q`
Expected: PASS.

- [ ] **Step 4: Commit only this migration**

Commit message: `refactor: move production tree service into domain`

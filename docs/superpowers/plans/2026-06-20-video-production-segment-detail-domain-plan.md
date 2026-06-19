# Video Production Segment Detail Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the segment detail response builder into the video production domain while preserving legacy import compatibility.

**Architecture:** `app.domains.video_production.production_segment_detail_service` becomes the implementation owner. `app.services.production_segment_detail_service` becomes a `sys.modules` alias facade, and `video_production_router.py` imports the domain helper directly inside the endpoint.

**Tech Stack:** Python, FastAPI route modules, SQLAlchemy `Session`, pytest.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_video_production_segment_detail_service_facade.py`
- Read: `server/app/services/production_segment_detail_service.py`
- Read: `server/app/domains/video_production/video_production_router.py`
- Read: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-segment-detail-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-segment-detail-domain-plan.md"
DOMAIN_DETAIL_PATH = REPO_ROOT / "server/app/domains/video_production/production_segment_detail_service.py"
LEGACY_DETAIL_PATH = REPO_ROOT / "server/app/services/production_segment_detail_service.py"
ROUTER_PATH = REPO_ROOT / "server/app/domains/video_production/video_production_router.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_segment_detail_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.production_segment_detail_service",
        "app.services.production_segment_detail_service",
        "_asset_payload",
        "get_segment_detail",
    ]:
        assert term in spec
        assert term in plan
```

- [ ] **Step 2: Run test to verify it fails**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_segment_detail_service_facade.py -q`
Expected: FAIL because the domain module, route import, and README facade register do not exist yet.

### Task 2: Domain Migration

**Files:**
- Create: `server/app/domains/video_production/production_segment_detail_service.py`
- Modify: `server/app/services/production_segment_detail_service.py`
- Modify: `server/app/domains/video_production/video_production_router.py`
- Modify: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Move the implementation**

Move `_asset_payload` and `get_segment_detail` unchanged into
`server/app/domains/video_production/production_segment_detail_service.py`.

- [ ] **Step 2: Replace the legacy module with a facade**

```python
import sys

from app.domains.video_production import production_segment_detail_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [ ] **Step 3: Update the router local import**

```python
from app.domains.video_production.production_segment_detail_service import get_segment_detail
```

- [ ] **Step 4: Document the facade register and cleanup gate**

Add `app.services.production_segment_detail_service` to the facade register with
`app.domains.video_production.production_segment_detail_service` as its target.
Add a cleanup gate requiring import inventory and direct domain coverage for
`get_segment_detail`.

### Task 3: Verification And Commit

**Files:**
- Test: `server/tests/test_video_production_segment_detail_service_facade.py`
- Test: `server/tests/test_video_production_segment_detail_api.py`

- [ ] **Step 1: Run the focused facade test**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_segment_detail_service_facade.py -q`
Expected: PASS.

- [ ] **Step 2: Run the endpoint behavior test**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_segment_detail_api.py -q`
Expected: PASS.

- [ ] **Step 3: Run the domain aggregate import test set**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_segment_detail_service_facade.py server/tests/test_video_production_segment_service_facade.py server/tests/test_video_production_status_aggregation_facade.py -q`
Expected: PASS.

- [ ] **Step 4: Commit only this migration**

Commit message: `refactor: move production segment detail into domain`

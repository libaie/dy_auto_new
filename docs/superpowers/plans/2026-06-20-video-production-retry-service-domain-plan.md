# Video Production Retry Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move production segment retry impact and retry execution into the video production domain while preserving legacy import compatibility.

**Architecture:** `app.domains.video_production.production_retry_service` becomes the implementation owner. `app.services.production_retry_service` becomes a `sys.modules` alias facade, and domain-owned callers import the domain helper directly.

**Tech Stack:** Python, FastAPI route modules, SQLAlchemy `Session`, pytest.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_video_production_retry_service_facade.py`
- Read: `server/app/services/production_retry_service.py`
- Read: `server/app/domains/video_production/production_segment_service.py`
- Read: `server/app/domains/video_production/video_production_router.py`
- Read: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-retry-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-retry-service-domain-plan.md"
DOMAIN_RETRY_PATH = REPO_ROOT / "server/app/domains/video_production/production_retry_service.py"
LEGACY_RETRY_PATH = REPO_ROOT / "server/app/services/production_retry_service.py"
SEGMENT_SERVICE_PATH = REPO_ROOT / "server/app/domains/video_production/production_segment_service.py"
ROUTER_PATH = REPO_ROOT / "server/app/domains/video_production/video_production_router.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_retry_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.production_retry_service",
        "app.services.production_retry_service",
        "get_retry_impact",
        "retry_segment_with_impact",
    ]:
        assert term in spec
        assert term in plan
```

- [ ] **Step 2: Run test to verify it fails**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_retry_service_facade.py -q`
Expected: FAIL because the domain module, domain imports, and README facade register do not exist yet.

### Task 2: Domain Migration

**Files:**
- Create: `server/app/domains/video_production/production_retry_service.py`
- Modify: `server/app/services/production_retry_service.py`
- Modify: `server/app/domains/video_production/production_segment_service.py`
- Modify: `server/app/domains/video_production/video_production_router.py`
- Modify: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Move the implementation**

Move `get_retry_impact`, `retry_segment_with_impact`,
`_enqueue_retry_stage_job`, `_run_for_segment`, and
`_retry_stage_for_segment` unchanged into
`server/app/domains/video_production/production_retry_service.py`.

- [ ] **Step 2: Replace the legacy module with a facade**

```python
import sys

from app.domains.video_production import production_retry_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [ ] **Step 3: Update domain-owned imports**

```python
from app.domains.video_production.production_retry_service import retry_segment_with_impact
from app.domains.video_production.production_retry_service import get_retry_impact
```

- [ ] **Step 4: Document the facade register and cleanup gate**

Add `app.services.production_retry_service` to the facade register with
`app.domains.video_production.production_retry_service` as its target. Add a
cleanup gate requiring import inventory and direct domain coverage for
`get_retry_impact` and `retry_segment_with_impact`.

### Task 3: Verification And Commit

**Files:**
- Test: `server/tests/test_video_production_retry_service_facade.py`
- Test: `server/tests/test_video_production_retry_impact.py`
- Test: `server/tests/test_production_bulk_review.py`

- [ ] **Step 1: Run the focused facade test**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_retry_service_facade.py -q`
Expected: PASS.

- [ ] **Step 2: Run retry behavior tests**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_retry_impact.py server/tests/test_production_bulk_review.py -q`
Expected: PASS.

- [ ] **Step 3: Run the domain aggregate import test set**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_retry_service_facade.py server/tests/test_video_production_segment_service_facade.py server/tests/test_video_production_segment_detail_service_facade.py -q`
Expected: PASS.

- [ ] **Step 4: Commit only this migration**

Commit message: `refactor: move production retry service into domain`

# Video Production Segment Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `retry_segment` into the video production domain while preserving legacy import compatibility.

**Architecture:** `app.domains.video_production.production_segment_service` becomes the implementation owner. `app.services.production_segment_service` becomes a `sys.modules` alias facade during the migration window, and the domain router imports the domain path directly.

**Tech Stack:** Python, FastAPI route modules, SQLAlchemy `Session`, pytest.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_video_production_segment_service_facade.py`
- Read: `server/app/services/production_segment_service.py`
- Read: `server/app/domains/video_production/video_production_router.py`
- Read: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-segment-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-segment-service-domain-plan.md"
DOMAIN_SEGMENT_PATH = REPO_ROOT / "server/app/domains/video_production/production_segment_service.py"
LEGACY_SEGMENT_PATH = REPO_ROOT / "server/app/services/production_segment_service.py"
ROUTER_PATH = REPO_ROOT / "server/app/domains/video_production/video_production_router.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_segment_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.production_segment_service",
        "app.services.production_segment_service",
        "retry_segment",
        "retry_segment_with_impact",
    ]:
        assert term in spec
        assert term in plan
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest server/tests/test_video_production_segment_service_facade.py -q`
Expected: FAIL because the domain module, route import, and README facade register are not migrated yet.

### Task 2: Domain Migration

**Files:**
- Create: `server/app/domains/video_production/production_segment_service.py`
- Modify: `server/app/services/production_segment_service.py`
- Modify: `server/app/domains/video_production/video_production_router.py`
- Modify: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Move the implementation**

```python
from sqlalchemy.orm import Session

from app.db_models import ProductionSegment
from app.services.production_retry_service import retry_segment_with_impact


def retry_segment(db: Session, segment_id: str) -> ProductionSegment:
    return retry_segment_with_impact(db, segment_id)
```

- [ ] **Step 2: Replace the legacy module with a facade**

```python
import sys

from app.domains.video_production import production_segment_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [ ] **Step 3: Update the domain router import**

```python
from app.domains.video_production.production_segment_service import retry_segment
```

- [ ] **Step 4: Document the facade register and cleanup gate**

Add `app.services.production_segment_service` to the facade register with
`app.domains.video_production.production_segment_service` as its target. Add a
cleanup gate requiring import inventory and direct domain coverage for
`retry_segment`.

### Task 3: Verification And Commit

**Files:**
- Test: `server/tests/test_video_production_segment_service_facade.py`
- Test: `server/tests/test_production_bulk_review.py`
- Test: `server/tests/test_video_production_retry_impact.py`

- [ ] **Step 1: Run the focused facade test**

Run: `python -m pytest server/tests/test_video_production_segment_service_facade.py -q`
Expected: PASS.

- [ ] **Step 2: Run the retry behavior tests**

Run: `python -m pytest server/tests/test_production_bulk_review.py server/tests/test_video_production_retry_impact.py -q`
Expected: PASS.

- [ ] **Step 3: Run the domain aggregate import test set**

Run: `python -m pytest server/tests/test_video_production_segment_service_facade.py server/tests/test_video_production_run_types_facade.py server/tests/test_video_production_review_service_facade.py server/tests/test_video_production_cost_summary_service_facade.py -q`
Expected: PASS.

- [ ] **Step 4: Commit only this migration**

Commit message: `refactor: move production segment service into domain`

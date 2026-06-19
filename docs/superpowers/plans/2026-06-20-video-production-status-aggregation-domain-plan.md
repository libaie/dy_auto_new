# Video Production Status Aggregation Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move production status aggregation into the video production domain while preserving legacy import compatibility.

**Architecture:** `app.domains.video_production.production_status_aggregation` becomes the implementation owner. `app.services.production_status_aggregation` becomes a `sys.modules` alias facade while unmigrated service modules continue to use the legacy import.

**Tech Stack:** Python, SQLAlchemy `Session`, pytest.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_video_production_status_aggregation_facade.py`
- Read: `server/app/services/production_status_aggregation.py`
- Read: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-status-aggregation-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-status-aggregation-domain-plan.md"
DOMAIN_AGGREGATION_PATH = REPO_ROOT / "server/app/domains/video_production/production_status_aggregation.py"
LEGACY_AGGREGATION_PATH = REPO_ROOT / "server/app/services/production_status_aggregation.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_status_aggregation_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.production_status_aggregation",
        "app.services.production_status_aggregation",
        "_parent_status",
        "recompute_from_segment",
    ]:
        assert term in spec
        assert term in plan
```

- [ ] **Step 2: Run test to verify it fails**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_status_aggregation_facade.py -q`
Expected: FAIL because the domain module and README facade register do not exist yet.

### Task 2: Domain Migration

**Files:**
- Create: `server/app/domains/video_production/production_status_aggregation.py`
- Modify: `server/app/services/production_status_aggregation.py`
- Modify: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Move the implementation**

```python
from sqlalchemy.orm import Session

from app.db_models import ProductionEpisode, ProductionPlan, ProductionScene, ProductionSegment, ProductionShot


def _parent_status(child_statuses: list[str]) -> str:
    if not child_statuses:
        return "planned"
    if any(status in {"failed_terminal"} for status in child_statuses):
        return "failed_terminal"
    if any(status in {"failed", "failed_retryable"} for status in child_statuses):
        return "failed_retryable"
    if any(status in {"image_running", "video_running", "composing"} for status in child_statuses):
        return "running"
    if any(status in {"image_review_pending", "video_review_pending", "blocked_by_review"} for status in child_statuses):
        return "blocked_by_review"
    if all(status == "completed" for status in child_statuses):
        return "completed"
    if all(status == "paused" for status in child_statuses):
        return "paused"
    return "running"


def recompute_from_segment(db: Session, segment_id: str) -> None:
    segment = db.query(ProductionSegment).filter(ProductionSegment.id == segment_id).first()
    if not segment:
        return
```

- [ ] **Step 2: Replace the legacy module with a facade**

```python
import sys

from app.domains.video_production import production_status_aggregation as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [ ] **Step 3: Document the facade register and cleanup gate**

Add `app.services.production_status_aggregation` to the facade register with
`app.domains.video_production.production_status_aggregation` as its target. Add
a cleanup gate requiring import inventory and direct domain coverage for
`recompute_from_segment`.

### Task 3: Verification And Commit

**Files:**
- Test: `server/tests/test_video_production_status_aggregation_facade.py`
- Test: `server/tests/test_video_production_pause_resume.py`

- [ ] **Step 1: Run the focused facade test**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_status_aggregation_facade.py -q`
Expected: PASS.

- [ ] **Step 2: Run the behavior test**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_pause_resume.py -q`
Expected: PASS.

- [ ] **Step 3: Run the domain aggregate import test set**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_status_aggregation_facade.py server/tests/test_video_production_segment_service_facade.py server/tests/test_video_production_status_contract_facade.py -q`
Expected: PASS.

- [ ] **Step 4: Commit only this migration**

Commit message: `refactor: move production status aggregation into domain`

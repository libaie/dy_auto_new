# Video Production State Helper Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move video production stage-gate state helpers into the video production domain while preserving legacy import compatibility.

**Architecture:** `app.domains.video_production.video_production_state` becomes the implementation owner. `app.services.video_production_state` becomes a `sys.modules` alias facade, and clean domain callers import the domain helper directly.

**Tech Stack:** Python, SQLAlchemy `Session`, pytest.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_video_production_state_helper_facade.py`
- Read: `server/app/services/video_production_state.py`
- Read: `server/app/domains/video_production/production_review_service.py`
- Read: `server/app/domains/ai_video_series/status_read_model.py`
- Read: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-state-helper-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-state-helper-domain-plan.md"
DOMAIN_STATE_PATH = REPO_ROOT / "server/app/domains/video_production/video_production_state.py"
LEGACY_STATE_PATH = REPO_ROOT / "server/app/services/video_production_state.py"
REVIEW_SERVICE_PATH = REPO_ROOT / "server/app/domains/video_production/production_review_service.py"
AI_VIDEO_STATUS_PATH = REPO_ROOT / "server/app/domains/ai_video_series/status_read_model.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_state_helper_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.video_production_state",
        "app.services.video_production_state",
        "production_segment_frame_ids",
        "recompute_run_gate",
    ]:
        assert term in spec
        assert term in plan
```

- [ ] **Step 2: Run test to verify it fails**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_state_helper_facade.py -q`
Expected: FAIL because the domain module, clean domain imports, and README facade register do not exist yet.

### Task 2: Domain Migration

**Files:**
- Move: `server/app/services/video_production_state.py` to `server/app/domains/video_production/video_production_state.py`
- Modify: `server/app/services/video_production_state.py`
- Modify: `server/app/domains/video_production/production_review_service.py`
- Modify: `server/app/domains/ai_video_series/status_read_model.py`
- Modify: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Move the implementation**

Move the existing state helper implementation unchanged into
`server/app/domains/video_production/video_production_state.py`.

- [ ] **Step 2: Replace the legacy module with a facade**

```python
import sys

from app.domains.video_production import video_production_state as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [ ] **Step 3: Update clean domain callers**

```python
from app.domains.video_production.video_production_state import latest_assets_by_frame, recompute_run_gate
from app.domains.video_production.video_production_state import IMAGE_READY_STATUS, VIDEO_READY_STATUS
```

- [ ] **Step 4: Document the facade register and cleanup gate**

Add `app.services.video_production_state` to the facade register with
`app.domains.video_production.video_production_state` as its target. Add a
cleanup gate requiring import inventory and direct domain coverage for
`recompute_run_gate`.

### Task 3: Verification And Commit

**Files:**
- Test: `server/tests/test_video_production_state_helper_facade.py`
- Test: `server/tests/test_video_production_state_machine.py`
- Test: `server/tests/test_production_bulk_review.py`
- Test: `server/tests/test_ai_video_series_status_read_model.py`

- [ ] **Step 1: Run the focused facade test**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_state_helper_facade.py -q`
Expected: PASS.

- [ ] **Step 2: Run state behavior tests**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_state_machine.py server/tests/test_production_bulk_review.py server/tests/test_ai_video_series_status_read_model.py -q`
Expected: PASS.

- [ ] **Step 3: Run the domain aggregate import test set**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_state_helper_facade.py server/tests/test_video_production_review_service_facade.py server/tests/test_video_production_run_types_facade.py -q`
Expected: PASS.

- [ ] **Step 4: Commit only this migration**

Commit message: `refactor: move video production state helper into domain`

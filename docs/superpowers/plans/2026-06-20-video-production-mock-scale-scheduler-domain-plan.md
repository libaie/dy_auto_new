# Video Production Mock Scale Scheduler Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move mock-scale video production scheduler logic into the video production domain while preserving legacy import compatibility.

**Architecture:** `app.domains.video_production.mock_scale_scheduler_service` becomes the implementation owner. `app.services.mock_scale_scheduler_service` becomes a `sys.modules` alias facade, and `video_production_router.py` imports the domain scheduler directly.

**Tech Stack:** Python, FastAPI route modules, SQLAlchemy `Session`, pytest.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_video_production_mock_scale_scheduler_facade.py`
- Read: `server/app/services/mock_scale_scheduler_service.py`
- Read: `server/app/domains/video_production/video_production_router.py`
- Read: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-mock-scale-scheduler-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-mock-scale-scheduler-domain-plan.md"
DOMAIN_SCHEDULER_PATH = REPO_ROOT / "server/app/domains/video_production/mock_scale_scheduler_service.py"
LEGACY_SCHEDULER_PATH = REPO_ROOT / "server/app/services/mock_scale_scheduler_service.py"
ROUTER_PATH = REPO_ROOT / "server/app/domains/video_production/video_production_router.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_mock_scale_scheduler_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.mock_scale_scheduler_service",
        "app.services.mock_scale_scheduler_service",
        "create_mock_scale_run",
        "advance_mock_scheduler",
    ]:
        assert term in spec
        assert term in plan
```

- [ ] **Step 2: Run test to verify it fails**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_mock_scale_scheduler_facade.py -q`
Expected: FAIL because the domain module, router import, and README facade register do not exist yet.

### Task 2: Domain Migration

**Files:**
- Move: `server/app/services/mock_scale_scheduler_service.py` to `server/app/domains/video_production/mock_scale_scheduler_service.py`
- Modify: `server/app/services/mock_scale_scheduler_service.py`
- Modify: `server/app/domains/video_production/video_production_router.py`
- Modify: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Move the implementation and domain imports**

Move the existing scheduler implementation into
`server/app/domains/video_production/mock_scale_scheduler_service.py` and change
already-migrated imports to:

```python
from app.domains.video_production.production_status import (...)
from app.domains.video_production.video_production_run_types import MOCK_SERIES_SCALE
```

- [ ] **Step 2: Replace the legacy module with a facade**

```python
import sys

from app.domains.video_production import mock_scale_scheduler_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [ ] **Step 3: Update the router import**

```python
from app.domains.video_production.mock_scale_scheduler_service import advance_mock_scheduler
```

- [ ] **Step 4: Document the facade register and cleanup gate**

Add `app.services.mock_scale_scheduler_service` to the facade register with
`app.domains.video_production.mock_scale_scheduler_service` as its target. Add a
cleanup gate requiring import inventory and direct domain coverage for
`create_mock_scale_run` and `advance_mock_scheduler`.

### Task 3: Verification And Commit

**Files:**
- Test: `server/tests/test_video_production_mock_scale_scheduler_facade.py`
- Test: `server/tests/test_mock_scale_scheduler_service.py`
- Test: `server/tests/test_video_production_observability_events.py`

- [ ] **Step 1: Run the focused facade test**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_mock_scale_scheduler_facade.py -q`
Expected: PASS.

- [ ] **Step 2: Run scheduler behavior tests**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_mock_scale_scheduler_service.py -q`
Expected: PASS.

- [ ] **Step 3: Run observability coverage that uses mock scale scheduler**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_observability_events.py -q`
Expected: PASS.

- [ ] **Step 4: Commit only this migration**

Commit message: `refactor: move mock scale scheduler into domain`

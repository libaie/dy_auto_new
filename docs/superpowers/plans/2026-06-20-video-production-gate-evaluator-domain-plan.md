# Video Production Gate Evaluator Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move video production stage gate evaluation into the video production domain while preserving legacy import compatibility.

**Architecture:** `app.domains.video_production.production_gate_evaluator` becomes the implementation owner. `app.services.production_gate_evaluator` becomes a `sys.modules` alias facade while unmigrated service callers keep working.

**Tech Stack:** Python, SQLAlchemy `Session`, pytest.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_video_production_gate_evaluator_facade.py`
- Read: `server/app/services/production_gate_evaluator.py`
- Read: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-gate-evaluator-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-gate-evaluator-domain-plan.md"
DOMAIN_GATE_PATH = REPO_ROOT / "server/app/domains/video_production/production_gate_evaluator.py"
LEGACY_GATE_PATH = REPO_ROOT / "server/app/services/production_gate_evaluator.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_video_production_gate_evaluator_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.production_gate_evaluator",
        "app.services.production_gate_evaluator",
        "evaluate_stage_gate",
        "STAGE_ASSET_TYPES",
    ]:
        assert term in spec
        assert term in plan
```

- [ ] **Step 2: Run test to verify it fails**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_gate_evaluator_facade.py -q`
Expected: FAIL because the domain module and README facade register do not exist yet.

### Task 2: Domain Migration

**Files:**
- Create: `server/app/domains/video_production/production_gate_evaluator.py`
- Modify: `server/app/services/production_gate_evaluator.py`
- Modify: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Move the implementation**

Move the existing gate evaluator implementation into
`server/app/domains/video_production/production_gate_evaluator.py` and replace
the state helper import with:

```python
from app.domains.video_production.video_production_state import production_segment_frame_ids
```

- [ ] **Step 2: Replace the legacy module with a facade**

```python
import sys

from app.domains.video_production import production_gate_evaluator as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [ ] **Step 3: Document the facade register and cleanup gate**

Add `app.services.production_gate_evaluator` to the facade register with
`app.domains.video_production.production_gate_evaluator` as its target. Add a
cleanup gate requiring import inventory and direct domain coverage for
`evaluate_stage_gate`.

### Task 3: Verification And Commit

**Files:**
- Test: `server/tests/test_video_production_gate_evaluator_facade.py`
- Test: `server/tests/test_production_gate_evaluator.py`
- Test: `server/tests/test_video_production_retry_impact.py`

- [ ] **Step 1: Run the focused facade test**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_gate_evaluator_facade.py -q`
Expected: PASS.

- [ ] **Step 2: Run gate behavior tests**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_production_gate_evaluator.py server/tests/test_video_production_retry_impact.py -q`
Expected: PASS.

- [ ] **Step 3: Run the domain aggregate import test set**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_gate_evaluator_facade.py server/tests/test_video_production_state_helper_facade.py server/tests/test_video_production_retry_service_facade.py -q`
Expected: PASS.

- [ ] **Step 4: Commit only this migration**

Commit message: `refactor: move production gate evaluator into domain`

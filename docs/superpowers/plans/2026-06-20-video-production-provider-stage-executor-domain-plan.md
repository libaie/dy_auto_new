# Video Production Provider Stage Executor Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the real provider stage executor into the video production domain while preserving legacy import compatibility.

**Architecture:** `app.domains.video_production.provider_stage_executor` becomes the implementation owner. `app.services.provider_stage_executor` becomes a `sys.modules` alias facade, and clean callers such as system health import the domain constant directly.

**Tech Stack:** Python, SQLAlchemy `Session`, FastAPI route modules, pytest.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_video_production_provider_stage_executor_facade.py`
- Read: `server/app/services/provider_stage_executor.py`
- Read: `server/app/domains/system_operations/system_health_router.py`
- Read: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-provider-stage-executor-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-provider-stage-executor-domain-plan.md"
DOMAIN_EXECUTOR_PATH = REPO_ROOT / "server/app/domains/video_production/provider_stage_executor.py"
LEGACY_EXECUTOR_PATH = REPO_ROOT / "server/app/services/provider_stage_executor.py"
SYSTEM_HEALTH_PATH = REPO_ROOT / "server/app/domains/system_operations/system_health_router.py"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"


def test_provider_stage_executor_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.video_production.provider_stage_executor",
        "app.services.provider_stage_executor",
        "ProviderStageExecutor",
        "PROVIDER_THROTTLE_DEPLOYMENT_CONTRACT",
    ]:
        assert term in spec
        assert term in plan
```

- [ ] **Step 2: Run test to verify it fails**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_provider_stage_executor_facade.py -q`
Expected: FAIL because the domain module, system health import, and README
facade register do not exist yet.

### Task 2: Domain Migration

**Files:**
- Move: `server/app/services/provider_stage_executor.py` to `server/app/domains/video_production/provider_stage_executor.py`
- Modify: `server/app/services/provider_stage_executor.py`
- Modify: `server/app/domains/system_operations/system_health_router.py`
- Modify: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Move the implementation and domain helper imports**

Move the existing executor implementation into
`server/app/domains/video_production/provider_stage_executor.py` and change the
already-migrated helper imports to:

```python
from app.domains.video_production.production_action_result import ProductionActionResult
from app.domains.video_production.production_errors import ProductionErrorCode, ProductionRepairableError
from app.domains.video_production.production_state_contract import (...)
from app.domains.video_production.provider_capability_service import (...)
from app.domains.video_production.provider_cost_reservation_service import (...)
from app.domains.video_production.provider_stage_task_service import (...)
```

Use the shared production observability domain path after the observability
domain migration:

```python
from app.domains.production_observability.production_observability_service import record_production_event
```

Keep this import unchanged in this slice:

```python
from app.services.production_queue_service import retry_job_without_attempt
```

- [ ] **Step 2: Replace the legacy module with a facade**

```python
import sys

from app.domains.video_production import provider_stage_executor as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [ ] **Step 3: Update clean system health import**

```python
from app.domains.video_production.provider_stage_executor import PROVIDER_SUBMIT_WORKER_COUNT_ENV
```

- [ ] **Step 4: Document the facade register and cleanup gate**

Add `provider_stage_executor.py` to the current module list. Add
`app.services.provider_stage_executor` to the facade register with
`app.domains.video_production.provider_stage_executor` as its target. Add a
cleanup gate requiring import inventory and direct domain coverage for
`ProviderStageExecutor` and `PROVIDER_THROTTLE_DEPLOYMENT_CONTRACT`.

### Task 3: Verification And Commit

**Files:**
- Test: `server/tests/test_video_production_provider_stage_executor_facade.py`
- Test: `server/tests/test_provider_stage_executor.py`
- Test: `server/tests/test_provider_throttle_and_backoff.py`
- Test: `server/tests/test_system_health_page_contract.py`

- [ ] **Step 1: Run the focused facade test**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_provider_stage_executor_facade.py -q`
Expected: PASS.

- [ ] **Step 2: Run provider executor behavior tests**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_provider_stage_executor.py server/tests/test_provider_throttle_and_backoff.py -q`
Expected: PASS.

- [ ] **Step 3: Run system health coverage**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_system_health_page_contract.py -q`
Expected: PASS.

- [ ] **Step 4: Commit only this migration**

Commit message: `refactor: move provider stage executor into domain`

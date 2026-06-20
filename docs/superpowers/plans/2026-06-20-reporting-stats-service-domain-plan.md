# Reporting Stats Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move daily stats counting and quota checks into the reporting domain while preserving legacy import compatibility.

**Architecture:** `app.domains.reporting.stats_service` becomes the implementation owner. `app.services.stats_service` becomes a `sys.modules` alias facade, and the clean reporting router imports the domain service directly while device/task/channel callers continue through the facade.

**Tech Stack:** Python, SQLAlchemy `Session`, FastAPI route modules, pytest.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_reporting_stats_service_facade.py`
- Read: `server/app/services/stats_service.py`
- Read: `server/app/domains/reporting/stats_router.py`
- Read: `server/app/domains/device_operations/reporting.py`
- Read: `server/app/domains/reporting/README.md`

- [ ] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-reporting-stats-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-reporting-stats-service-domain-plan.md"
DOMAIN_STATS_PATH = REPO_ROOT / "server/app/domains/reporting/stats_service.py"
LEGACY_STATS_PATH = REPO_ROOT / "server/app/services/stats_service.py"
STATS_ROUTER_PATH = REPO_ROOT / "server/app/domains/reporting/stats_router.py"
DEVICE_REPORTING_PATH = REPO_ROOT / "server/app/domains/device_operations/reporting.py"
README_PATH = REPO_ROOT / "server/app/domains/reporting/README.md"


def test_reporting_stats_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.reporting.stats_service",
        "app.services.stats_service",
        "StatsService",
        "stats_service",
    ]:
        assert term in spec
        assert term in plan
```

- [ ] **Step 2: Run test to verify it fails**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_reporting_stats_service_facade.py -q`
Expected: FAIL because the domain module, facade, reporting router import, and
README facade register do not exist yet.

### Task 2: Domain Migration

**Files:**
- Move: `server/app/services/stats_service.py` to `server/app/domains/reporting/stats_service.py`
- Modify: `server/app/services/stats_service.py`
- Modify: `server/app/domains/reporting/stats_router.py`
- Modify: `server/app/domains/reporting/README.md`
- Modify: `docs/superpowers/specs/2026-06-20-reporting-domain-design.md`
- Modify: `docs/superpowers/plans/2026-06-20-reporting-domain-plan.md`

- [ ] **Step 1: Move the implementation**

Move the implementation into `server/app/domains/reporting/stats_service.py`
without changing counting or quota behavior.

- [ ] **Step 2: Replace the legacy module with a facade**

```python
import sys

from app.domains.reporting import stats_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [ ] **Step 3: Update reporting router import**

```python
from app.domains.reporting.stats_service import stats_service
```

- [ ] **Step 4: Document facade register and cleanup gate**

Add `stats_service.py` to the reporting README current modules, add
`app.services.stats_service` to the facade register, and update the same-day
reporting design/plan docs to state that daily stats logic now lives in
`app.domains.reporting.stats_service`.

### Task 3: Verification And Commit

**Files:**
- Test: `server/tests/test_reporting_stats_service_facade.py`
- Test: `server/tests/test_stats_service.py`
- Test: `server/tests/test_stats_api.py`
- Test: `server/tests/test_reporting_router_facade.py`
- Test: `server/tests/test_reporting_domain_boundary.py`
- Test: `server/tests/test_device_operations_polling_reporting.py`

- [ ] **Step 1: Run the focused facade test**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_reporting_stats_service_facade.py -q`
Expected: PASS.

- [ ] **Step 2: Run stats behavior and API tests**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_stats_service.py server/tests/test_stats_api.py -q`
Expected: PASS.

- [ ] **Step 3: Run reporting and device stats route coverage**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_reporting_router_facade.py server/tests/test_reporting_domain_boundary.py server/tests/test_device_operations_polling_reporting.py -q`
Expected: PASS.

- [ ] **Step 4: Commit only this migration**

Commit message: `refactor: move stats service into reporting domain`

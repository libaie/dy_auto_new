# Production Observability Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move shared production audit-event observability into a dedicated domain while preserving legacy import compatibility.

**Architecture:** `app.domains.production_observability.production_observability_service` becomes the implementation owner. `app.services.production_observability` becomes a `sys.modules` alias facade, and clean domain callers import the shared domain service directly.

**Tech Stack:** Python, SQLAlchemy `Session`, pytest.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_production_observability_domain_facade.py`
- Read: `server/app/services/production_observability.py`
- Read: clean domain callers listed in the spec

- [ ] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-production-observability-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-production-observability-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/production_observability/production_observability_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/production_observability.py"
README_PATH = REPO_ROOT / "server/app/domains/production_observability/README.md"


def test_production_observability_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.production_observability.production_observability_service",
        "app.services.production_observability",
        "_redact",
        "record_production_event",
    ]:
        assert term in spec
        assert term in plan
```

- [ ] **Step 2: Run test to verify it fails**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_production_observability_domain_facade.py -q`
Expected: FAIL because the shared domain module, facade, updated imports, and
README do not exist yet.

### Task 2: Domain Migration

**Files:**
- Create: `server/app/domains/production_observability/__init__.py`
- Create: `server/app/domains/production_observability/README.md`
- Move: `server/app/services/production_observability.py` to `server/app/domains/production_observability/production_observability_service.py`
- Modify: `server/app/services/production_observability.py`
- Modify: clean domain callers listed in the spec

- [ ] **Step 1: Move the implementation**

Move the existing implementation into
`server/app/domains/production_observability/production_observability_service.py`
without changing redaction or transaction behavior.

- [ ] **Step 2: Replace the legacy module with a facade**

```python
import sys

from app.domains.production_observability import production_observability_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [ ] **Step 3: Update clean domain imports**

Replace clean domain imports with:

```python
from app.domains.production_observability.production_observability_service import record_production_event
from app.domains.production_observability.production_observability_service import _redact as _redact_secret_fields
```

- [ ] **Step 4: Document the facade register and cleanup gate**

Create `server/app/domains/production_observability/README.md` with module
ownership, `app.services.production_observability` facade registration, and a
cleanup gate requiring import inventory and direct domain behavior coverage for
`_redact` and `record_production_event`.

### Task 3: Verification And Commit

**Files:**
- Test: `server/tests/test_production_observability_domain_facade.py`
- Test: `server/tests/test_video_production_observability_events.py`
- Test: `server/tests/test_agency_operations_router_facade.py`

- [ ] **Step 1: Run the focused facade test**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_production_observability_domain_facade.py -q`
Expected: PASS.

- [ ] **Step 2: Run observability behavior tests**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_video_production_observability_events.py::test_record_production_event_redacts_secret_like_fields server/tests/test_video_production_observability_events.py::test_record_production_event_uses_caller_transaction -q`
Expected: PASS.

- [ ] **Step 3: Run affected router facade coverage**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_agency_operations_router_facade.py -q`
Expected: PASS.

- [ ] **Step 4: Commit only this migration**

Commit message: `refactor: move production observability into domain`

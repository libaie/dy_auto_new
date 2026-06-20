# Quality Audit Gate Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move audit gate classification into the quality audit domain while preserving legacy import compatibility.

**Architecture:** `app.domains.quality_audit.audit_gate` becomes the implementation owner. `app.services.audit_gate` becomes a `sys.modules` alias facade, and the clean quality audit router imports the domain classifier directly.

**Tech Stack:** Python, FastAPI route modules, pytest.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_quality_audit_gate_facade.py`
- Read: `server/app/services/audit_gate.py`
- Read: `server/app/domains/quality_audit/audit_router.py`
- Read: `server/app/domains/quality_audit/README.md`
- Read: `docs/superpowers/specs/2026-06-20-quality-audit-domain-design.md`

- [ ] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-quality-audit-gate-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-quality-audit-gate-domain-plan.md"
DOMAIN_GATE_PATH = REPO_ROOT / "server/app/domains/quality_audit/audit_gate.py"
LEGACY_GATE_PATH = REPO_ROOT / "server/app/services/audit_gate.py"
AUDIT_ROUTER_PATH = REPO_ROOT / "server/app/domains/quality_audit/audit_router.py"
README_PATH = REPO_ROOT / "server/app/domains/quality_audit/README.md"
QUALITY_AUDIT_SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-quality-audit-domain-design.md"


def test_quality_audit_gate_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.quality_audit.audit_gate",
        "app.services.audit_gate",
        "classify_audit_gate",
        "approve_threshold",
    ]:
        assert term in spec
        assert term in plan
```

- [ ] **Step 2: Run test to verify it fails**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_quality_audit_gate_facade.py -q`
Expected: FAIL because the domain module, router import, facade register, and
same-day quality audit spec update do not exist yet.

### Task 2: Domain Migration

**Files:**
- Move: `server/app/services/audit_gate.py` to `server/app/domains/quality_audit/audit_gate.py`
- Modify: `server/app/services/audit_gate.py`
- Modify: `server/app/domains/quality_audit/audit_router.py`
- Modify: `server/app/domains/quality_audit/README.md`
- Modify: `docs/superpowers/specs/2026-06-20-quality-audit-domain-design.md`

- [ ] **Step 1: Move the implementation**

Move the implementation into `server/app/domains/quality_audit/audit_gate.py`
without changing `classify_audit_gate` behavior.

- [ ] **Step 2: Replace the legacy module with a facade**

```python
import sys

from app.domains.quality_audit import audit_gate as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [ ] **Step 3: Update clean quality audit router import**

```python
from app.domains.quality_audit.audit_gate import classify_audit_gate
```

- [ ] **Step 4: Document facade register and cleanup gate**

Add `audit_gate.py` to the README current modules, add
`app.services.audit_gate` to the facade register, and update the same-day
quality audit domain design spec to state that audit gate classification now
lives in `app.domains.quality_audit.audit_gate`.

### Task 3: Verification And Commit

**Files:**
- Test: `server/tests/test_quality_audit_gate_facade.py`
- Test: `server/tests/test_audit_gate.py`
- Test: `server/tests/test_quality_audit_router_facade.py`
- Test: `server/tests/test_quality_audit_domain_boundary.py`

- [ ] **Step 1: Run the focused facade test**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_quality_audit_gate_facade.py -q`
Expected: PASS.

- [ ] **Step 2: Run audit gate behavior tests**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_audit_gate.py -q`
Expected: PASS.

- [ ] **Step 3: Run quality audit route boundary tests**

Run: `server/.venv/Scripts/python.exe -m pytest server/tests/test_quality_audit_router_facade.py server/tests/test_quality_audit_domain_boundary.py -q`
Expected: PASS.

- [ ] **Step 4: Commit only this migration**

Commit message: `refactor: move audit gate into quality audit domain`

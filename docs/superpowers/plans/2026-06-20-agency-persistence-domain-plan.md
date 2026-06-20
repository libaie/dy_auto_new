# Agency Persistence Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move agency invocation persistence into `app.domains.agency_operations` while preserving `app.services.agency_persistence` compatibility.

**Architecture:** Keep behavior in one domain module and make the old service file a module-alias facade. Reuse existing database models, audit recording, creative patch creation, and repair orchestration imports.

**Tech Stack:** Python, SQLAlchemy, pytest, existing agency operations facade pattern.

---

### Task 1: Facade Test

**Files:**

- Create: `server/tests/test_agency_persistence_facade.py`
- Read: `server/app/services/agency_persistence.py`

- [ ] **Step 1: Write the failing test**

```python
def test_legacy_agency_persistence_module_aliases_domain():
    legacy = importlib.import_module("app.services.agency_persistence")
    domain = importlib.import_module("app.domains.agency_operations.agency_persistence")

    assert sys.modules["app.services.agency_persistence"] is domain
    assert legacy.create_or_resume_invocation is domain.create_or_resume_invocation
    assert legacy.finalize_invocation_and_audit is domain.finalize_invocation_and_audit
```

- [ ] **Step 2: Run red**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_persistence_facade.py -q
```

Expected: fails because `app.domains.agency_operations.agency_persistence` does
not exist and the README does not document the facade.

### Task 2: Move Implementation

**Files:**

- Create: `server/app/domains/agency_operations/agency_persistence.py`
- Modify: `server/app/services/agency_persistence.py`
- Modify: `server/app/domains/agency_operations/README.md`

- [ ] **Step 1: Copy the current implementation**

```powershell
Copy-Item -LiteralPath 'server/app/services/agency_persistence.py' -Destination 'server/app/domains/agency_operations/agency_persistence.py'
```

- [ ] **Step 2: Replace the old service with a facade**

```python
"""Compatibility facade for agency invocation persistence."""

import sys

from app.domains.agency_operations import agency_persistence as _domain_module

_LEGACY_MODULE_NAME = __name__
sys.modules[_domain_module.__name__] = _domain_module
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
```

- [ ] **Step 3: Document the module**

Add `agency_persistence.py` to the Current Modules list and add
`app.services.agency_persistence` to the Facade Register in the agency
operations README.

### Task 3: Verify And Commit

**Files:**

- Test: `server/tests/test_agency_persistence_facade.py`
- Test: `server/tests/test_agency_persistence.py`
- Smoke: `server/app/main.py`

- [ ] **Step 1: Run focused tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_persistence_facade.py server/tests/test_agency_persistence.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run import smoke**

```powershell
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
```

Expected: prints the app title.

- [ ] **Step 3: Commit only this slice**

```powershell
git add -f docs/superpowers/specs/2026-06-20-agency-persistence-domain-design.md docs/superpowers/plans/2026-06-20-agency-persistence-domain-plan.md server/tests/test_agency_persistence_facade.py server/app/domains/agency_operations/agency_persistence.py server/app/services/agency_persistence.py server/app/domains/agency_operations/README.md
git commit --only docs/superpowers/specs/2026-06-20-agency-persistence-domain-design.md docs/superpowers/plans/2026-06-20-agency-persistence-domain-plan.md server/tests/test_agency_persistence_facade.py server/app/domains/agency_operations/agency_persistence.py server/app/services/agency_persistence.py server/app/domains/agency_operations/README.md -m "refactor: move agency persistence into domain"
```

### Task 4: Remove Legacy Imports For Already-Migrated Helpers

**Files:**

- Modify: `server/app/domains/agency_operations/agency_persistence.py`
- Test: `server/tests/test_agency_persistence_facade.py`

- [ ] **Step 1: Add the failing boundary test**

```python
def test_agency_persistence_imports_already_migrated_helpers_from_domains():
    text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "from app.domains.production_observability.production_observability_service import record_production_event" in text
    assert "from app.domains.agency_operations.agency_repair_classifier import classify_repair_tasks" in text
    assert "from app.domains.agency_operations.agency_repair_orchestrator import enqueue_repair_tasks_for_invocation" in text
    assert "app.services.production_observability" not in text
    assert "app.services.agency_repair_classifier" not in text
    assert "app.services.agency_repair_orchestrator" not in text
```

- [ ] **Step 2: Change only those imports**

```python
from app.domains.production_observability.production_observability_service import record_production_event
from app.domains.agency_operations.agency_repair_classifier import classify_repair_tasks
from app.domains.agency_operations.agency_repair_orchestrator import enqueue_repair_tasks_for_invocation
```

- [ ] **Step 3: Run focused verification**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_persistence_facade.py server/tests/test_agency_persistence.py -q
```

Expected: all selected tests pass.

### Task 5: Use Domain Video Production Run Types Import

**Files:**

- Modify: `server/app/domains/agency_operations/agency_persistence.py`
- Test: `server/tests/test_agency_persistence_facade.py`

- [ ] **Step 1: Add the failing boundary test**

```python
def test_agency_persistence_imports_video_run_types_from_domain():
    text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "from app.domains.video_production.video_production_run_types import get_run_type" in text
    assert "app.services.video_production_run_types" not in text
```

- [ ] **Step 2: Change only that import**

```python
from app.domains.video_production.video_production_run_types import get_run_type
```

- [ ] **Step 3: Run focused verification**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_persistence_facade.py server/tests/test_agency_persistence.py server/tests/test_video_production_run_types_facade.py server/tests/test_video_production_run_type.py -q
```

Expected: all selected tests pass.

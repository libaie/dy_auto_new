# Task Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `TaskService` implementation ownership into `app.domains.task_operations` with a legacy compatibility facade.

**Architecture:** The domain module becomes canonical and the old service module becomes a `sys.modules` alias facade. Existing behavior remains unchanged because the implementation body is mechanically copied first, then domain-owned imports are updated to the canonical path.

**Tech Stack:** Python, FastAPI, SQLAlchemy, pytest.

---

## File Structure

- Create: `server/app/domains/task_operations/task_service.py` as the canonical implementation copied from `server/app/services/task_service.py`.
- Modify: `server/app/services/task_service.py` into a thin compatibility facade.
- Modify: `server/app/domains/task_operations/adapters.py` to import `task_service` from the canonical domain path.
- Modify: `server/app/domains/device_operations/polling.py` to import `task_service` and `_db_task_to_pydantic` from the canonical domain path.
- Modify: `server/app/domains/device_operations/reporting.py` to import `task_service` from the canonical domain path.
- Modify: `server/app/domains/device_operations/status_lifecycle.py` to import `MAX_RETRIES` from the canonical domain path.
- Modify: `server/app/domains/account_operations/channel_service.py` to import `_db_task_to_pydantic` from the canonical domain path.
- Modify: `server/app/domains/task_operations/README.md` to register the new service facade.
- Modify: `server/tests/test_task_adapter_domain_imports.py` to expect the adapter to use the domain task-service path.
- Create: `server/tests/test_task_service_domain_facade.py` for migration coverage.

### Task 1: Write Boundary Tests

**Files:**
- Create: `server/tests/test_task_service_domain_facade.py`
- Modify: `server/tests/test_task_adapter_domain_imports.py`

- [x] **Step 1: Add the new failing test**

```python
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-task-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-task-service-domain-plan.md"
DOMAIN_TASK_SERVICE_PATH = REPO_ROOT / "server/app/domains/task_operations/task_service.py"
LEGACY_TASK_SERVICE_PATH = REPO_ROOT / "server/app/services/task_service.py"
README_PATH = REPO_ROOT / "server/app/domains/task_operations/README.md"


DOMAIN_IMPORT_PATHS = [
    REPO_ROOT / "server/app/domains/task_operations/adapters.py",
    REPO_ROOT / "server/app/domains/device_operations/polling.py",
    REPO_ROOT / "server/app/domains/device_operations/reporting.py",
    REPO_ROOT / "server/app/domains/device_operations/status_lifecycle.py",
    REPO_ROOT / "server/app/domains/account_operations/channel_service.py",
]


def test_task_service_domain_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.task_operations.task_service",
        "app.services.task_service",
        "TaskService",
        "task_service",
        "_db_task_to_pydantic",
        "MAX_RETRIES",
    ]:
        assert term in spec
        assert term in plan


def test_task_service_implementation_lives_in_task_operations_domain():
    domain_text = DOMAIN_TASK_SERVICE_PATH.read_text(encoding="utf-8")
    assert "class TaskService" in domain_text
    assert "task_service = TaskService()" in domain_text
    assert "def _db_task_to_pydantic" in domain_text
    assert "MAX_RETRIES = 3" in domain_text

    legacy_text = LEGACY_TASK_SERVICE_PATH.read_text(encoding="utf-8")
    assert "app.domains.task_operations" in legacy_text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in legacy_text
    assert "class TaskService" not in legacy_text
    assert "MAX_RETRIES = 3" not in legacy_text


def test_legacy_task_service_facade_resolves_to_domain_module():
    domain = importlib.import_module("app.domains.task_operations.task_service")
    legacy = importlib.import_module("app.services.task_service")
    assert legacy is domain
    assert legacy.TaskService is domain.TaskService
    assert legacy.task_service is domain.task_service
    assert legacy._db_task_to_pydantic is domain._db_task_to_pydantic
    assert legacy.MAX_RETRIES == domain.MAX_RETRIES


def test_domain_modules_import_task_service_from_domain_path():
    for path in DOMAIN_IMPORT_PATHS:
        text = path.read_text(encoding="utf-8")
        assert "app.domains.task_operations.task_service" in text
        assert "app.services.task_service" not in text


def test_task_operations_readme_registers_task_service_facade():
    text = README_PATH.read_text(encoding="utf-8")
    assert "app.domains.task_operations.task_service" in text
    assert "app.services.task_service" in text
    assert "TaskService" in text
```

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_task_service_domain_facade.py server/tests/test_task_adapter_domain_imports.py -q
```

Expected: FAIL because `server/app/domains/task_operations/task_service.py` does not exist yet and adapters still import the legacy task-service path.

### Task 2: Move Implementation and Update Imports

**Files:**
- Create: `server/app/domains/task_operations/task_service.py`
- Modify: `server/app/services/task_service.py`
- Modify: domain import files listed above
- Modify: `server/app/domains/task_operations/README.md`

- [x] **Step 1: Copy the implementation mechanically**

Run:

```powershell
Copy-Item -LiteralPath 'server/app/services/task_service.py' -Destination 'server/app/domains/task_operations/task_service.py'
```

- [x] **Step 2: Replace the legacy module with a facade**

Use exactly this facade:

```python
"""Compatibility facade for task operation services."""

import sys

from app.domains.task_operations import task_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
```

- [x] **Step 3: Update domain imports**

Use these replacements:

```python
from app.domains.task_operations.task_service import task_service
from app.domains.task_operations.task_service import _db_task_to_pydantic
from app.domains.task_operations.task_service import MAX_RETRIES
```

- [x] **Step 4: Update the README facade register**

Add a row:

```markdown
| `app.services.task_service` | `app.domains.task_operations.task_service` | 2026-06-20 task service domain migration | Cleanup only after all non-compatibility callers use the domain path and task-service behavior tests pass. |
```

- [x] **Step 5: Run tests to verify GREEN**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_task_service_domain_facade.py server/tests/test_task_adapter_domain_imports.py server/tests/test_task_service.py -q
```

Expected: PASS.

### Task 3: Final Verification and Commit

**Files:**
- All files from Tasks 1 and 2

- [x] **Step 1: Verify import scan**

Run:

```powershell
rg -n "from app\.services\.task_service|app\.services\.task_service" server/app/domains -g "*.py"
```

Expected: no matches.

- [x] **Step 2: Verify app import**

Run from `server`:

```powershell
..\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
```

Expected: command exits 0 and prints the app title.

- [x] **Step 3: Verify diff whitespace**

Run:

```powershell
git diff --check -- docs/superpowers/specs/2026-06-20-task-service-domain-design.md docs/superpowers/plans/2026-06-20-task-service-domain-plan.md server/tests/test_task_service_domain_facade.py server/tests/test_task_adapter_domain_imports.py server/app/domains/task_operations/task_service.py server/app/services/task_service.py server/app/domains/task_operations/adapters.py server/app/domains/device_operations/polling.py server/app/domains/device_operations/reporting.py server/app/domains/device_operations/status_lifecycle.py server/app/domains/account_operations/channel_service.py server/app/domains/task_operations/README.md
```

Expected: no output, exit 0.

- [x] **Step 4: Commit only target files**

Run:

```powershell
git add -f docs/superpowers/specs/2026-06-20-task-service-domain-design.md docs/superpowers/plans/2026-06-20-task-service-domain-plan.md server/tests/test_task_service_domain_facade.py server/tests/test_task_adapter_domain_imports.py server/app/domains/task_operations/task_service.py server/app/services/task_service.py server/app/domains/task_operations/adapters.py server/app/domains/device_operations/polling.py server/app/domains/device_operations/reporting.py server/app/domains/device_operations/status_lifecycle.py server/app/domains/account_operations/channel_service.py server/app/domains/task_operations/README.md
git commit --only docs/superpowers/specs/2026-06-20-task-service-domain-design.md docs/superpowers/plans/2026-06-20-task-service-domain-plan.md server/tests/test_task_service_domain_facade.py server/tests/test_task_adapter_domain_imports.py server/app/domains/task_operations/task_service.py server/app/services/task_service.py server/app/domains/task_operations/adapters.py server/app/domains/device_operations/polling.py server/app/domains/device_operations/reporting.py server/app/domains/device_operations/status_lifecycle.py server/app/domains/account_operations/channel_service.py server/app/domains/task_operations/README.md -m "refactor: move task service into task operations"
```

Expected: commit succeeds.

# Chain Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move chain orchestration into account operations while preserving legacy imports and task reporting behavior.

**Architecture:** `app.domains.account_operations.chain_service` becomes the implementation owner. `app.services.chain_service` becomes a `sys.modules` alias facade. `account_operations.adapters` imports the domain service directly, while `task_service` remains legacy-compatible.

**Tech Stack:** Python, SQLAlchemy `Session`, pytest, Python module aliasing via `sys.modules`.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_chain_service_domain_facade.py`
- Read: `server/app/services/chain_service.py`
- Read: `server/app/domains/account_operations/adapters.py`
- Read: `server/app/services/task_service.py`
- Read: `server/app/domains/account_operations/README.md`

- [ ] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-chain-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-chain-service-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/account_operations/chain_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/chain_service.py"
ADAPTERS_PATH = REPO_ROOT / "server/app/domains/account_operations/adapters.py"
TASK_SERVICE_PATH = REPO_ROOT / "server/app/services/task_service.py"
README_PATH = REPO_ROOT / "server/app/domains/account_operations/README.md"


def test_chain_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.account_operations.chain_service",
        "app.services.chain_service",
        "ChainService",
    ]:
        assert term in spec
        assert term in plan
```

- [ ] **Step 2: Complete the test file**

```python
def test_chain_service_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_chain_service_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.account_operations" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "class ChainService" not in text
    assert "chain_service = ChainService()" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_chain_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.chain_service")
        domain = importlib.import_module("app.domains.account_operations.chain_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"chain service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.ChainService is domain.ChainService
    assert legacy.chain_service is domain.chain_service
    assert legacy._account_lock is domain._account_lock
    assert legacy.VALID_STEP_TYPES is domain.VALID_STEP_TYPES
    assert legacy._task_to_push_dict is domain._task_to_push_dict


def test_services_parent_package_chain_service_attribute_is_domain_module():
    from app.services import chain_service as parent_import

    domain = importlib.import_module("app.domains.account_operations.chain_service")

    assert parent_import is domain
    assert parent_import.chain_service is domain.chain_service


def test_account_operations_adapters_imports_domain_chain_service_only():
    text = ADAPTERS_PATH.read_text(encoding="utf-8")

    assert "app.domains.account_operations.chain_service" in text
    assert "app.services.chain_service" not in text


def test_task_service_stays_legacy_compatible():
    text = TASK_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.services.chain_service" in text
    assert "app.domains.account_operations.chain_service" not in text


def test_account_operations_docs_register_chain_service_facade():
    readme = README_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.account_operations.chain_service",
        "app.services.chain_service",
        "ChainService",
        "approved `task_service` compatibility import",
        "remove only when that command returns no production imports",
    ]:
        assert term in readme


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
```

- [ ] **Step 3: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_chain_service_domain_facade.py -q
```

Expected: FAIL because the domain file, facade, direct adapter import, and README entries do not exist yet.

### Task 2: Domain Migration

**Files:**
- Create: `server/app/domains/account_operations/chain_service.py`
- Modify: `server/app/services/chain_service.py`
- Modify: `server/app/domains/account_operations/adapters.py`

- [ ] **Step 1: Move implementation**

Move the current service body into:

```text
server/app/domains/account_operations/chain_service.py
```

Use this module docstring:

```python
"""Chain orchestration service for account operations."""
```

- [ ] **Step 2: Replace legacy module with facade**

```python
"""Compatibility facade for account operation chain services."""

import sys

from app.domains.account_operations import chain_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [ ] **Step 3: Update adapters import**

Replace:

```python
from app.services.chain_service import chain_service
```

with:

```python
from app.domains.account_operations.chain_service import chain_service
```

### Task 3: Documentation Update

**Files:**
- Modify: `server/app/domains/account_operations/README.md`

- [ ] **Step 1: Add ownership rule**

```markdown
- `app.domains.account_operations.chain_service` owns `ChainService` chain instance orchestration, step task creation, and chain advancement.
```

- [ ] **Step 2: Add facade register row**

```markdown
| `app.services.chain_service` | `app.domains.account_operations.chain_service` | Chain service domain slice | Keep while `rg -n "app\.services\.chain_service" server/app -g "*.py"` returns the approved `task_service` compatibility import; remove only when that command returns no production imports. |
```

- [ ] **Step 3: Add cleanup gate**

```markdown
- Do not remove `app.services.chain_service` while `server/app/services/task_service.py` imports it; removal requires zero production matches from `rg -n "app\.services\.chain_service" server/app -g "*.py"`.
```

### Task 4: Verification

- [ ] **Step 1: Run boundary test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_chain_service_domain_facade.py -q
```

Expected: PASS.

- [ ] **Step 2: Run chain behavior tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_chain_service.py server/tests/test_chains_api.py server/tests/test_tasks_api.py -q
```

Expected: PASS.

- [ ] **Step 3: Run account operations boundary tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_account_operations_domain_boundary.py server/tests/test_account_operations_mutations.py -q
```

Expected: PASS.

- [ ] **Step 4: Verify cleanup inventory**

```powershell
rg -n "app\.services\.chain_service" server/app -g "*.py"
```

Expected: only `server/app/services/task_service.py` during this compatibility slice.

- [ ] **Step 5: Commit**

```powershell
git add -f docs/superpowers/specs/2026-06-20-chain-service-domain-design.md docs/superpowers/plans/2026-06-20-chain-service-domain-plan.md server/tests/test_chain_service_domain_facade.py server/app/domains/account_operations/chain_service.py server/app/services/chain_service.py server/app/domains/account_operations/adapters.py server/app/domains/account_operations/README.md
git commit -m "refactor: move chain service into account operations"
```

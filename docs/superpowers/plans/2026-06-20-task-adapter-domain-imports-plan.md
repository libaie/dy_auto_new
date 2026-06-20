# Task Adapter Domain Imports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Point task adapters at account-operation and content-collection domain helpers.

**Architecture:** Channel behavior lives in `app.domains.account_operations.channel_service`; content behavior lives in `app.domains.content_collection.content_service`. `task_service` stays on `app.services.task_service` until its implementation has a domain home.

**Tech Stack:** Python, pytest, existing compatibility facades.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_task_adapter_domain_imports.py`
- Read: `server/app/domains/task_operations/adapters.py`

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-task-adapter-domain-imports-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-task-adapter-domain-imports-plan.md"
ADAPTERS_PATH = REPO_ROOT / "server/app/domains/task_operations/adapters.py"


def test_task_adapter_import_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.account_operations.channel_service",
        "app.domains.content_collection.content_service",
        "app.services.channel_service",
        "app.services.content_service",
        "app.services.task_service",
    ]:
        assert term in spec
        assert term in plan
```

- [x] **Step 2: Complete the boundary test**

```python
def test_task_adapters_import_moved_helpers_from_domain_paths():
    text = ADAPTERS_PATH.read_text(encoding="utf-8")
    assert "app.domains.account_operations.channel_service" in text
    assert "app.domains.content_collection.content_service" in text
    assert "app.services.channel_service" not in text
    assert "app.services.content_service" not in text
    assert "app.services.task_service" in text


def test_legacy_channel_and_content_facades_resolve_to_domain_modules():
    channel_legacy = importlib.import_module("app.services.channel_service")
    channel_domain = importlib.import_module("app.domains.account_operations.channel_service")
    content_legacy = importlib.import_module("app.services.content_service")
    content_domain = importlib.import_module("app.domains.content_collection.content_service")
    assert channel_legacy is channel_domain
    assert channel_legacy.channel_service is channel_domain.channel_service
    assert content_legacy is content_domain
    assert content_legacy.content_service is content_domain.content_service
```

- [x] **Step 3: Run the red test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_task_adapter_domain_imports.py -q
```

Expected: FAIL because task adapters still import channel/content helpers from legacy service facades.

### Task 2: Import Migration

**Files:**
- Modify: `server/app/domains/task_operations/adapters.py`
- Modify: `server/tests/test_channel_service_domain_facade.py`
- Modify: `server/tests/test_content_service_domain_facade.py`

- [x] **Step 1: Replace legacy imports**

```python
from app.domains.account_operations.channel_service import channel_service
from app.domains.content_collection.content_service import content_service
from app.services.task_service import task_service
```

- [x] **Step 2: Update existing facade boundary expectations**

Existing channel and content facade tests should now expect task adapters to
use direct domain imports while old service modules may keep legacy imports.

- [x] **Step 3: Run verification**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_task_adapter_domain_imports.py server/tests/test_channel_service_domain_facade.py server/tests/test_content_service_domain_facade.py -q
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
rg -n "from app\.services\.(channel_service|content_service)" server/app/domains/task_operations -g "*.py"
```

Expected: pytest passes, app import prints the title, and `rg` returns no task-operation channel/content legacy imports.

- [x] **Step 4: Commit**

```powershell
git add -f docs/superpowers/specs/2026-06-20-task-adapter-domain-imports-design.md docs/superpowers/plans/2026-06-20-task-adapter-domain-imports-plan.md server/tests/test_task_adapter_domain_imports.py server/tests/test_channel_service_domain_facade.py server/tests/test_content_service_domain_facade.py server/app/domains/task_operations/adapters.py
git commit -m "refactor: use task adapter domain imports"
```

# Content Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move content template and sensitive-word service logic into content collection while preserving legacy bridge imports.

**Architecture:** `app.domains.content_collection.content_service` becomes the implementation owner. `app.services.content_service` becomes a `sys.modules` alias facade. `content_collection.content_generation` and `content_collection.mutations` import the domain service directly; task, device, account/channel, and AI generator bridges stay legacy-compatible.

**Tech Stack:** Python, SQLAlchemy `Session`, pytest, Python module aliasing via `sys.modules`.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_content_service_domain_facade.py`
- Read: `server/app/services/content_service.py`
- Read: `server/app/domains/content_collection/content_generation.py`
- Read: `server/app/domains/content_collection/mutations.py`
- Read: `server/app/services/ai_generator.py`
- Read: `server/app/domains/task_operations/adapters.py`
- Read: `server/app/domains/account_operations/channel_service.py`
- Read: `server/app/domains/content_collection/README.md`

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-content-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-content-service-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/content_collection/content_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/content_service.py"
CONTENT_GENERATION_PATH = REPO_ROOT / "server/app/domains/content_collection/content_generation.py"
MUTATIONS_PATH = REPO_ROOT / "server/app/domains/content_collection/mutations.py"
AI_GENERATOR_PATH = REPO_ROOT / "server/app/services/ai_generator.py"
TASK_ADAPTERS_PATH = REPO_ROOT / "server/app/domains/task_operations/adapters.py"
CHANNEL_SERVICE_PATH = REPO_ROOT / "server/app/domains/account_operations/channel_service.py"
README_PATH = REPO_ROOT / "server/app/domains/content_collection/README.md"


def test_content_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.content_collection.content_service",
        "app.services.content_service",
        "ContentService",
    ]:
        assert term in spec
        assert term in plan
```

- [x] **Step 2: Complete the test file**

```python
def test_content_service_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_content_service_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.content_collection" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "class ContentService" not in text
    assert "content_service = ContentService()" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_content_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.content_service")
        domain = importlib.import_module("app.domains.content_collection.content_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"content service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.ContentService is domain.ContentService
    assert legacy.content_service is domain.content_service
    assert legacy._build_ac_automaton is domain._build_ac_automaton
    assert legacy._ac_contains is domain._ac_contains
    assert legacy._db_template_to_response is domain._db_template_to_response
    assert legacy._db_word_to_response is domain._db_word_to_response


def test_services_parent_package_content_service_attribute_is_domain_module():
    from app.services import content_service as parent_import

    domain = importlib.import_module("app.domains.content_collection.content_service")

    assert parent_import is domain
    assert parent_import.content_service is domain.content_service


def test_content_collection_modules_import_domain_content_service_only():
    for path in [CONTENT_GENERATION_PATH, MUTATIONS_PATH]:
        text = path.read_text(encoding="utf-8")
        assert "app.domains.content_collection.content_service" in text
        assert "app.services.content_service" not in text


def test_bridges_stay_legacy_compatible():
    for path in [AI_GENERATOR_PATH, TASK_ADAPTERS_PATH, CHANNEL_SERVICE_PATH]:
        text = path.read_text(encoding="utf-8")
        assert "app.services.content_service" in text
        assert "app.domains.content_collection.content_service" not in text


def test_content_collection_docs_register_content_service_facade():
    readme = README_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.content_collection.content_service",
        "app.services.content_service",
        "ContentService",
        "approved task/device/account/AI bridge compatibility imports",
        "remove only when that command returns no production imports",
    ]:
        assert term in readme


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
```

- [x] **Step 3: Run the red test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_service_domain_facade.py -q
```

Expected: FAIL because the domain file, facade, direct content collection imports, and README entries do not exist yet.

### Task 2: Domain Migration

**Files:**
- Create: `server/app/domains/content_collection/content_service.py`
- Modify: `server/app/services/content_service.py`
- Modify: `server/app/domains/content_collection/content_generation.py`
- Modify: `server/app/domains/content_collection/mutations.py`

- [x] **Step 1: Move implementation**

Move the current service body into:

```text
server/app/domains/content_collection/content_service.py
```

Use this module docstring:

```python
"""Content template and sensitive word service for content collection."""
```

- [x] **Step 2: Replace legacy module with facade**

```python
"""Compatibility facade for content collection services."""

import sys

from app.domains.content_collection import content_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [x] **Step 3: Update content collection imports**

Replace `from app.services.content_service import content_service` with:

```python
from app.domains.content_collection.content_service import content_service
```

### Task 3: Documentation Update

**Files:**
- Modify: `server/app/domains/content_collection/README.md`

- [x] **Step 1: Add ownership rule**

```markdown
- `app.domains.content_collection.content_service` owns `ContentService` template CRUD, sensitive-word CRUD/matching, variable substitution, and content-generation helpers.
```

- [x] **Step 2: Add facade register row**

```markdown
| `app.services.content_service` | `app.domains.content_collection.content_service` | Content service domain slice | Keep while `rg -n "app\.services\.content_service" server/app -g "*.py"` returns approved task/device/account/AI bridge compatibility imports; remove only when that command returns no production imports. |
```

### Task 4: Verification

- [x] **Step 1: Run boundary test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_service_domain_facade.py -q
```

Expected: PASS.

- [x] **Step 2: Run content behavior tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_service.py server/tests/test_content_api.py server/tests/test_content_collection_mutations.py -q
```

Expected: PASS.

- [x] **Step 3: Run bridge compatibility tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_collection_device_bridge.py server/tests/test_device_operations_content_bridge.py server/tests/test_tasks_api.py -q
```

Expected: PASS.

- [x] **Step 4: Verify cleanup inventory**

```powershell
rg -n "app\.services\.content_service" server/app -g "*.py"
```

Expected: only approved task/device/account/AI bridge compatibility imports.

- [x] **Step 5: Commit**

```powershell
git add -f docs/superpowers/specs/2026-06-20-content-service-domain-design.md docs/superpowers/plans/2026-06-20-content-service-domain-plan.md server/tests/test_content_service_domain_facade.py server/app/domains/content_collection/content_service.py server/app/services/content_service.py server/app/domains/content_collection/content_generation.py server/app/domains/content_collection/mutations.py server/app/domains/content_collection/README.md
git commit -m "refactor: move content service into content collection"
```

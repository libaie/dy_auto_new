# DM Sequence Visibility Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move DM sequence visibility rules into the content collection domain while preserving legacy imports and device polling behavior.

**Architecture:** `app.domains.content_collection.dm_sequence_visibility` becomes the implementation owner. `app.services.dm_sequence_visibility` becomes a `sys.modules` alias facade. `content_collection.mutations` imports the domain service directly, while `device_operations.polling` can continue through the legacy facade until the device bridge cleanup slice.

**Tech Stack:** Python, SQLAlchemy `Session`, FastAPI route modules, pytest, Python module aliasing via `sys.modules`.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_dm_sequence_visibility_domain_facade.py`
- Read: `server/app/services/dm_sequence_visibility.py`
- Read: `server/app/domains/content_collection/mutations.py`
- Read: `server/app/domains/device_operations/polling.py`
- Read: `server/app/domains/content_collection/README.md`

- [ ] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-dm-sequence-visibility-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-dm-sequence-visibility-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/content_collection/dm_sequence_visibility.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/dm_sequence_visibility.py"
MUTATIONS_PATH = REPO_ROOT / "server/app/domains/content_collection/mutations.py"
DEVICE_POLLING_PATH = REPO_ROOT / "server/app/domains/device_operations/polling.py"
README_PATH = REPO_ROOT / "server/app/domains/content_collection/README.md"


def test_dm_sequence_visibility_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.content_collection.dm_sequence_visibility",
        "app.services.dm_sequence_visibility",
        "get_device_visible_dm_sequences",
    ]:
        assert term in spec
        assert term in plan
```

- [ ] **Step 2: Complete the test file**

```python
def test_dm_sequence_visibility_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_dm_sequence_visibility_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.content_collection" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def get_device_visible_dm_sequences" not in text
    assert "Task.status.in_" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_dm_sequence_visibility_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.dm_sequence_visibility")
        domain = importlib.import_module("app.domains.content_collection.dm_sequence_visibility")
    except ModuleNotFoundError as exc:
        pytest.fail(f"dm sequence visibility domain import failed: {exc}")

    assert legacy is domain
    assert legacy.get_device_visible_dm_sequences is domain.get_device_visible_dm_sequences
    assert legacy._extract_sequence_id is domain._extract_sequence_id
    assert legacy._task_sequence_ids_for_device is domain._task_sequence_ids_for_device


def test_services_parent_package_dm_sequence_visibility_attribute_is_domain_module():
    from app.services import dm_sequence_visibility as parent_import

    domain = importlib.import_module("app.domains.content_collection.dm_sequence_visibility")

    assert parent_import is domain
    assert parent_import.get_device_visible_dm_sequences is domain.get_device_visible_dm_sequences


def test_content_collection_mutations_imports_domain_visibility_only():
    text = MUTATIONS_PATH.read_text(encoding="utf-8")

    assert "app.domains.content_collection.dm_sequence_visibility" in text
    assert "app.services.dm_sequence_visibility" not in text


def test_device_polling_stays_device_owned_and_legacy_compatible():
    text = DEVICE_POLLING_PATH.read_text(encoding="utf-8")

    assert "app.services.dm_sequence_visibility" in text
    assert "app.domains.content_collection.dm_sequence_visibility" not in text


def test_content_collection_docs_register_dm_sequence_visibility_facade():
    readme = README_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.content_collection.dm_sequence_visibility",
        "app.services.dm_sequence_visibility",
        "get_device_visible_dm_sequences",
        'rg -n "app\\.services\\.dm_sequence_visibility" server/app -g "*.py"',
    ]:
        assert term in readme


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
```

- [ ] **Step 3: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_dm_sequence_visibility_domain_facade.py -q
```

Expected: FAIL because the domain service file, legacy facade, direct domain
import, and README updates do not exist yet.

### Task 2: Domain Migration

**Files:**
- Move: `server/app/services/dm_sequence_visibility.py` to `server/app/domains/content_collection/dm_sequence_visibility.py`
- Modify: `server/app/services/dm_sequence_visibility.py`
- Modify: `server/app/domains/content_collection/mutations.py`

- [ ] **Step 1: Move the implementation**

Move the current service implementation into:

```text
server/app/domains/content_collection/dm_sequence_visibility.py
```

Keep the implementation body unchanged except for the module docstring:

```python
"""DM sequence visibility rules for content collection."""
```

- [ ] **Step 2: Replace the legacy module with a facade**

```python
"""Compatibility facade for DM sequence visibility rules."""

import sys

from app.domains.content_collection import dm_sequence_visibility as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [ ] **Step 3: Update content collection import**

Replace:

```python
from app.services.dm_sequence_visibility import get_device_visible_dm_sequences
```

with:

```python
from app.domains.content_collection.dm_sequence_visibility import get_device_visible_dm_sequences
```

Keep `device_operations.polling` on the legacy import path in this slice.

### Task 3: Documentation Update

**Files:**
- Modify: `server/app/domains/content_collection/README.md`

- [ ] **Step 1: Update ownership rules**

Add:

```markdown
- `app.domains.content_collection.dm_sequence_visibility` owns DM sequence visibility rules for device sync and polling payload inclusion.
```

- [ ] **Step 2: Update facade register**

Add:

```markdown
| `app.services.dm_sequence_visibility` | `app.domains.content_collection.dm_sequence_visibility` | DM sequence visibility slice | `rg -n "app\.services\.dm_sequence_visibility" server/app -g "*.py"` returns only approved device bridge compatibility imports. |
```

- [ ] **Step 3: Update cleanup gates**

Add:

```markdown
- Do not remove `app.services.dm_sequence_visibility` until device bridge cleanup either imports the domain service directly or documents the legacy import as the approved compatibility path.
```

### Task 4: Verification

- [ ] **Step 1: Run the new domain facade test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_dm_sequence_visibility_domain_facade.py -q
```

Expected: PASS.

- [ ] **Step 2: Run DM sequence behavior tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_dm_sequences_api.py -q
```

Expected: PASS.

- [ ] **Step 3: Run content collection boundary tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_collection_domain_boundary.py -q
```

Expected: PASS.

- [ ] **Step 4: Run device polling regression tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_polling_reporting.py server/tests/test_device_operations_uploads.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Stage only the files in this slice:

```powershell
git add -f docs/superpowers/specs/2026-06-20-dm-sequence-visibility-domain-design.md docs/superpowers/plans/2026-06-20-dm-sequence-visibility-domain-plan.md server/tests/test_dm_sequence_visibility_domain_facade.py server/app/domains/content_collection/dm_sequence_visibility.py server/app/services/dm_sequence_visibility.py server/app/domains/content_collection/mutations.py server/app/domains/content_collection/README.md
git commit -m "refactor: move dm sequence visibility into content collection"
```

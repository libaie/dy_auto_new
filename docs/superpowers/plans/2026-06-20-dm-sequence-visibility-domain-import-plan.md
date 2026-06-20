# DM Sequence Visibility Domain Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Point device polling at the content-collection DM sequence visibility domain module.

**Architecture:** DM sequence visibility behavior already lives in `app.domains.content_collection.dm_sequence_visibility`. This change updates one lazy import and leaves the service facade intact.

**Tech Stack:** Python, pytest, existing compatibility facade.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_dm_sequence_visibility_domain_import.py`
- Read: `server/app/domains/device_operations/polling.py`

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-dm-sequence-visibility-domain-import-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-dm-sequence-visibility-domain-import-plan.md"
POLLING_PATH = REPO_ROOT / "server/app/domains/device_operations/polling.py"


def test_dm_sequence_visibility_import_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.content_collection.dm_sequence_visibility",
        "app.services.dm_sequence_visibility",
        "device_operations.polling",
    ]:
        assert term in spec
        assert term in plan
```

- [x] **Step 2: Complete the boundary test**

```python
def test_device_polling_imports_dm_sequence_visibility_from_domain_path():
    text = POLLING_PATH.read_text(encoding="utf-8")
    assert "app.domains.content_collection.dm_sequence_visibility" in text
    assert "app.services.dm_sequence_visibility" not in text


def test_legacy_dm_sequence_visibility_facade_still_resolves_to_domain_module():
    legacy = importlib.import_module("app.services.dm_sequence_visibility")
    domain = importlib.import_module("app.domains.content_collection.dm_sequence_visibility")
    assert legacy is domain
    assert legacy.get_device_visible_dm_sequences is domain.get_device_visible_dm_sequences
```

- [x] **Step 3: Run the red test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_dm_sequence_visibility_domain_import.py -q
```

Expected: FAIL because `polling.py` still imports the legacy service facade.

### Task 2: Import Migration

**Files:**
- Modify: `server/app/domains/device_operations/polling.py`
- Modify: `server/tests/test_dm_sequence_visibility_domain_facade.py`

- [x] **Step 1: Replace legacy import**

```python
from app.domains.content_collection.dm_sequence_visibility import get_device_visible_dm_sequences
```

- [x] **Step 2: Update existing facade boundary expectation**

```python
def test_device_polling_imports_domain_visibility_directly():
    text = DEVICE_POLLING_PATH.read_text(encoding="utf-8")

    assert "app.domains.content_collection.dm_sequence_visibility" in text
    assert "app.services.dm_sequence_visibility" not in text
```

- [x] **Step 3: Run verification**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_dm_sequence_visibility_domain_import.py server/tests/test_dm_sequence_visibility_domain_facade.py -q
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
rg -n "from app\.services\.dm_sequence_visibility" server/app/domains -g "*.py"
```

Expected: pytest passes, app import prints the title, and `rg` returns no domain matches.

- [x] **Step 4: Commit**

```powershell
git add -f docs/superpowers/specs/2026-06-20-dm-sequence-visibility-domain-import-design.md docs/superpowers/plans/2026-06-20-dm-sequence-visibility-domain-import-plan.md server/tests/test_dm_sequence_visibility_domain_import.py server/tests/test_dm_sequence_visibility_domain_facade.py server/app/domains/device_operations/polling.py
git commit -m "refactor: use dm sequence visibility domain import"
```

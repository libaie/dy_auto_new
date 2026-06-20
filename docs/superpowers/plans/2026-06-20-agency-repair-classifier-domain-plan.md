# Agency Repair Classifier Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move agency repair-task classification into `app.domains.agency_operations` with a legacy facade.

**Architecture:** Copy the current implementation into `server/app/domains/agency_operations/agency_repair_classifier.py`, change its contract import to the domain path, then replace `server/app/services/agency_repair_classifier.py` with a `sys.modules` facade. Dirty service modules keep legacy imports for this slice.

**Tech Stack:** Python, Pydantic, pytest.

---

## Files

- Create: `server/app/domains/agency_operations/agency_repair_classifier.py`
- Modify: `server/app/services/agency_repair_classifier.py`
- Modify: `server/app/domains/agency_operations/README.md`
- Create: `server/tests/test_agency_repair_classifier_facade.py`

### Task 1: Boundary Test

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-agency-repair-classifier-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-agency-repair-classifier-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/agency_operations/agency_repair_classifier.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/agency_repair_classifier.py"
README_PATH = REPO_ROOT / "server/app/domains/agency_operations/README.md"


def test_agency_repair_classifier_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.agency_operations.agency_repair_classifier",
        "app.services.agency_repair_classifier",
        "app.domains.agency_operations.agency_repair_contracts",
        "classify_repair_tasks",
    ]:
        assert term in spec
        assert term in plan


def test_agency_repair_classifier_implementation_lives_in_agency_operations_domain():
    domain_text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "def classify_repair_tasks" in domain_text
    assert "def _needs_manual_from_summary" in domain_text
    assert "app.domains.agency_operations.agency_repair_contracts" in domain_text
    assert "app.services.agency_repair_contracts" not in domain_text

    legacy_text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations" in legacy_text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in legacy_text
    assert "def classify_repair_tasks" not in legacy_text


def test_legacy_agency_repair_classifier_facade_resolves_to_domain_module():
    domain = importlib.import_module("app.domains.agency_operations.agency_repair_classifier")
    legacy = importlib.import_module("app.services.agency_repair_classifier")
    assert legacy is domain
    assert legacy.classify_repair_tasks is domain.classify_repair_tasks

    manual = legacy.classify_repair_tasks(
        {"summary": "已记录审查发现"},
        stage="style_lock",
        series_id="series-1",
    )
    assert manual.manual_gate_required is True
    assert manual.repair_tasks[0].type == "manual_incomplete_repair_task"

    paid = legacy.classify_repair_tasks(
        {"repair_tasks": [{"type": "image_generation_failed", "stage": "image", "target_id": "seg-1", "auto_execute": True}]},
        stage="image",
        series_id="series-1",
    )
    assert paid.repairable is True
    assert paid.repair_tasks[0].requires_paid_provider is True


def test_agency_operations_readme_registers_repair_classifier_facade():
    text = README_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations.agency_repair_classifier" in text
    assert "app.services.agency_repair_classifier" in text
```

- [x] **Step 2: Verify RED**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_repair_classifier_facade.py -q
```

Expected: fails because the domain module does not exist and the README has no
facade row.

### Task 2: Minimal Migration

- [x] **Step 1: Copy implementation**

Run:

```powershell
Copy-Item -LiteralPath 'server/app/services/agency_repair_classifier.py' -Destination 'server/app/domains/agency_operations/agency_repair_classifier.py'
```

- [x] **Step 2: Update canonical contract import**

Change:

```python
from app.services.agency_repair_contracts import (
```

to:

```python
from app.domains.agency_operations.agency_repair_contracts import (
```

- [x] **Step 3: Replace legacy file with facade**

```python
"""Compatibility facade for agency repair classifier helpers."""

import sys

from app.domains.agency_operations import agency_repair_classifier as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
```

- [x] **Step 4: Register facade**

Add this README row:

```markdown
| `app.services.agency_repair_classifier` | `app.domains.agency_operations.agency_repair_classifier` | Keep while dirty service modules import the repair classifier from `app.services`; remove after import inventory is clean. |
```

- [x] **Step 5: Verify GREEN**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_repair_classifier_facade.py server/tests/test_agency_repair_classifier.py server/tests/test_agency_repair_loop.py -q
```

Expected: all tests pass.

### Task 3: Final Checks

- [x] **Step 1: Import app**

Run from `server`:

```powershell
..\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
```

Expected: exits 0.

- [x] **Step 2: Diff check**

Run:

```powershell
git diff --check -- docs/superpowers/specs/2026-06-20-agency-repair-classifier-domain-design.md docs/superpowers/plans/2026-06-20-agency-repair-classifier-domain-plan.md server/tests/test_agency_repair_classifier_facade.py server/app/domains/agency_operations/agency_repair_classifier.py server/app/services/agency_repair_classifier.py server/app/domains/agency_operations/README.md
```

Expected: exits 0.

- [x] **Step 3: Commit target files only**

Run:

```powershell
git add -f docs/superpowers/specs/2026-06-20-agency-repair-classifier-domain-design.md docs/superpowers/plans/2026-06-20-agency-repair-classifier-domain-plan.md server/tests/test_agency_repair_classifier_facade.py server/app/domains/agency_operations/agency_repair_classifier.py server/app/services/agency_repair_classifier.py server/app/domains/agency_operations/README.md
git commit --only docs/superpowers/specs/2026-06-20-agency-repair-classifier-domain-design.md docs/superpowers/plans/2026-06-20-agency-repair-classifier-domain-plan.md server/tests/test_agency_repair_classifier_facade.py server/app/domains/agency_operations/agency_repair_classifier.py server/app/services/agency_repair_classifier.py server/app/domains/agency_operations/README.md -m "refactor: move agency repair classifier into agency operations"
```

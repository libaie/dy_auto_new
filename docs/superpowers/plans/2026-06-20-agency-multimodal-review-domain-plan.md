# Agency Multimodal Review Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move agency multimodal asset review helpers into `agency_operations` while preserving legacy monkeypatch imports.

**Architecture:** `app.domains.agency_operations.agency_multimodal_review` owns context building and review dispatch. `app.services.agency_multimodal_review` aliases the domain module. `agency_router.py` imports the domain helper directly.

**Tech Stack:** Python, FastAPI route module, pytest.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_agency_multimodal_review_facade.py`
- Keep: `server/tests/test_agency_multimodal_review.py`

- [ ] **Step 1: Add this test file**

```python
import importlib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-agency-multimodal-review-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-agency-multimodal-review-domain-plan.md"
README_PATH = REPO_ROOT / "server/app/domains/agency_operations/README.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/agency_operations/agency_multimodal_review.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/agency_multimodal_review.py"
ROUTER_PATH = REPO_ROOT / "server/app/domains/agency_operations/agency_router.py"


def test_agency_multimodal_review_spec_plan_and_readme_document_boundary():
    combined = SPEC_PATH.read_text(encoding="utf-8") + PLAN_PATH.read_text(encoding="utf-8")
    for expected in (
        "app.domains.agency_operations.agency_multimodal_review",
        "app.services.agency_multimodal_review",
        "build_multimodal_asset_context",
        "run_multimodal_asset_review",
    ):
        assert expected in combined

    readme = README_PATH.read_text(encoding="utf-8")
    assert "agency_multimodal_review.py" in readme
    assert "app.domains.agency_operations.agency_multimodal_review" in readme
    assert "app.services.agency_multimodal_review" in readme


def test_agency_multimodal_review_domain_file_owns_helpers():
    text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "def build_multimodal_asset_context" in text
    assert "async def run_multimodal_asset_review" in text


def test_legacy_agency_multimodal_review_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations import agency_multimodal_review" in text
    assert "sys.modules[_LEGACY_MODULE_NAME] = _domain_module" in text
    assert "def build_multimodal_asset_context" not in text
    assert "async def run_multimodal_asset_review" not in text


def test_legacy_agency_multimodal_review_module_aliases_domain():
    for name in (
        "app.services.agency_multimodal_review",
        "app.domains.agency_operations.agency_multimodal_review",
    ):
        sys.modules.pop(name, None)

    legacy = importlib.import_module("app.services.agency_multimodal_review")
    domain = importlib.import_module("app.domains.agency_operations.agency_multimodal_review")

    assert sys.modules["app.services.agency_multimodal_review"] is domain
    assert legacy.build_multimodal_asset_context is domain.build_multimodal_asset_context
    assert legacy.run_multimodal_asset_review is domain.run_multimodal_asset_review


def test_agency_router_imports_multimodal_review_from_domain():
    text = ROUTER_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations.agency_multimodal_review" in text
    assert "app.services.agency_multimodal_review" not in text
```

- [ ] **Step 2: Verify red**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_multimodal_review_facade.py -q
```

Expected: FAIL because the domain module and README registration do not exist and the legacy service still owns helper bodies.

### Task 2: Move Multimodal Review

**Files:**
- Create: `server/app/domains/agency_operations/agency_multimodal_review.py`
- Modify: `server/app/services/agency_multimodal_review.py`
- Modify: `server/app/domains/agency_operations/agency_router.py`
- Modify: `server/app/domains/agency_operations/README.md`

- [ ] **Step 1: Copy implementation to the domain module**

Copy `server/app/services/agency_multimodal_review.py` to
`server/app/domains/agency_operations/agency_multimodal_review.py`.

- [ ] **Step 2: Replace legacy service with this facade**

```python
"""Compatibility facade for agency multimodal review helpers."""

import sys

from app.domains.agency_operations import agency_multimodal_review as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_domain_module.__name__] = _domain_module
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
```

- [ ] **Step 3: Update router import**

Change the multimodal review route local import to:

```python
from app.domains.agency_operations.agency_multimodal_review import run_multimodal_asset_review
```

- [ ] **Step 4: Update README**

Add `agency_multimodal_review.py` to Current Modules and this facade row:

```markdown
| `app.services.agency_multimodal_review` | `app.domains.agency_operations.agency_multimodal_review` | Keep while legacy tests monkeypatch multimodal review through `app.services`; remove after import inventory is clean. |
```

- [ ] **Step 5: Verify green**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_multimodal_review_facade.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_multimodal_review.py -q
git diff --check -- docs/superpowers/specs/2026-06-20-agency-multimodal-review-domain-design.md docs/superpowers/plans/2026-06-20-agency-multimodal-review-domain-plan.md server/tests/test_agency_multimodal_review_facade.py server/tests/test_agency_multimodal_review.py server/app/domains/agency_operations/agency_multimodal_review.py server/app/services/agency_multimodal_review.py server/app/domains/agency_operations/agency_router.py server/app/domains/agency_operations/README.md
```

Expected: both pytest commands pass and `git diff --check` exits 0.

- [ ] **Step 6: Commit target files only**

```powershell
git add -f docs/superpowers/specs/2026-06-20-agency-multimodal-review-domain-design.md docs/superpowers/plans/2026-06-20-agency-multimodal-review-domain-plan.md server/tests/test_agency_multimodal_review_facade.py server/tests/test_agency_multimodal_review.py server/app/domains/agency_operations/agency_multimodal_review.py server/app/services/agency_multimodal_review.py server/app/domains/agency_operations/agency_router.py server/app/domains/agency_operations/README.md
git commit --only docs/superpowers/specs/2026-06-20-agency-multimodal-review-domain-design.md docs/superpowers/plans/2026-06-20-agency-multimodal-review-domain-plan.md server/tests/test_agency_multimodal_review_facade.py server/tests/test_agency_multimodal_review.py server/app/domains/agency_operations/agency_multimodal_review.py server/app/services/agency_multimodal_review.py server/app/domains/agency_operations/agency_router.py server/app/domains/agency_operations/README.md -m "refactor: move agency multimodal review into domain"
```

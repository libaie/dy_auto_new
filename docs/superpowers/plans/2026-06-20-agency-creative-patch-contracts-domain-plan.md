# Agency Creative Patch Contracts Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move creative patch contract validation into `agency_operations` while preserving the legacy service import.

**Architecture:** `app.domains.agency_operations.agency_creative_patch_contracts` owns the enums, `CreativePatchProposal`, and `normalize_patch_payload`. `app.services.agency_creative_patch_contracts` aliases the domain module.

**Tech Stack:** Python, Pydantic, pytest.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_agency_creative_patch_contracts_facade.py`
- Keep: `server/tests/test_agency_creative_patch_contracts.py`

- [ ] **Step 1: Add this test file**

```python
import importlib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-agency-creative-patch-contracts-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-agency-creative-patch-contracts-domain-plan.md"
README_PATH = REPO_ROOT / "server/app/domains/agency_operations/README.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/agency_operations/agency_creative_patch_contracts.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/agency_creative_patch_contracts.py"


def test_agency_creative_patch_contracts_spec_plan_and_readme_document_boundary():
    combined = SPEC_PATH.read_text(encoding="utf-8") + PLAN_PATH.read_text(encoding="utf-8")
    for expected in (
        "app.domains.agency_operations.agency_creative_patch_contracts",
        "app.services.agency_creative_patch_contracts",
        "CreativePatchProposal",
        "normalize_patch_payload",
    ):
        assert expected in combined

    readme = README_PATH.read_text(encoding="utf-8")
    assert "agency_creative_patch_contracts.py" in readme
    assert "app.domains.agency_operations.agency_creative_patch_contracts" in readme
    assert "app.services.agency_creative_patch_contracts" in readme


def test_agency_creative_patch_contracts_domain_file_owns_contracts():
    text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "class CreativePatchProposal" in text
    assert "def normalize_patch_payload" in text
    assert "creative patch after must include at least one executable allowed field" in text


def test_legacy_agency_creative_patch_contracts_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations import agency_creative_patch_contracts" in text
    assert "sys.modules[_LEGACY_MODULE_NAME] = _domain_module" in text
    assert "class CreativePatchProposal" not in text
    assert "def normalize_patch_payload" not in text


def test_legacy_agency_creative_patch_contracts_module_aliases_domain():
    for name in (
        "app.services.agency_creative_patch_contracts",
        "app.domains.agency_operations.agency_creative_patch_contracts",
    ):
        sys.modules.pop(name, None)

    legacy = importlib.import_module("app.services.agency_creative_patch_contracts")
    domain = importlib.import_module("app.domains.agency_operations.agency_creative_patch_contracts")

    assert sys.modules["app.services.agency_creative_patch_contracts"] is domain
    assert legacy.CreativePatchProposal is domain.CreativePatchProposal
    assert legacy.normalize_patch_payload is domain.normalize_patch_payload
```

- [ ] **Step 2: Verify red**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_creative_patch_contracts_facade.py -q
```

Expected: FAIL because the domain module and README registration do not exist and the legacy service still owns contract bodies.

### Task 2: Move Contracts

**Files:**
- Create: `server/app/domains/agency_operations/agency_creative_patch_contracts.py`
- Modify: `server/app/services/agency_creative_patch_contracts.py`
- Modify: `server/app/domains/agency_operations/README.md`

- [ ] **Step 1: Copy implementation to the domain module**

Copy `server/app/services/agency_creative_patch_contracts.py` to
`server/app/domains/agency_operations/agency_creative_patch_contracts.py`.

- [ ] **Step 2: Replace legacy service with this facade**

```python
"""Compatibility facade for agency creative patch contracts."""

import sys

from app.domains.agency_operations import agency_creative_patch_contracts as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_domain_module.__name__] = _domain_module
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
```

- [ ] **Step 3: Update README**

Add `agency_creative_patch_contracts.py` to Current Modules and this facade row:

```markdown
| `app.services.agency_creative_patch_contracts` | `app.domains.agency_operations.agency_creative_patch_contracts` | Keep while dirty creative patch service code imports contracts from `app.services`; remove after import inventory is clean. |
```

- [ ] **Step 4: Verify green**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_creative_patch_contracts_facade.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_creative_patch_contracts.py -q
git diff --check -- docs/superpowers/specs/2026-06-20-agency-creative-patch-contracts-domain-design.md docs/superpowers/plans/2026-06-20-agency-creative-patch-contracts-domain-plan.md server/tests/test_agency_creative_patch_contracts_facade.py server/tests/test_agency_creative_patch_contracts.py server/app/domains/agency_operations/agency_creative_patch_contracts.py server/app/services/agency_creative_patch_contracts.py server/app/domains/agency_operations/README.md
```

Expected: both pytest commands pass and `git diff --check` exits 0.

- [ ] **Step 5: Commit target files only**

```powershell
git add -f docs/superpowers/specs/2026-06-20-agency-creative-patch-contracts-domain-design.md docs/superpowers/plans/2026-06-20-agency-creative-patch-contracts-domain-plan.md server/tests/test_agency_creative_patch_contracts_facade.py server/tests/test_agency_creative_patch_contracts.py server/app/domains/agency_operations/agency_creative_patch_contracts.py server/app/services/agency_creative_patch_contracts.py server/app/domains/agency_operations/README.md
git commit --only docs/superpowers/specs/2026-06-20-agency-creative-patch-contracts-domain-design.md docs/superpowers/plans/2026-06-20-agency-creative-patch-contracts-domain-plan.md server/tests/test_agency_creative_patch_contracts_facade.py server/tests/test_agency_creative_patch_contracts.py server/app/domains/agency_operations/agency_creative_patch_contracts.py server/app/services/agency_creative_patch_contracts.py server/app/domains/agency_operations/README.md -m "refactor: move agency creative patch contracts into domain"
```

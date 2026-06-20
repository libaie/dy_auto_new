# Agency Scorecard Contracts Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move agency scorecard contract helpers into `agency_operations` while preserving the legacy service import.

**Architecture:** `app.domains.agency_operations.agency_scorecard_contracts` owns `normalize_scorecard` and `scorecard_blocks_stage`. `app.services.agency_scorecard_contracts` aliases the domain module.

**Tech Stack:** Python, pytest.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_agency_scorecard_contracts_facade.py`
- Keep: `server/tests/test_agency_scorecard_contracts.py`

- [ ] **Step 1: Add this test file**

```python
import importlib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-agency-scorecard-contracts-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-agency-scorecard-contracts-domain-plan.md"
README_PATH = REPO_ROOT / "server/app/domains/agency_operations/README.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/agency_operations/agency_scorecard_contracts.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/agency_scorecard_contracts.py"


def test_agency_scorecard_contracts_spec_plan_and_readme_document_boundary():
    combined = SPEC_PATH.read_text(encoding="utf-8") + PLAN_PATH.read_text(encoding="utf-8")
    for expected in (
        "app.domains.agency_operations.agency_scorecard_contracts",
        "app.services.agency_scorecard_contracts",
        "normalize_scorecard",
        "scorecard_blocks_stage",
    ):
        assert expected in combined

    readme = README_PATH.read_text(encoding="utf-8")
    assert "agency_scorecard_contracts.py" in readme
    assert "app.domains.agency_operations.agency_scorecard_contracts" in readme
    assert "app.services.agency_scorecard_contracts" in readme


def test_agency_scorecard_contracts_domain_file_owns_helpers():
    text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "def normalize_scorecard" in text
    assert "def scorecard_blocks_stage" in text
    assert "SCORECARD_SCHEMA_VERSION" in text


def test_legacy_agency_scorecard_contracts_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations import agency_scorecard_contracts" in text
    assert "sys.modules[_LEGACY_MODULE_NAME] = _domain_module" in text
    assert "def normalize_scorecard" not in text
    assert "def scorecard_blocks_stage" not in text


def test_legacy_agency_scorecard_contracts_module_is_domain_module():
    for name in (
        "app.services.agency_scorecard_contracts",
        "app.domains.agency_operations.agency_scorecard_contracts",
    ):
        sys.modules.pop(name, None)

    legacy = importlib.import_module("app.services.agency_scorecard_contracts")
    domain = importlib.import_module("app.domains.agency_operations.agency_scorecard_contracts")

    assert sys.modules["app.services.agency_scorecard_contracts"] is domain
    assert legacy.normalize_scorecard is domain.normalize_scorecard
    assert legacy.scorecard_blocks_stage is domain.scorecard_blocks_stage
```

- [ ] **Step 2: Verify red**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_scorecard_contracts_facade.py -q
```

Expected: FAIL because the domain module and README registration do not exist and the legacy service still owns helper bodies.

### Task 2: Move Contracts

**Files:**
- Create: `server/app/domains/agency_operations/agency_scorecard_contracts.py`
- Modify: `server/app/services/agency_scorecard_contracts.py`
- Modify: `server/app/domains/agency_operations/README.md`

- [ ] **Step 1: Copy implementation to the domain module**

Copy `server/app/services/agency_scorecard_contracts.py` to
`server/app/domains/agency_operations/agency_scorecard_contracts.py`.

- [ ] **Step 2: Replace legacy service with this facade**

```python
"""Compatibility facade for agency scorecard contracts."""

import sys

from app.domains.agency_operations import agency_scorecard_contracts as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_domain_module.__name__] = _domain_module
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
```

- [ ] **Step 3: Update README**

Add `agency_scorecard_contracts.py` to Current Modules and this facade row:

```markdown
| `app.services.agency_scorecard_contracts` | `app.domains.agency_operations.agency_scorecard_contracts` | Keep while dirty agency service modules import scorecard contracts from `app.services`; remove after import inventory is clean. |
```

- [ ] **Step 4: Verify green**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_scorecard_contracts_facade.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_scorecard_contracts.py -q
git diff --check -- docs/superpowers/specs/2026-06-20-agency-scorecard-contracts-domain-design.md docs/superpowers/plans/2026-06-20-agency-scorecard-contracts-domain-plan.md server/tests/test_agency_scorecard_contracts_facade.py server/app/domains/agency_operations/agency_scorecard_contracts.py server/app/services/agency_scorecard_contracts.py server/app/domains/agency_operations/README.md
```

Expected: both pytest commands pass and `git diff --check` exits 0.

- [ ] **Step 5: Commit target files only**

```powershell
git add -f docs/superpowers/specs/2026-06-20-agency-scorecard-contracts-domain-design.md docs/superpowers/plans/2026-06-20-agency-scorecard-contracts-domain-plan.md server/tests/test_agency_scorecard_contracts_facade.py server/tests/test_agency_scorecard_contracts.py server/app/domains/agency_operations/agency_scorecard_contracts.py server/app/services/agency_scorecard_contracts.py server/app/domains/agency_operations/README.md
git commit --only docs/superpowers/specs/2026-06-20-agency-scorecard-contracts-domain-design.md docs/superpowers/plans/2026-06-20-agency-scorecard-contracts-domain-plan.md server/tests/test_agency_scorecard_contracts_facade.py server/tests/test_agency_scorecard_contracts.py server/app/domains/agency_operations/agency_scorecard_contracts.py server/app/services/agency_scorecard_contracts.py server/app/domains/agency_operations/README.md -m "refactor: move agency scorecard contracts into domain"
```

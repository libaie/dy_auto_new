# Agency Contracts Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move agency API contract models into `app.domains.agency_operations` with a legacy facade.

**Architecture:** Copy the current implementation into `server/app/domains/agency_operations/agency_contracts.py`, then replace `server/app/services/agency_contracts.py` with the existing `sys.modules` facade pattern.

**Tech Stack:** Python, Pydantic, pytest.

---

## Files

- Create: `server/app/domains/agency_operations/agency_contracts.py`
- Modify: `server/app/services/agency_contracts.py`
- Modify: `server/app/domains/agency_operations/README.md`
- Create: `server/tests/test_agency_contracts_facade.py`

### Task 1: Boundary Test

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-agency-contracts-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-agency-contracts-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/agency_operations/agency_contracts.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/agency_contracts.py"
README_PATH = REPO_ROOT / "server/app/domains/agency_operations/README.md"


def test_agency_contracts_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.agency_operations.agency_contracts",
        "app.services.agency_contracts",
        "AgencyConsoleResponse",
        "AgencyInvocationSummary",
        "AgencyExecutionStatus",
    ]:
        assert term in spec
        assert term in plan


def test_agency_contracts_implementation_lives_in_agency_operations_domain():
    domain_text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "class AgencyExecutionStatus" in domain_text
    assert "class AgencyInvocationSummary" in domain_text
    assert "class AgencyConsoleResponse" in domain_text

    legacy_text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations" in legacy_text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in legacy_text
    assert "class AgencyExecutionStatus" not in legacy_text


def test_legacy_agency_contracts_facade_resolves_to_domain_module():
    domain = importlib.import_module("app.domains.agency_operations.agency_contracts")
    legacy = importlib.import_module("app.services.agency_contracts")
    assert legacy is domain
    assert legacy.AgencyConsoleResponse is domain.AgencyConsoleResponse
    assert legacy.AgencyInvocationSummary is domain.AgencyInvocationSummary
    assert legacy.AgencyExecutionStatus is domain.AgencyExecutionStatus

    summary = legacy.AgencyInvocationSummary(
        id="inv-1",
        stage="script",
        expert_id="story-architect",
        role="reviewer",
        execution_status=legacy.AgencyExecutionStatus.running,
        result_status=legacy.AgencyInvocationResultStatus.pending,
    )
    assert summary.execution_status == "running"


def test_agency_operations_readme_registers_contracts_facade():
    text = README_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations.agency_contracts" in text
    assert "app.services.agency_contracts" in text
```

- [x] **Step 2: Verify RED**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_contracts_facade.py -q
```

Expected: fails because the domain module does not exist and the README has no
facade row.

### Task 2: Minimal Migration

- [x] **Step 1: Copy implementation**

Run:

```powershell
Copy-Item -LiteralPath 'server/app/services/agency_contracts.py' -Destination 'server/app/domains/agency_operations/agency_contracts.py'
```

- [x] **Step 2: Replace legacy file with facade**

```python
"""Compatibility facade for agency operation contract models."""

import sys

from app.domains.agency_operations import agency_contracts as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
```

- [x] **Step 3: Register facade**

Add this README row:

```markdown
| `app.services.agency_contracts` | `app.domains.agency_operations.agency_contracts` | Keep while legacy tests or dirty service modules import agency response contracts from `app.services`; remove after import inventory is clean. |
```

- [x] **Step 4: Verify GREEN**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_contracts_facade.py server/tests/test_agency_invocation_models.py -q
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
git diff --check -- docs/superpowers/specs/2026-06-20-agency-contracts-domain-design.md docs/superpowers/plans/2026-06-20-agency-contracts-domain-plan.md server/tests/test_agency_contracts_facade.py server/app/domains/agency_operations/agency_contracts.py server/app/services/agency_contracts.py server/app/domains/agency_operations/README.md
```

Expected: exits 0.

- [x] **Step 3: Commit target files only**

Run:

```powershell
git add -f docs/superpowers/specs/2026-06-20-agency-contracts-domain-design.md docs/superpowers/plans/2026-06-20-agency-contracts-domain-plan.md server/tests/test_agency_contracts_facade.py server/app/domains/agency_operations/agency_contracts.py server/app/services/agency_contracts.py server/app/domains/agency_operations/README.md
git commit --only docs/superpowers/specs/2026-06-20-agency-contracts-domain-design.md docs/superpowers/plans/2026-06-20-agency-contracts-domain-plan.md server/tests/test_agency_contracts_facade.py server/app/domains/agency_operations/agency_contracts.py server/app/services/agency_contracts.py server/app/domains/agency_operations/README.md -m "refactor: move agency contracts into agency operations"
```

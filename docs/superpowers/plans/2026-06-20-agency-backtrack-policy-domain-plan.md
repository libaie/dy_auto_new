# Agency Backtrack Policy Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move agency backtrack policy into `agency_operations` while preserving the legacy service import.

**Architecture:** `app.domains.agency_operations.agency_backtrack_policy` owns `trigger_backtrack_if_needed`. `app.services.agency_backtrack_policy` aliases the domain module for dirty callers that still use the legacy path.

**Tech Stack:** Python, SQLAlchemy ORM, pytest.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_agency_backtrack_policy_facade.py`
- Keep: `server/tests/test_agency_backtrack_policy.py`

- [ ] **Step 1: Add this test file**

```python
import importlib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-agency-backtrack-policy-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-agency-backtrack-policy-domain-plan.md"
README_PATH = REPO_ROOT / "server/app/domains/agency_operations/README.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/agency_operations/agency_backtrack_policy.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/agency_backtrack_policy.py"


def test_agency_backtrack_policy_spec_plan_and_readme_document_boundary():
    combined = SPEC_PATH.read_text(encoding="utf-8") + PLAN_PATH.read_text(encoding="utf-8")
    for expected in (
        "app.domains.agency_operations.agency_backtrack_policy",
        "app.services.agency_backtrack_policy",
        "trigger_backtrack_if_needed",
    ):
        assert expected in combined

    readme = README_PATH.read_text(encoding="utf-8")
    assert "agency_backtrack_policy.py" in readme
    assert "app.domains.agency_operations.agency_backtrack_policy" in readme
    assert "app.services.agency_backtrack_policy" in readme


def test_agency_backtrack_policy_domain_file_owns_policy():
    text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "def trigger_backtrack_if_needed" in text
    assert "BACKTRACK_FAILURE_THRESHOLD" in text
    assert "agency_backtrack_triggered" in text


def test_legacy_agency_backtrack_policy_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations import agency_backtrack_policy" in text
    assert "sys.modules[_LEGACY_MODULE_NAME] = _domain_module" in text
    assert "def trigger_backtrack_if_needed" not in text
    assert "ProductionAuditEvent" not in text


def test_legacy_agency_backtrack_policy_module_aliases_domain():
    for name in (
        "app.services.agency_backtrack_policy",
        "app.domains.agency_operations.agency_backtrack_policy",
    ):
        sys.modules.pop(name, None)

    legacy = importlib.import_module("app.services.agency_backtrack_policy")
    domain = importlib.import_module("app.domains.agency_operations.agency_backtrack_policy")

    assert sys.modules["app.services.agency_backtrack_policy"] is domain
    assert legacy.trigger_backtrack_if_needed is domain.trigger_backtrack_if_needed
```

- [ ] **Step 2: Verify red**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_backtrack_policy_facade.py -q
```

Expected: FAIL because the domain module and README registration do not exist and the legacy service still owns policy logic.

### Task 2: Move Policy

**Files:**
- Create: `server/app/domains/agency_operations/agency_backtrack_policy.py`
- Modify: `server/app/services/agency_backtrack_policy.py`
- Modify: `server/app/domains/agency_operations/README.md`

- [ ] **Step 1: Copy implementation to the domain module**

Copy `server/app/services/agency_backtrack_policy.py` to
`server/app/domains/agency_operations/agency_backtrack_policy.py`.

- [ ] **Step 2: Replace legacy service with this facade**

```python
"""Compatibility facade for agency backtrack policy."""

import sys

from app.domains.agency_operations import agency_backtrack_policy as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_domain_module.__name__] = _domain_module
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
```

- [ ] **Step 3: Update README**

Add `agency_backtrack_policy.py` to Current Modules and this facade row:

```markdown
| `app.services.agency_backtrack_policy` | `app.domains.agency_operations.agency_backtrack_policy` | Keep while dirty video production service code imports backtrack policy from `app.services`; remove after import inventory is clean. |
```

- [ ] **Step 4: Verify green**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_backtrack_policy_facade.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_backtrack_policy.py -q
git diff --check -- docs/superpowers/specs/2026-06-20-agency-backtrack-policy-domain-design.md docs/superpowers/plans/2026-06-20-agency-backtrack-policy-domain-plan.md server/tests/test_agency_backtrack_policy_facade.py server/tests/test_agency_backtrack_policy.py server/app/domains/agency_operations/agency_backtrack_policy.py server/app/services/agency_backtrack_policy.py server/app/domains/agency_operations/README.md
```

Expected: both pytest commands pass and `git diff --check` exits 0.

- [ ] **Step 5: Commit target files only**

```powershell
git add -f docs/superpowers/specs/2026-06-20-agency-backtrack-policy-domain-design.md docs/superpowers/plans/2026-06-20-agency-backtrack-policy-domain-plan.md server/tests/test_agency_backtrack_policy_facade.py server/tests/test_agency_backtrack_policy.py server/app/domains/agency_operations/agency_backtrack_policy.py server/app/services/agency_backtrack_policy.py server/app/domains/agency_operations/README.md
git commit --only docs/superpowers/specs/2026-06-20-agency-backtrack-policy-domain-design.md docs/superpowers/plans/2026-06-20-agency-backtrack-policy-domain-plan.md server/tests/test_agency_backtrack_policy_facade.py server/tests/test_agency_backtrack_policy.py server/app/domains/agency_operations/agency_backtrack_policy.py server/app/services/agency_backtrack_policy.py server/app/domains/agency_operations/README.md -m "refactor: move agency backtrack policy into domain"
```

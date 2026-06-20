# Selector Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move selector CRUD and revision logic into the selector management domain while preserving legacy import compatibility.

**Architecture:** `app.domains.selector_management.selector_service` becomes the implementation owner. `app.services.selector_service` becomes a `sys.modules` alias facade, and `selectors_router.py` imports the domain service directly. Device operations and seed helpers keep using the legacy import path until their domain boundaries move.

**Tech Stack:** Python, SQLAlchemy `Session`, FastAPI route modules, pytest, Python module aliasing via `sys.modules`.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_selector_service_domain_facade.py`
- Read: `server/app/services/selector_service.py`
- Read: `server/app/domains/selector_management/selectors_router.py`
- Read: `server/app/domains/device_operations/script_assets.py`
- Read: `server/app/domains/selector_management/README.md`

- [ ] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-selector-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-selector-service-domain-plan.md"
SELECTOR_SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-selector-management-domain-design.md"
SELECTOR_PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-selector-management-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/selector_management/selector_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/selector_service.py"
SELECTORS_ROUTER_PATH = REPO_ROOT / "server/app/domains/selector_management/selectors_router.py"
DEVICE_SCRIPT_ASSETS_PATH = REPO_ROOT / "server/app/domains/device_operations/script_assets.py"
README_PATH = REPO_ROOT / "server/app/domains/selector_management/README.md"


def test_selector_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.selector_management.selector_service",
        "app.services.selector_service",
        "SelectorService",
        "selector_service",
        "_bump_revision",
    ]:
        assert term in spec
        assert term in plan
```

- [ ] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_selector_service_domain_facade.py -q
```

Expected: FAIL because the domain service file, legacy facade, router direct
domain import, and docs updates do not exist yet.

- [ ] **Step 3: Complete the test file**

Add assertions that:

```python
def test_selector_service_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_selector_service_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.selector_management" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "class SelectorService" not in text
    assert "selector_service = SelectorService()" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_selector_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.selector_service")
        domain = importlib.import_module("app.domains.selector_management.selector_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"selector service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.SelectorService is domain.SelectorService
    assert legacy.selector_service is domain.selector_service
    assert legacy._bump_revision is domain._bump_revision
    assert legacy._aspect_tag is domain._aspect_tag
    assert legacy._profile_priority is domain._profile_priority


def test_selectors_router_imports_domain_selector_service_only():
    text = SELECTORS_ROUTER_PATH.read_text(encoding="utf-8")

    assert "app.domains.selector_management.selector_service" in text
    assert "app.services.selector_service" not in text
    assert "app.services.template_service" in text


def test_device_selectors_stay_device_owned_and_legacy_compatible():
    text = DEVICE_SCRIPT_ASSETS_PATH.read_text(encoding="utf-8")

    assert '@router.get("/selectors")' in text
    assert "app.services.selector_service" in text
    assert "app.domains.selector_management.selector_service" not in text


def test_selector_management_docs_register_selector_service_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    design = SELECTOR_SPEC_PATH.read_text(encoding="utf-8")
    plan = SELECTOR_PLAN_PATH.read_text(encoding="utf-8")

    for text in [readme, design, plan]:
        assert "app.domains.selector_management.selector_service" in text
        assert "app.services.selector_service" in text
        assert "SelectorService" in text or "selector_service" in text

    assert 'rg "app\\.services\\.selector_service" server/app server/tests' in readme


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
```

### Task 2: Domain Migration

**Files:**
- Move: `server/app/services/selector_service.py` to `server/app/domains/selector_management/selector_service.py`
- Modify: `server/app/services/selector_service.py`
- Modify: `server/app/domains/selector_management/selectors_router.py`
- Modify: `server/app/domains/selector_management/README.md`
- Modify: `docs/superpowers/specs/2026-06-20-selector-management-domain-design.md`
- Modify: `docs/superpowers/plans/2026-06-20-selector-management-domain-plan.md`

- [ ] **Step 1: Move the implementation**

Move the service implementation into:

```text
server/app/domains/selector_management/selector_service.py
```

Keep the implementation body unchanged except for the module docstring:

```python
"""Selector management service for selector CRUD and device selector filtering."""
```

- [ ] **Step 2: Replace the legacy module with a facade**

```python
"""Compatibility facade for selector management services."""

import sys

from app.domains.selector_management import selector_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [ ] **Step 3: Update selector management router import**

Replace:

```python
from app.services.selector_service import selector_service
```

with:

```python
from app.domains.selector_management.selector_service import selector_service
```

Keep:

```python
from app.services.template_service import template_service
```

### Task 3: Documentation Updates

**Files:**
- Modify: `server/app/domains/selector_management/README.md`
- Modify: `docs/superpowers/specs/2026-06-20-selector-management-domain-design.md`
- Modify: `docs/superpowers/plans/2026-06-20-selector-management-domain-plan.md`

- [ ] **Step 1: Update README current modules**

Add this module entry:

```markdown
- `selector_service.py` owns `SelectorService`, `selector_service`, selector
  CRUD, revision counter updates, device selector filtering, and selector
  serialization.
```

- [ ] **Step 2: Add facade register row**

```markdown
| `app.services.selector_service` | `app.domains.selector_management.selector_service` | All selector service callers import the domain service directly or belong to domains that have not moved yet. |
```

- [ ] **Step 3: Add cleanup gate**

```markdown
Do not remove the legacy selector service facade until all of these are true:

- `rg "app\.services\.selector_service" server/app server/tests` returns only
  compatibility tests, migration docs, seed helpers, or modules whose domains
  have not moved yet.
- `test_selector_service_domain_facade.py` has been replaced with tests for
  direct domain imports.
- Domain-owned selector management modules import
  `app.domains.selector_management.selector_service` directly.
- Direct domain selector service coverage proves `SelectorService`,
  `selector_service`, and `_bump_revision` behavior without legacy imports.
```

- [ ] **Step 4: Update same-day design and plan docs**

The selector management design must state:

```markdown
Selector CRUD, revision tracking, and device selector filtering now live in
`app.domains.selector_management.selector_service`; `app.services.selector_service`
remains as a temporary compatibility facade.
```

The selector management plan must state:

```markdown
Selector service logic now lives in
`app.domains.selector_management.selector_service`; keep
`app.services.selector_service` as a compatibility facade until direct-domain
coverage replaces legacy imports.
```

### Task 4: Verification And Commit

**Files:**
- Test: `server/tests/test_selector_service_domain_facade.py`
- Test: `server/tests/test_selector_service.py`
- Test: `server/tests/test_selector_management_auth_parity.py`
- Test: `server/tests/test_selector_management_domain_boundary.py`
- Test: `server/tests/test_selector_management_router_facade.py`
- Test: `server/tests/test_device_operations_polling_reporting.py`

- [ ] **Step 1: Run the focused facade test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_selector_service_domain_facade.py -q
```

Expected: PASS.

- [ ] **Step 2: Run selector behavior tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_selector_service.py -q
```

Expected: PASS.

- [ ] **Step 3: Run selector management and device route coverage**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_selector_management_auth_parity.py server/tests/test_selector_management_domain_boundary.py server/tests/test_selector_management_router_facade.py server/tests/test_device_operations_polling_reporting.py -q
```

Expected: PASS.

- [ ] **Step 4: Check for placeholders and import inventory**

Run:

```powershell
$patterns = @("T" + "BD", "TO" + "DO", "implement" + " later", "fill in" + " details", "Similar to" + " Task")
$files = @(
  "docs/superpowers/specs/2026-06-20-selector-service-domain-design.md",
  "docs/superpowers/plans/2026-06-20-selector-service-domain-plan.md",
  "server/tests/test_selector_service_domain_facade.py",
  "server/app/domains/selector_management/selector_service.py",
  "server/app/services/selector_service.py",
  "server/app/domains/selector_management/selectors_router.py",
  "server/app/domains/selector_management/README.md"
)
foreach ($pattern in $patterns) { rg -n --fixed-strings $pattern $files }
rg -n "app\.services\.selector_service|app\.domains\.selector_management\.selector_service" server/app server/tests docs/superpowers -g "*.py" -g "*.md"
```

Expected: no placeholder hits. Import inventory shows direct domain import for
selector management router, and legacy imports only for compatibility tests,
seed helpers, device operations, or domains that have not moved yet.

- [ ] **Step 5: Commit only this migration**

Use an isolated Git index if the real worktree contains unrelated WIP.

Commit message:

```text
refactor: move selector service into selector domain
```

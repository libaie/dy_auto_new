# Device Config Domain Imports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Point device-operation prompt, selector, and template imports at their domain modules.

**Architecture:** Prompt template behavior lives in `app.domains.prompt_management`; selector and template behavior live in `app.domains.selector_management`. Legacy `app.services.*` modules remain `sys.modules` facades.

**Tech Stack:** Python, pytest, existing compatibility facades.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_device_config_domain_imports.py`
- Read: `server/app/domains/device_operations/polling.py`
- Read: `server/app/domains/device_operations/script_assets.py`

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-device-config-domain-imports-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-device-config-domain-imports-plan.md"
POLLING_PATH = REPO_ROOT / "server/app/domains/device_operations/polling.py"
SCRIPT_ASSETS_PATH = REPO_ROOT / "server/app/domains/device_operations/script_assets.py"


def test_device_config_import_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.prompt_management.prompt_template_service",
        "app.domains.selector_management.selector_service",
        "app.domains.selector_management.template_service",
        "app.services.prompt_template_service",
        "app.services.selector_service",
        "app.services.template_service",
    ]:
        assert term in spec
        assert term in plan
```

- [x] **Step 2: Complete the boundary test**

```python
def test_device_operations_import_config_helpers_from_domain_paths():
    polling = POLLING_PATH.read_text(encoding="utf-8")
    script_assets = SCRIPT_ASSETS_PATH.read_text(encoding="utf-8")
    for text in [polling, script_assets]:
        assert "app.domains.prompt_management.prompt_template_service" in text
        assert "app.domains.selector_management.selector_service" in text
        assert "app.services.prompt_template_service" not in text
        assert "app.services.selector_service" not in text
    assert "app.domains.selector_management.template_service" in script_assets
    assert "app.services.template_service" not in script_assets


def test_legacy_device_config_facades_still_resolve_to_domain_modules():
    prompt_legacy = importlib.import_module("app.services.prompt_template_service")
    prompt_domain = importlib.import_module("app.domains.prompt_management.prompt_template_service")
    selector_legacy = importlib.import_module("app.services.selector_service")
    selector_domain = importlib.import_module("app.domains.selector_management.selector_service")
    template_legacy = importlib.import_module("app.services.template_service")
    template_domain = importlib.import_module("app.domains.selector_management.template_service")
    assert prompt_legacy is prompt_domain
    assert prompt_legacy.prompt_template_service is prompt_domain.prompt_template_service
    assert selector_legacy is selector_domain
    assert selector_legacy.selector_service is selector_domain.selector_service
    assert template_legacy is template_domain
    assert template_legacy.template_service is template_domain.template_service
```

- [x] **Step 3: Run the red test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_config_domain_imports.py -q
```

Expected: FAIL because device operation modules still import the legacy service facades.

### Task 2: Import Migration

**Files:**
- Modify: `server/app/domains/device_operations/polling.py`
- Modify: `server/app/domains/device_operations/script_assets.py`
- Modify: `server/tests/test_prompt_template_service_domain_facade.py`
- Modify: `server/tests/test_selector_service_domain_facade.py`
- Modify: `server/tests/test_selector_template_service_domain_facade.py`

- [x] **Step 1: Replace legacy imports**

```python
from app.domains.prompt_management.prompt_template_service import prompt_template_service
from app.domains.selector_management.selector_service import selector_service
from app.domains.selector_management.selector_service import _bump_revision
from app.domains.selector_management.template_service import template_service
```

- [x] **Step 2: Update existing facade boundary expectations**

Existing prompt, selector, and template facade tests should now expect device
operation modules to use the direct domain import and not the legacy service
facade.

- [x] **Step 3: Run verification**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_config_domain_imports.py server/tests/test_prompt_template_service_domain_facade.py server/tests/test_selector_service_domain_facade.py server/tests/test_selector_template_service_domain_facade.py -q
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
rg -n "from app\.services\.(prompt_template_service|selector_service|template_service)" server/app/domains -g "*.py"
```

Expected: pytest passes, app import prints the title, and `rg` returns no domain matches.

- [x] **Step 4: Commit**

```powershell
git add -f docs/superpowers/specs/2026-06-20-device-config-domain-imports-design.md docs/superpowers/plans/2026-06-20-device-config-domain-imports-plan.md server/tests/test_device_config_domain_imports.py server/tests/test_prompt_template_service_domain_facade.py server/tests/test_selector_service_domain_facade.py server/tests/test_selector_template_service_domain_facade.py server/app/domains/device_operations/polling.py server/app/domains/device_operations/script_assets.py
git commit -m "refactor: use device config domain imports"
```

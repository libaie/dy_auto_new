# Prompt Template Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move prompt template CRUD, revision, and rewrite validation helpers into the prompt management domain while preserving legacy imports and monkeypatch paths.

**Architecture:** `app.domains.prompt_management.prompt_template_service` becomes the implementation owner. `app.services.prompt_template_service` becomes a `sys.modules` alias facade, and `prompt_templates_router.py` imports the domain service directly. Device operations and legacy router monkeypatch paths stay compatible through facades.

**Tech Stack:** Python, SQLAlchemy `Session`, FastAPI route modules, pytest, Python module aliasing via `sys.modules`.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_prompt_template_service_domain_facade.py`
- Read: `server/app/services/prompt_template_service.py`
- Read: `server/app/domains/prompt_management/prompt_templates_router.py`
- Read: `server/app/domains/device_operations/script_assets.py`
- Read: `server/app/domains/prompt_management/README.md`

- [ ] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-prompt-template-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-prompt-template-service-domain-plan.md"
PROMPT_SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-prompt-management-domain-design.md"
PROMPT_PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-prompt-management-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/prompt_management/prompt_template_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/prompt_template_service.py"
PROMPT_ROUTER_PATH = REPO_ROOT / "server/app/domains/prompt_management/prompt_templates_router.py"
DEVICE_SCRIPT_ASSETS_PATH = REPO_ROOT / "server/app/domains/device_operations/script_assets.py"
README_PATH = REPO_ROOT / "server/app/domains/prompt_management/README.md"


def test_prompt_template_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.prompt_management.prompt_template_service",
        "app.services.prompt_template_service",
        "PromptTemplateService",
        "prompt_template_service",
        "PROMPT_TEMPLATE_REWRITE_MAX_CONTENT_BYTES",
    ]:
        assert term in spec
        assert term in plan
```

- [ ] **Step 2: Complete the test file**

Add assertions that:

```python
def test_prompt_template_service_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_prompt_template_service_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.prompt_management" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "class PromptTemplateService" not in text
    assert "prompt_template_service = PromptTemplateService()" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_prompt_template_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.prompt_template_service")
        domain = importlib.import_module("app.domains.prompt_management.prompt_template_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"prompt template service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.PromptTemplateService is domain.PromptTemplateService
    assert legacy.prompt_template_service is domain.prompt_template_service
    assert legacy.PROMPT_TEMPLATE_REWRITE_MAX_CONTENT_BYTES is domain.PROMPT_TEMPLATE_REWRITE_MAX_CONTENT_BYTES
    assert legacy._bump_tmpl_revision is domain._bump_tmpl_revision
    assert legacy._to_dict is domain._to_dict
    assert legacy._to_device_dict is domain._to_device_dict


def test_services_parent_package_prompt_template_service_attribute_is_domain_module():
    from app.services import prompt_template_service as parent_import

    domain = importlib.import_module("app.domains.prompt_management.prompt_template_service")

    assert parent_import is domain
    assert parent_import.prompt_template_service is domain.prompt_template_service


def test_prompt_router_imports_domain_prompt_template_service_only():
    text = PROMPT_ROUTER_PATH.read_text(encoding="utf-8")

    assert "app.domains.prompt_management.prompt_template_service" in text
    assert "app.services.prompt_template_service" not in text


def test_legacy_router_facade_preserves_prompt_template_service_patch_path():
    legacy_router = importlib.import_module("app.routers.prompt_templates")
    domain_router = importlib.import_module("app.domains.prompt_management.prompt_templates_router")
    service_domain = importlib.import_module("app.domains.prompt_management.prompt_template_service")

    assert legacy_router is domain_router
    assert legacy_router.prompt_template_service is service_domain.prompt_template_service
    assert domain_router.prompt_template_service is service_domain.prompt_template_service


def test_device_prompt_templates_stay_device_owned_and_legacy_compatible():
    text = DEVICE_SCRIPT_ASSETS_PATH.read_text(encoding="utf-8")

    assert '@router.get("/prompt-templates")' in text
    assert "app.services.prompt_template_service" in text
    assert "app.domains.prompt_management.prompt_template_service" not in text


def test_prompt_management_docs_register_prompt_template_service_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    design = PROMPT_SPEC_PATH.read_text(encoding="utf-8")
    plan = PROMPT_PLAN_PATH.read_text(encoding="utf-8")

    for text in [readme, design, plan]:
        assert "app.domains.prompt_management.prompt_template_service" in text
        assert "app.services.prompt_template_service" in text
        assert "PromptTemplateService" in text or "prompt_template_service" in text

    assert 'rg "app\\.services\\.prompt_template_service" server/app server/tests' in readme
    assert "app.routers.prompt_templates.prompt_template_service" in readme


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
```

- [ ] **Step 3: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_prompt_template_service_domain_facade.py -q
```

Expected: FAIL because the domain service file, legacy facade, router direct
domain import, and docs updates do not exist yet.

### Task 2: Domain Migration

**Files:**
- Move: `server/app/services/prompt_template_service.py` to `server/app/domains/prompt_management/prompt_template_service.py`
- Modify: `server/app/services/prompt_template_service.py`
- Modify: `server/app/domains/prompt_management/prompt_templates_router.py`

- [ ] **Step 1: Move the implementation**

Move the service implementation into:

```text
server/app/domains/prompt_management/prompt_template_service.py
```

Keep the implementation body unchanged except for the module docstring:

```python
"""Prompt template management service for prompt management."""
```

- [ ] **Step 2: Replace the legacy module with a facade**

```python
"""Compatibility facade for prompt template management services."""

import sys

from app.domains.prompt_management import prompt_template_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [ ] **Step 3: Update prompt management router import**

Replace:

```python
from app.services.prompt_template_service import prompt_template_service
```

with:

```python
from app.domains.prompt_management.prompt_template_service import prompt_template_service
```

Keep the logger line:

```python
logger = logging.getLogger("app.routers.prompt_templates")
```

### Task 3: Documentation Updates

**Files:**
- Modify: `server/app/domains/prompt_management/README.md`
- Modify: `docs/superpowers/specs/2026-06-20-prompt-management-domain-design.md`
- Modify: `docs/superpowers/plans/2026-06-20-prompt-management-domain-plan.md`

- [ ] **Step 1: Update README current modules**

Add this module entry:

```markdown
- `prompt_template_service.py` owns `PromptTemplateService`,
  `prompt_template_service`, CRUD, revision tracking, device payloads, rewrite
  request validation, rewrite output validation, serialized-size checks, and
  rewrite prompt construction.
```

- [ ] **Step 2: Add facade register row**

```markdown
| `app.services.prompt_template_service` | `app.domains.prompt_management.prompt_template_service` | All prompt template service callers import the domain service directly or belong to domains that have not moved yet. |
```

- [ ] **Step 3: Add cleanup gate**

```markdown
Do not remove the legacy prompt template service facade until all of these are true:

- `rg "app\.services\.prompt_template_service" server/app server/tests` returns
  only compatibility tests, migration docs, or modules whose domains have not
  moved yet.
- `test_prompt_template_service_domain_facade.py` has been replaced with tests
  for direct domain imports.
- Domain-owned prompt management modules import
  `app.domains.prompt_management.prompt_template_service` directly.
- Legacy router patch paths such as
  `app.routers.prompt_templates.prompt_template_service.validate_rewrite_request`
  have either been removed or are backed by direct-domain tests.
- Direct domain prompt template service coverage proves `PromptTemplateService`,
  `prompt_template_service`, and `PROMPT_TEMPLATE_REWRITE_MAX_CONTENT_BYTES`
  behavior without legacy imports.
```

- [ ] **Step 4: Update same-day design and plan docs**

The prompt management design must state:

```markdown
Prompt template CRUD, revision tracking, device payloads, rewrite validation,
rewrite output validation, and rewrite prompt construction now live in
`app.domains.prompt_management.prompt_template_service`;
`app.services.prompt_template_service` remains as a temporary compatibility
facade.
```

The prompt management plan must state:

```markdown
Prompt template service logic now lives in
`app.domains.prompt_management.prompt_template_service`; keep
`app.services.prompt_template_service` as a compatibility facade until
direct-domain coverage replaces legacy imports.
```

### Task 4: Verification And Commit

**Files:**
- Test: `server/tests/test_prompt_template_service_domain_facade.py`
- Test: `server/tests/test_prompt_template_service.py`
- Test: `server/tests/test_prompt_templates_rewrite.py`
- Test: `server/tests/test_prompt_management_auth_parity.py`
- Test: `server/tests/test_prompt_management_domain_boundary.py`
- Test: `server/tests/test_prompt_management_router_facade.py`
- Test: `server/tests/test_device_operations_polling_reporting.py`
- Test: `server/tests/test_device_operations_uploads.py`

- [ ] **Step 1: Run the focused facade test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_prompt_template_service_domain_facade.py -q
```

Expected: PASS.

- [ ] **Step 2: Run prompt template service tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_prompt_template_service.py -q
```

Expected: PASS.

- [ ] **Step 3: Run prompt rewrite and route facade tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_prompt_templates_rewrite.py server/tests/test_prompt_management_auth_parity.py server/tests/test_prompt_management_domain_boundary.py server/tests/test_prompt_management_router_facade.py -q
```

Expected: PASS.

- [ ] **Step 4: Run device prompt-template route coverage**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_polling_reporting.py server/tests/test_device_operations_uploads.py -q
```

Expected: PASS.

- [ ] **Step 5: Check placeholders and import inventory**

Run:

```powershell
$patterns = @("T" + "BD", "TO" + "DO", "implement" + " later", "fill in" + " details", "Similar to" + " Task")
$files = @(
  "docs/superpowers/specs/2026-06-20-prompt-template-service-domain-design.md",
  "docs/superpowers/plans/2026-06-20-prompt-template-service-domain-plan.md",
  "server/tests/test_prompt_template_service_domain_facade.py",
  "server/app/domains/prompt_management/prompt_template_service.py",
  "server/app/services/prompt_template_service.py",
  "server/app/domains/prompt_management/prompt_templates_router.py",
  "server/app/domains/prompt_management/README.md"
)
foreach ($pattern in $patterns) { rg -n --fixed-strings $pattern $files }
rg -n "app\.services\.prompt_template_service|app\.domains\.prompt_management\.prompt_template_service" server/app server/tests docs/superpowers -g "*.py" -g "*.md"
```

Expected: no placeholder hits. Import inventory shows direct domain import for
prompt management router, and legacy imports only for compatibility tests,
device operations, historical docs, or domains that have not moved yet.

- [ ] **Step 6: Commit only this migration**

Use an isolated Git index if the real worktree contains unrelated WIP.

Commit message:

```text
refactor: move prompt template service into prompt domain
```

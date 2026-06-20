# Model Schema Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move AI model schema helper functions into the model configuration domain while preserving legacy imports.

**Architecture:** `app.domains.model_configuration.model_schema` becomes the implementation owner. `app.services.model_schema` becomes a `sys.modules` alias facade. `ai_models_router.py` imports the domain helper directly and raw schema data remains in `app.data.model_schema_data`.

**Tech Stack:** Python, FastAPI route tests, pytest, Python module aliasing via `sys.modules`.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_model_configuration_model_schema_facade.py`
- Read: `server/app/services/model_schema.py`
- Read: `server/app/domains/model_configuration/ai_models_router.py`
- Read: `server/app/domains/model_configuration/README.md`

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-model-schema-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-model-schema-domain-plan.md"
DOMAIN_SCHEMA_PATH = REPO_ROOT / "server/app/domains/model_configuration/model_schema.py"
LEGACY_SCHEMA_PATH = REPO_ROOT / "server/app/services/model_schema.py"
ROUTER_PATH = REPO_ROOT / "server/app/domains/model_configuration/ai_models_router.py"
README_PATH = REPO_ROOT / "server/app/domains/model_configuration/README.md"


def test_model_schema_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.model_configuration.model_schema",
        "app.services.model_schema",
        "get_schema_payload",
    ]:
        assert term in spec
        assert term in plan
```

- [x] **Step 2: Complete the boundary test**

```python
def test_model_schema_domain_file_exists():
    assert DOMAIN_SCHEMA_PATH.exists()


def test_legacy_model_schema_is_thin_facade():
    text = LEGACY_SCHEMA_PATH.read_text(encoding="utf-8")
    assert "app.domains.model_configuration" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def get_schema_payload" not in text
    assert "def get_provider_preset" not in text
    assert _line_count(LEGACY_SCHEMA_PATH) <= 12


def test_legacy_model_schema_module_is_domain_module():
    legacy = importlib.import_module("app.services.model_schema")
    domain = importlib.import_module("app.domains.model_configuration.model_schema")
    assert legacy is domain
    assert legacy.get_schema_payload is domain.get_schema_payload
    assert legacy.get_provider_preset is domain.get_provider_preset
    assert legacy.get_scene_by_key is domain.get_scene_by_key
    assert legacy.get_providers_for_scene is domain.get_providers_for_scene


def test_services_parent_package_model_schema_attribute_is_domain_module():
    from app.services import model_schema as parent_import

    domain = importlib.import_module("app.domains.model_configuration.model_schema")
    assert parent_import is domain


def test_ai_models_router_imports_domain_model_schema_only():
    text = ROUTER_PATH.read_text(encoding="utf-8")
    assert "app.domains.model_configuration.model_schema" in text
    assert "app.services.model_schema" not in text


def test_model_configuration_docs_register_model_schema_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.model_configuration.model_schema",
        "app.services.model_schema",
        "get_schema_payload",
        "raw schema data stays in `app.data.model_schema_data`",
    ]:
        assert term in readme


def test_model_schema_provider_fallback_stays_legacy_compatible():
    legacy = importlib.import_module("app.services.model_schema")
    preset = legacy.get_provider_preset("unknown_provider_xyz")
    assert preset["label"] == "unknown_provider_xyz"
    assert preset["test_strategy"] == "health_check"


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
```

- [x] **Step 3: Run the red test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_model_configuration_model_schema_facade.py -q
```

Expected: FAIL because the domain module, facade, and router import are not in place.

### Task 2: Domain Migration

**Files:**
- Create: `server/app/domains/model_configuration/model_schema.py`
- Modify: `server/app/services/model_schema.py`
- Modify: `server/app/domains/model_configuration/ai_models_router.py`

- [x] **Step 1: Move implementation**

Move the current service body into:

```text
server/app/domains/model_configuration/model_schema.py
```

Use this module docstring:

```python
"""Model schema helpers for model configuration."""
```

- [x] **Step 2: Replace legacy module with facade**

```python
"""Compatibility facade for model configuration schema helpers."""

import sys

from app.domains.model_configuration import model_schema as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [x] **Step 3: Update router import**

Replace `from app.services.model_schema import get_schema_payload, get_provider_preset` with:

```python
from app.domains.model_configuration.model_schema import get_schema_payload, get_provider_preset
```

### Task 3: Documentation

**Files:**
- Modify: `server/app/domains/model_configuration/README.md`

- [x] **Step 1: Register ownership**

```markdown
- `model_schema.py` owns `get_schema_payload`, `get_provider_preset`, scene lookups, and provider lists; raw schema data stays in `app.data.model_schema_data`.
```

- [x] **Step 2: Register facade**

```markdown
| `app.services.model_schema` | `app.domains.model_configuration.model_schema` | Keep while legacy tests or callers import schema helpers from `app.services`; remove only after import inventory shows no production legacy imports. |
```

### Task 4: Verification

- [x] **Step 1: Run boundary test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_model_configuration_model_schema_facade.py -q
```

Expected: PASS.

- [x] **Step 2: Run model schema endpoint tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_model_schema.py -q
```

Expected: PASS.

- [x] **Step 3: Verify production legacy import inventory**

```powershell
rg -n "app\.services\.model_schema" server/app -g "*.py"
```

Expected: no production imports.

- [x] **Step 4: Commit**

```powershell
git add -f docs/superpowers/specs/2026-06-20-model-schema-domain-design.md docs/superpowers/plans/2026-06-20-model-schema-domain-plan.md server/tests/test_model_configuration_model_schema_facade.py server/app/domains/model_configuration/model_schema.py server/app/services/model_schema.py server/app/domains/model_configuration/ai_models_router.py server/app/domains/model_configuration/README.md
git commit -m "refactor: move model schema into model configuration"
```

# Model Registry Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move scene-based AI model registry resolution into the model configuration domain while preserving legacy imports.

**Architecture:** `app.domains.model_configuration.model_registry` becomes the implementation owner. `app.services.model_registry` becomes a `sys.modules` alias facade. `quality_audit.audit_router` imports the domain registry directly; `video_production_service` keeps the legacy path as an approved WIP compatibility import.

**Tech Stack:** Python, SQLAlchemy `Session`, pytest, Python module aliasing via `sys.modules`.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_model_configuration_model_registry_facade.py`
- Read: `server/app/services/model_registry.py`
- Read: `server/app/domains/quality_audit/audit_router.py`
- Read: `server/app/services/video_production_service.py`
- Read: `server/app/domains/model_configuration/README.md`

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-model-registry-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-model-registry-domain-plan.md"
DOMAIN_REGISTRY_PATH = REPO_ROOT / "server/app/domains/model_configuration/model_registry.py"
LEGACY_REGISTRY_PATH = REPO_ROOT / "server/app/services/model_registry.py"
AUDIT_ROUTER_PATH = REPO_ROOT / "server/app/domains/quality_audit/audit_router.py"
VIDEO_SERVICE_PATH = REPO_ROOT / "server/app/services/video_production_service.py"
README_PATH = REPO_ROOT / "server/app/domains/model_configuration/README.md"


def test_model_registry_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.model_configuration.model_registry",
        "app.services.model_registry",
        "get_model_for_scene",
    ]:
        assert term in spec
        assert term in plan
```

- [x] **Step 2: Complete the boundary test**

```python
def test_model_registry_domain_file_exists():
    assert DOMAIN_REGISTRY_PATH.exists()


def test_legacy_model_registry_is_thin_facade():
    text = LEGACY_REGISTRY_PATH.read_text(encoding="utf-8")
    assert "app.domains.model_configuration" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def get_model_for_scene" not in text
    assert "class ModelResolutionError" not in text
    assert _line_count(LEGACY_REGISTRY_PATH) <= 12


def test_legacy_model_registry_module_is_domain_module():
    legacy = importlib.import_module("app.services.model_registry")
    domain = importlib.import_module("app.domains.model_configuration.model_registry")
    assert legacy is domain
    assert legacy.ModelResolutionError is domain.ModelResolutionError
    assert legacy.get_model_for_scene is domain.get_model_for_scene
    assert legacy._get_scene_label is domain._get_scene_label


def test_services_parent_package_model_registry_attribute_is_domain_module():
    from app.services import model_registry as parent_import

    domain = importlib.import_module("app.domains.model_configuration.model_registry")
    assert parent_import is domain


def test_quality_audit_imports_domain_model_registry_only():
    text = AUDIT_ROUTER_PATH.read_text(encoding="utf-8")
    assert "app.domains.model_configuration.model_registry" in text
    assert "app.services.model_registry" not in text


def test_video_production_stays_legacy_compatible_for_wip_slice():
    text = VIDEO_SERVICE_PATH.read_text(encoding="utf-8")
    assert "app.services.model_registry" in text
    assert "app.domains.model_configuration.model_registry" not in text


def test_model_configuration_docs_register_model_registry_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.model_configuration.model_registry",
        "app.services.model_registry",
        "get_model_for_scene",
        "approved video production compatibility import",
    ]:
        assert term in readme


def test_model_registry_error_identity_stays_legacy_compatible():
    legacy = importlib.import_module("app.services.model_registry")
    err = legacy.ModelResolutionError("quality_audit", "repair", status_code=409)
    assert err.scene_key == "quality_audit"
    assert err.repair_action == "repair"
    assert err.status_code == 409


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
```

- [x] **Step 3: Run the red test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_model_configuration_model_registry_facade.py -q
```

Expected: FAIL because the domain file, facade, and quality audit domain import are not in place.

### Task 2: Domain Migration

**Files:**
- Create: `server/app/domains/model_configuration/model_registry.py`
- Modify: `server/app/services/model_registry.py`
- Modify: `server/app/domains/quality_audit/audit_router.py`

- [x] **Step 1: Move implementation**

Move the current service body into:

```text
server/app/domains/model_configuration/model_registry.py
```

Use this module docstring:

```python
"""Scene-based model registry for model configuration."""
```

- [x] **Step 2: Replace legacy module with facade**

```python
"""Compatibility facade for model configuration registry."""

import sys

from app.domains.model_configuration import model_registry as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [x] **Step 3: Update quality audit import**

Replace `from app.services.model_registry import get_model_for_scene, ModelResolutionError` with:

```python
from app.domains.model_configuration.model_registry import get_model_for_scene, ModelResolutionError
```

### Task 3: Documentation

**Files:**
- Modify: `server/app/domains/model_configuration/README.md`

- [x] **Step 1: Register ownership**

```markdown
- `model_registry.py` owns `ModelResolutionError`, `get_model_for_scene`, scene-based AIModel selection, decrypted runtime credentials, and repair messages.
```

- [x] **Step 2: Register facade**

```markdown
| `app.services.model_registry` | `app.domains.model_configuration.model_registry` | Keep while `video_production_service` has an approved video production compatibility import; remove only after import inventory shows no production legacy imports. |
```

### Task 4: Verification

- [x] **Step 1: Run boundary test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_model_configuration_model_registry_facade.py -q
```

Expected: PASS.

- [x] **Step 2: Run model registry tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_model_registry.py -q
```

Expected: PASS.

- [x] **Step 3: Verify production legacy import inventory**

```powershell
rg -n "app\.services\.model_registry" server/app -g "*.py"
```

Expected: only the approved `server/app/services/video_production_service.py` compatibility import.

- [x] **Step 4: Commit**

```powershell
git add -f docs/superpowers/specs/2026-06-20-model-registry-domain-design.md docs/superpowers/plans/2026-06-20-model-registry-domain-plan.md server/tests/test_model_configuration_model_registry_facade.py server/app/domains/model_configuration/model_registry.py server/app/services/model_registry.py server/app/domains/quality_audit/audit_router.py server/app/domains/model_configuration/README.md
git commit -m "refactor: move model registry into model configuration"
```

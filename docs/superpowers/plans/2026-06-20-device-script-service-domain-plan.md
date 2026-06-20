# Device Script Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move device script package helpers into the device operations domain while preserving legacy imports.

**Architecture:** `app.domains.device_operations.script_service` becomes the implementation owner. `app.services.script_service` becomes a `sys.modules` alias facade. `device_operations.script_assets` imports the domain helper directly and script zip storage remains under `SERVER_DIR / "scripts"`.

**Tech Stack:** Python, pathlib, FastAPI route tests, pytest, Python module aliasing via `sys.modules`.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_device_operations_script_service_facade.py`
- Read: `server/app/services/script_service.py`
- Read: `server/app/domains/device_operations/script_assets.py`
- Read: `server/app/domains/device_operations/README.md`

- [x] **Step 1: Write the failing test**

```python
import importlib
import io
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-device-script-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-device-script-service-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/device_operations/script_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/script_service.py"
SCRIPT_ASSETS_PATH = REPO_ROOT / "server/app/domains/device_operations/script_assets.py"
README_PATH = REPO_ROOT / "server/app/domains/device_operations/README.md"


def test_script_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.device_operations.script_service",
        "app.services.script_service",
        "ScriptService",
    ]:
        assert term in spec
        assert term in plan
```

- [x] **Step 2: Complete the boundary test**

```python
def test_script_service_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_script_service_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")
    assert "app.domains.device_operations" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "class ScriptService" not in text
    assert "script_service = ScriptService()" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 12


def test_legacy_script_service_module_is_domain_module():
    legacy = importlib.import_module("app.services.script_service")
    domain = importlib.import_module("app.domains.device_operations.script_service")
    assert legacy is domain
    assert legacy.ScriptService is domain.ScriptService
    assert legacy.script_service is domain.script_service


def test_services_parent_package_script_service_attribute_is_domain_module():
    from app.services import script_service as parent_import

    domain = importlib.import_module("app.domains.device_operations.script_service")
    assert parent_import is domain


def test_script_assets_import_domain_script_service_only():
    text = SCRIPT_ASSETS_PATH.read_text(encoding="utf-8")
    assert "app.domains.device_operations.script_service" in text
    assert "app.services.script_service" not in text


def test_device_operations_docs_register_script_service_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.device_operations.script_service",
        "app.services.script_service",
        "ScriptService",
        "SERVER_DIR / `scripts`",
    ]:
        assert term in readme


def test_script_service_upload_download_behavior_stays_legacy_compatible(tmp_path):
    legacy = importlib.import_module("app.services.script_service")
    service = legacy.ScriptService(tmp_path / "scripts", tmp_path / "scripts" / "version.txt")
    assert service.get_version() == "0.0.0"
    assert service.download_script() is None
    version = service.upload_script(io.BytesIO(b"PK\x03\x04zip"))
    assert version == "0.0.1"
    assert service.download_script() == b"PK\x03\x04zip"


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
```

- [x] **Step 3: Run the red test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_script_service_facade.py -q
```

Expected: FAIL because the domain file, facade, and direct script asset imports are not in place.

### Task 2: Domain Migration

**Files:**
- Create: `server/app/domains/device_operations/script_service.py`
- Modify: `server/app/services/script_service.py`
- Modify: `server/app/domains/device_operations/script_assets.py`

- [x] **Step 1: Move implementation**

Move the current service body into:

```text
server/app/domains/device_operations/script_service.py
```

Use this module docstring:

```python
"""Device script package service for device operations."""
```

- [x] **Step 2: Replace legacy module with facade**

```python
"""Compatibility facade for device script package service."""

import sys

from app.domains.device_operations import script_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [x] **Step 3: Update script asset imports**

Replace `from app.services.script_service import script_service` with:

```python
from app.domains.device_operations.script_service import script_service
```

### Task 3: Documentation

**Files:**
- Modify: `server/app/domains/device_operations/README.md`

- [x] **Step 1: Register ownership**

```markdown
- `app.domains.device_operations.script_service` owns `ScriptService`, `script_service`, script zip upload/download, and version storage under SERVER_DIR / `scripts`.
```

- [x] **Step 2: Register facade**

```markdown
| `app.services.script_service` | `app.domains.device_operations.script_service` | Script service domain slice | Remove only after import inventory shows no production imports of `app.services.script_service` and legacy-path tests are migrated or retired. |
```

### Task 4: Verification

- [x] **Step 1: Run boundary test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_script_service_facade.py -q
```

Expected: PASS.

- [x] **Step 2: Run script service tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_script_service.py server/tests/test_device_operations_uploads.py -q
```

Expected: PASS.

- [x] **Step 3: Verify production legacy import inventory**

```powershell
rg -n "app\.services\.script_service" server/app -g "*.py"
```

Expected: no production imports.

- [x] **Step 4: Commit**

```powershell
git add -f docs/superpowers/specs/2026-06-20-device-script-service-domain-design.md docs/superpowers/plans/2026-06-20-device-script-service-domain-plan.md server/tests/test_device_operations_script_service_facade.py server/app/domains/device_operations/script_service.py server/app/services/script_service.py server/app/domains/device_operations/script_assets.py server/app/domains/device_operations/README.md
git commit -m "refactor: move script service into device operations"
```

# Device Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move device registration and heartbeat state into device operations while preserving legacy imports.

**Architecture:** `app.domains.device_operations.device_service` becomes the implementation owner. `app.services.device_service` becomes a `sys.modules` alias facade. Device operation modules import the domain service directly.

**Tech Stack:** Python, SQLAlchemy `Session`, pytest, Python module aliasing via `sys.modules`.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_device_service_domain_facade.py`
- Read: `server/app/services/device_service.py`
- Read: `server/app/domains/device_operations/device_router.py`
- Read: `server/app/domains/device_operations/polling.py`
- Read: `server/app/domains/device_operations/reporting.py`
- Read: `server/app/domains/device_operations/status_ws.py`
- Read: `server/app/domains/device_operations/README.md`

- [ ] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-device-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-device-service-domain-plan.md"
DOMAIN_SERVICE_PATH = REPO_ROOT / "server/app/domains/device_operations/device_service.py"
LEGACY_SERVICE_PATH = REPO_ROOT / "server/app/services/device_service.py"
README_PATH = REPO_ROOT / "server/app/domains/device_operations/README.md"
DEVICE_MODULES = [
    REPO_ROOT / "server/app/domains/device_operations/device_router.py",
    REPO_ROOT / "server/app/domains/device_operations/polling.py",
    REPO_ROOT / "server/app/domains/device_operations/reporting.py",
    REPO_ROOT / "server/app/domains/device_operations/status_ws.py",
]


def test_device_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.device_operations.device_service",
        "app.services.device_service",
        "DeviceService",
    ]:
        assert term in spec
        assert term in plan
```

- [ ] **Step 2: Complete the test file**

```python
def test_device_service_domain_file_exists():
    assert DOMAIN_SERVICE_PATH.exists()


def test_legacy_device_service_is_thin_facade():
    text = LEGACY_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.device_operations" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "class DeviceService" not in text
    assert "device_service = DeviceService()" not in text
    assert _line_count(LEGACY_SERVICE_PATH) <= 20


def test_legacy_device_service_module_is_domain_module():
    try:
        legacy = importlib.import_module("app.services.device_service")
        domain = importlib.import_module("app.domains.device_operations.device_service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"device service domain import failed: {exc}")

    assert legacy is domain
    assert legacy.DeviceService is domain.DeviceService
    assert legacy.device_service is domain.device_service


def test_services_parent_package_device_service_attribute_is_domain_module():
    from app.services import device_service as parent_import

    domain = importlib.import_module("app.domains.device_operations.device_service")

    assert parent_import is domain
    assert parent_import.device_service is domain.device_service


def test_device_operations_modules_import_domain_device_service_only():
    for path in DEVICE_MODULES:
        text = path.read_text(encoding="utf-8")
        assert "app.domains.device_operations.device_service" in text
        assert "app.services.device_service" not in text


def test_device_operations_docs_register_device_service_facade():
    readme = README_PATH.read_text(encoding="utf-8")

    for term in [
        "app.domains.device_operations.device_service",
        "app.services.device_service",
        "DeviceService",
        'rg -n "app\\.services\\.device_service" server/app -g "*.py"',
    ]:
        assert term in readme


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
```

- [ ] **Step 3: Run the red test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_service_domain_facade.py -q
```

Expected: FAIL because the domain file, facade, direct domain imports, and README entries do not exist yet.

### Task 2: Domain Migration

**Files:**
- Create: `server/app/domains/device_operations/device_service.py`
- Modify: `server/app/services/device_service.py`
- Modify: `server/app/domains/device_operations/device_router.py`
- Modify: `server/app/domains/device_operations/polling.py`
- Modify: `server/app/domains/device_operations/reporting.py`
- Modify: `server/app/domains/device_operations/status_ws.py`

- [ ] **Step 1: Move implementation**

Move the current service body into:

```text
server/app/domains/device_operations/device_service.py
```

Use this module docstring:

```python
"""Device registration, heartbeat, and status management for device operations."""
```

- [ ] **Step 2: Replace legacy module with facade**

```python
"""Compatibility facade for device operation services."""

import sys

from app.domains.device_operations import device_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [ ] **Step 3: Update device operation imports**

Replace `app.services.device_service` imports in `device_router.py`,
`polling.py`, `reporting.py`, and `status_ws.py` with:

```python
from app.domains.device_operations.device_service import device_service
```

### Task 3: Documentation Update

**Files:**
- Modify: `server/app/domains/device_operations/README.md`

- [ ] **Step 1: Add ownership rule**

```markdown
- `app.domains.device_operations.device_service` owns `DeviceService` registration, heartbeat, status lookup, and offline marking.
```

- [ ] **Step 2: Add facade register row**

```markdown
| `app.services.device_service` | `app.domains.device_operations.device_service` | Device service domain slice | Remove only after `rg -n "app\.services\.device_service" server/app -g "*.py"` returns no production imports and remaining legacy-path tests are migrated or retired. |
```

### Task 4: Verification

- [ ] **Step 1: Run boundary test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_service_domain_facade.py -q
```

Expected: PASS.

- [ ] **Step 2: Run device behavior tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_service.py server/tests/test_device_api.py server/tests/test_device_endpoints.py server/tests/test_devices_api.py -q
```

Expected: PASS.

- [ ] **Step 3: Run device operations tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_auth_parity.py server/tests/test_device_operations_domain_boundary.py server/tests/test_device_operations_pairing.py server/tests/test_device_operations_polling_reporting.py server/tests/test_device_operations_status_lifecycle.py server/tests/test_device_operations_uploads.py -q
```

Expected: PASS.

- [ ] **Step 4: Verify cleanup inventory**

```powershell
rg -n "app\.services\.device_service" server/app -g "*.py"
```

Expected: no production imports.

- [ ] **Step 5: Commit**

```powershell
git add -f docs/superpowers/specs/2026-06-20-device-service-domain-design.md docs/superpowers/plans/2026-06-20-device-service-domain-plan.md server/tests/test_device_service_domain_facade.py server/app/domains/device_operations/device_service.py server/app/services/device_service.py server/app/domains/device_operations/device_router.py server/app/domains/device_operations/polling.py server/app/domains/device_operations/reporting.py server/app/domains/device_operations/status_ws.py server/app/domains/device_operations/README.md
git commit -m "refactor: move device service into device operations"
```

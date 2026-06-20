# Pixelle Client Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the Pixelle HTTP client into the Pixelle integration domain while preserving legacy imports.

**Architecture:** `app.domains.pixelle_integration.pixelle_client` becomes the implementation owner. `app.services.pixelle_client` becomes a `sys.modules` alias facade. Clean domain callers import the domain client directly, while app shutdown and not-yet-moved service modules keep legacy imports.

**Tech Stack:** Python, httpx, SQLAlchemy ORM session lookup, pytest, Python module aliasing via `sys.modules`.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_pixelle_integration_client_facade.py`
- Read: `server/app/services/pixelle_client.py`
- Read: `server/app/domains/image_generation/image_creation_router.py`
- Read: `server/app/domains/script_pipeline/pipeline_router.py`
- Read: `server/app/domains/pixelle_integration/README.md`

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-pixelle-client-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-pixelle-client-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/pixelle_integration/pixelle_client.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/pixelle_client.py"
IMAGE_ROUTER_PATH = REPO_ROOT / "server/app/domains/image_generation/image_creation_router.py"
PIPELINE_ROUTER_PATH = REPO_ROOT / "server/app/domains/script_pipeline/pipeline_router.py"
README_PATH = REPO_ROOT / "server/app/domains/pixelle_integration/README.md"


def test_pixelle_client_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.pixelle_integration.pixelle_client",
        "app.services.pixelle_client",
        "_pixelle_request",
        "close_client",
    ]:
        assert term in spec
        assert term in plan
```

- [x] **Step 2: Complete the boundary test**

```python
def test_pixelle_client_domain_file_exists():
    assert DOMAIN_PATH.exists()


def test_legacy_pixelle_client_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.pixelle_integration" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "async def _pixelle_request" not in text
    assert "async def close_client" not in text
    assert _line_count(LEGACY_PATH) <= 12


def test_legacy_pixelle_client_module_is_domain_module():
    legacy = importlib.import_module("app.services.pixelle_client")
    domain = importlib.import_module("app.domains.pixelle_integration.pixelle_client")
    assert legacy is domain
    assert legacy._pixelle_request is domain._pixelle_request
    assert legacy._get_base_url is domain._get_base_url
    assert legacy.close_client is domain.close_client


def test_services_parent_package_pixelle_client_attribute_is_domain_module():
    from app.services import pixelle_client as parent_import

    domain = importlib.import_module("app.domains.pixelle_integration.pixelle_client")
    assert parent_import is domain


def test_clean_domain_callers_import_domain_pixelle_client():
    for path in [IMAGE_ROUTER_PATH, PIPELINE_ROUTER_PATH]:
        text = path.read_text(encoding="utf-8")
        assert "app.domains.pixelle_integration.pixelle_client" in text
        assert "app.services.pixelle_client" not in text


def test_pixelle_integration_docs_register_pixelle_client_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.pixelle_integration.pixelle_client",
        "app.services.pixelle_client",
        "_pixelle_request",
        "approved compatibility imports",
    ]:
        assert term in readme


@pytest.mark.asyncio
async def test_pixelle_request_stays_legacy_compatible():
    legacy = importlib.import_module("app.services.pixelle_client")
    legacy._base_url = ""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value={"ok": True})
    resp.status_code = 200
    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=resp)

    with patch("app.services.pixelle_client._get_client", return_value=mock_client):
        result = await legacy._pixelle_request("GET", "/health")

    assert result == {"ok": True}
    assert mock_client.request.call_count == 1
    legacy._base_url = ""


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
```

- [x] **Step 3: Run the red test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_pixelle_integration_client_facade.py -q
```

Expected: FAIL because the domain file, facade, direct domain imports, and README registration are not in place.

### Task 2: Domain Migration

**Files:**
- Create: `server/app/domains/pixelle_integration/pixelle_client.py`
- Modify: `server/app/services/pixelle_client.py`
- Modify: `server/app/domains/image_generation/image_creation_router.py`
- Modify: `server/app/domains/script_pipeline/pipeline_router.py`

- [x] **Step 1: Move implementation**

Move the current service body into:

```text
server/app/domains/pixelle_integration/pixelle_client.py
```

- [x] **Step 2: Replace legacy module with facade**

```python
"""Compatibility facade for Pixelle HTTP client helpers."""

import sys

from app.domains.pixelle_integration import pixelle_client as _domain_module

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [x] **Step 3: Update clean domain imports**

Replace `from app.services.pixelle_client import ...` with:

```python
from app.domains.pixelle_integration.pixelle_client import ...
```

### Task 3: Documentation

**Files:**
- Modify: `server/app/domains/pixelle_integration/README.md`

- [x] **Step 1: Register ownership**

```markdown
- `pixelle_client.py` owns `DEFAULT_BASE_URL`, Pixelle base URL/API key
  lookup, lazy `httpx.AsyncClient`, `_pixelle_request`, retries, JSON parsing,
  and `close_client`.
```

- [x] **Step 2: Register facade**

```markdown
| `app.services.pixelle_client` | `app.domains.pixelle_integration.pixelle_client` | Keep while `app.main` shutdown and not-yet-moved service modules have approved compatibility imports; remove only after import inventory shows no production legacy imports. |
```

### Task 4: Verification

- [x] **Step 1: Run boundary test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_pixelle_integration_client_facade.py -q
```

Expected: PASS.

- [x] **Step 2: Run existing Pixelle client tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_pixelle_client.py -q
```

Expected: PASS.

- [x] **Step 3: Run app import smoke**

```powershell
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
```

Expected: prints the app title.

- [x] **Step 4: Verify production legacy import inventory**

```powershell
rg -n "app\.services\.pixelle_client|from app\.services import pixelle_client" server/app -g "*.py"
```

Expected: only `app.main` shutdown and not-yet-moved service modules keep approved compatibility imports.

- [x] **Step 5: Commit**

```powershell
git add -f docs/superpowers/specs/2026-06-20-pixelle-client-domain-design.md docs/superpowers/plans/2026-06-20-pixelle-client-domain-plan.md server/tests/test_pixelle_integration_client_facade.py server/app/domains/pixelle_integration/pixelle_client.py server/app/services/pixelle_client.py server/app/domains/pixelle_integration/README.md server/app/domains/image_generation/image_creation_router.py server/app/domains/script_pipeline/pipeline_router.py
git commit -m "refactor: move pixelle client into pixelle integration"
```

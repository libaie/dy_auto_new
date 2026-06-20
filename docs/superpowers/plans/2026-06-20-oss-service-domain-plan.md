# OSS Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move OSS/CDN upload behavior out of `app.services` and into `app.domains.system_operations` while preserving the legacy import path.

**Architecture:** `app.domains.system_operations.oss_service` owns `upload_to_oss`. `app.services.oss_service` becomes a compatibility alias to the domain module so existing imports keep the same function object.

**Tech Stack:** FastAPI service package layout, Python async helper, pytest.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_system_operations_oss_service_facade.py`

- [ ] **Step 1: Write the failing test**

```python
import asyncio
import importlib
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-oss-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-oss-service-domain-plan.md"
README_PATH = REPO_ROOT / "server/app/domains/system_operations/README.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/system_operations/oss_service.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/oss_service.py"


def test_oss_service_spec_plan_and_readme_document_boundary():
    combined = SPEC_PATH.read_text(encoding="utf-8") + PLAN_PATH.read_text(encoding="utf-8")
    for expected in (
        "app.domains.system_operations.oss_service",
        "app.services.oss_service",
        "upload_to_oss",
    ):
        assert expected in combined

    readme = README_PATH.read_text(encoding="utf-8")
    assert "app.domains.system_operations.oss_service" in readme
    assert "app.services.oss_service" in readme
    assert "upload_to_oss" in readme


def test_oss_service_domain_file_owns_upload_helper():
    text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "async def upload_to_oss" in text
    assert "provider == \"local\"" in text


def test_legacy_oss_service_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.system_operations import oss_service" in text
    assert "sys.modules[_LEGACY_MODULE_NAME] = _domain_module" in text
    assert "async def upload_to_oss" not in text
    assert "boto3.client" not in text
    assert "oss2.Bucket" not in text


def test_legacy_oss_service_module_is_domain_module():
    for name in ("app.services.oss_service", "app.domains.system_operations.oss_service"):
        sys.modules.pop(name, None)

    legacy = importlib.import_module("app.services.oss_service")
    domain = importlib.import_module("app.domains.system_operations.oss_service")

    assert legacy is domain
    assert legacy.upload_to_oss is domain.upload_to_oss


def test_oss_service_local_provider_returns_file_url(tmp_path):
    local_file = tmp_path / "asset.png"
    local_file.write_bytes(b"asset")

    domain = importlib.import_module("app.domains.system_operations.oss_service")
    result = asyncio.run(domain.upload_to_oss(str(local_file), provider="local"))

    assert result == f"file://{local_file.resolve()}"


def test_oss_service_missing_file_raises_file_not_found(tmp_path):
    domain = importlib.import_module("app.domains.system_operations.oss_service")

    with pytest.raises(FileNotFoundError):
        asyncio.run(domain.upload_to_oss(str(tmp_path / "missing.png"), provider="local"))
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_system_operations_oss_service_facade.py -q
```

Expected: FAIL because `server/app/domains/system_operations/oss_service.py` does not exist and the legacy file still owns `upload_to_oss`.

### Task 2: Domain Move

**Files:**
- Create: `server/app/domains/system_operations/oss_service.py`
- Modify: `server/app/services/oss_service.py`
- Modify: `server/app/domains/system_operations/README.md`

- [ ] **Step 1: Move the implementation**

Copy the current `server/app/services/oss_service.py` body to
`server/app/domains/system_operations/oss_service.py` without changing behavior.

- [ ] **Step 2: Replace the legacy file with a facade**

```python
"""Compatibility facade for system operations OSS upload helpers."""

import sys

from app.domains.system_operations import oss_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
```

- [ ] **Step 3: Update the system operations README**

Add `oss_service.py` to Current Modules and add this facade row:

```markdown
| `app.services.oss_service` | `app.domains.system_operations.oss_service` | Import inventory proves no production or test imports use the legacy service path. |
```

- [ ] **Step 4: Run focused verification**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_system_operations_oss_service_facade.py -q
Push-Location server; ..\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"; Pop-Location
git diff --check -- docs/superpowers/specs/2026-06-20-oss-service-domain-design.md docs/superpowers/plans/2026-06-20-oss-service-domain-plan.md server/tests/test_system_operations_oss_service_facade.py server/app/domains/system_operations/oss_service.py server/app/services/oss_service.py server/app/domains/system_operations/README.md
```

Expected: pytest passes, the app import prints the app title, and `git diff --check` exits 0.

- [ ] **Step 5: Commit target files only**

```powershell
git add -f docs/superpowers/specs/2026-06-20-oss-service-domain-design.md docs/superpowers/plans/2026-06-20-oss-service-domain-plan.md server/tests/test_system_operations_oss_service_facade.py server/app/domains/system_operations/oss_service.py server/app/services/oss_service.py server/app/domains/system_operations/README.md
git commit --only docs/superpowers/specs/2026-06-20-oss-service-domain-design.md docs/superpowers/plans/2026-06-20-oss-service-domain-plan.md server/tests/test_system_operations_oss_service_facade.py server/app/domains/system_operations/oss_service.py server/app/services/oss_service.py server/app/domains/system_operations/README.md -m "refactor: move oss upload helper into system operations"
```

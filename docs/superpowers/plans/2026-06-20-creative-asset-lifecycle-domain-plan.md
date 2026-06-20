# Creative Asset Lifecycle Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move creative asset lifecycle behavior into the Creative Library domain while preserving legacy imports.

**Architecture:** `app.domains.creative_library.asset_lifecycle_service` becomes the implementation owner. `app.services.asset_lifecycle_service` becomes a `sys.modules` alias facade. Creative Library routers import the domain path directly; AI video series legacy imports remain for a later slice.

**Tech Stack:** Python, SQLAlchemy ORM session usage, pytest, Python module aliasing via `sys.modules`.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_creative_library_asset_lifecycle_service_facade.py`
- Read: `server/app/services/asset_lifecycle_service.py`
- Read: `server/app/domains/creative_library/characters_router.py`
- Read: `server/app/domains/creative_library/scenes_router.py`
- Read: `server/app/domains/creative_library/README.md`

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-creative-asset-lifecycle-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-creative-asset-lifecycle-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/creative_library/asset_lifecycle_service.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/asset_lifecycle_service.py"
CHARACTERS_ROUTER_PATH = REPO_ROOT / "server/app/domains/creative_library/characters_router.py"
SCENES_ROUTER_PATH = REPO_ROOT / "server/app/domains/creative_library/scenes_router.py"
README_PATH = REPO_ROOT / "server/app/domains/creative_library/README.md"


def test_asset_lifecycle_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.creative_library.asset_lifecycle_service",
        "app.services.asset_lifecycle_service",
        "AssetLifecycleError",
        "archive_character_or_scene",
    ]:
        assert term in spec
        assert term in plan
```

- [x] **Step 2: Complete the boundary test**

```python
def test_asset_lifecycle_domain_file_exists():
    assert DOMAIN_PATH.exists()


def test_legacy_asset_lifecycle_service_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.creative_library" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def archive_character_or_scene" not in text
    assert "class AssetLifecycleError" not in text
    assert _line_count(LEGACY_PATH) <= 12


def test_legacy_asset_lifecycle_module_is_domain_module():
    legacy = importlib.import_module("app.services.asset_lifecycle_service")
    domain = importlib.import_module("app.domains.creative_library.asset_lifecycle_service")
    assert legacy is domain
    assert legacy.AssetLifecycleError is domain.AssetLifecycleError
    assert legacy.archive_character_or_scene is domain.archive_character_or_scene


def test_services_parent_package_asset_lifecycle_attribute_is_domain_module():
    from app.services import asset_lifecycle_service as parent_import

    domain = importlib.import_module("app.domains.creative_library.asset_lifecycle_service")
    assert parent_import is domain


def test_creative_library_routers_import_domain_asset_lifecycle_service():
    for path in [CHARACTERS_ROUTER_PATH, SCENES_ROUTER_PATH]:
        text = path.read_text(encoding="utf-8")
        assert "app.domains.creative_library.asset_lifecycle_service" in text
        assert "app.services.asset_lifecycle_service" not in text


def test_creative_library_docs_register_asset_lifecycle_service_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "asset_lifecycle_service.py",
        "AssetLifecycleError",
        "app.services.asset_lifecycle_service",
        "app.domains.creative_library.asset_lifecycle_service",
    ]:
        assert term in readme


def test_legacy_path_exports_same_error_class():
    from app.services.asset_lifecycle_service import AssetLifecycleError as legacy_error

    domain = importlib.import_module("app.domains.creative_library.asset_lifecycle_service")
    err = legacy_error("CODE", "Message", {"id": "1"})
    assert isinstance(err, domain.AssetLifecycleError)
    assert err.details == {"id": "1"}


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
```

- [x] **Step 3: Run the red test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_creative_library_asset_lifecycle_service_facade.py -q
```

Expected: FAIL because the domain file, facade, direct router imports, and README registration are not in place.

### Task 2: Domain Migration

**Files:**
- Create: `server/app/domains/creative_library/asset_lifecycle_service.py`
- Modify: `server/app/services/asset_lifecycle_service.py`
- Modify: `server/app/domains/creative_library/characters_router.py`
- Modify: `server/app/domains/creative_library/scenes_router.py`

- [x] **Step 1: Move implementation**

Copy the current service body into:

```text
server/app/domains/creative_library/asset_lifecycle_service.py
```

- [x] **Step 2: Replace legacy module with facade**

```python
"""Compatibility facade for creative library asset lifecycle services."""

import sys

from app.domains.creative_library import asset_lifecycle_service as _domain_module

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [x] **Step 3: Update creative router imports**

Replace:

```python
from app.services.asset_lifecycle_service import AssetLifecycleError, archive_character_or_scene
```

with:

```python
from app.domains.creative_library.asset_lifecycle_service import AssetLifecycleError, archive_character_or_scene
```

### Task 3: Documentation

**Files:**
- Modify: `server/app/domains/creative_library/README.md`

- [x] **Step 1: Register ownership**

```markdown
- `asset_lifecycle_service.py` owns `AssetLifecycleError`, series
  delete/archive decisions, character/scene unlinking, and character/scene
  archive-or-delete behavior.
```

- [x] **Step 2: Register facade**

```markdown
| `app.services.asset_lifecycle_service` | `app.domains.creative_library.asset_lifecycle_service` | Domain modules import the domain service path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
```

### Task 4: Verification

- [x] **Step 1: Run boundary test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_creative_library_asset_lifecycle_service_facade.py -q
```

Expected: PASS.

- [x] **Step 2: Run existing asset lifecycle tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_asset_lifecycle_service.py -q
```

Expected: PASS.

- [x] **Step 3: Run app import smoke**

```powershell
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
```

Expected: prints the app title.

- [x] **Step 4: Verify production legacy import inventory**

```powershell
rg -n "app\.services\.asset_lifecycle_service" server/app -g "*.py"
```

Expected: only not-yet-moved service or domain modules keep approved compatibility imports.

- [x] **Step 5: Commit**

```powershell
git add -f docs/superpowers/specs/2026-06-20-creative-asset-lifecycle-domain-design.md docs/superpowers/plans/2026-06-20-creative-asset-lifecycle-domain-plan.md server/tests/test_creative_library_asset_lifecycle_service_facade.py server/app/domains/creative_library/asset_lifecycle_service.py server/app/services/asset_lifecycle_service.py server/app/domains/creative_library/characters_router.py server/app/domains/creative_library/scenes_router.py server/app/domains/creative_library/README.md
git commit -m "refactor: move asset lifecycle into creative library"
```

# Creative Anchor Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move creative asset anchor management into the Creative Library domain while preserving legacy imports.

**Architecture:** `app.domains.creative_library.anchor_service` becomes the implementation owner. `app.services.anchor_service` becomes a `sys.modules` alias facade. Existing callers outside this domain keep legacy imports for this slice.

**Tech Stack:** Python, SQLAlchemy ORM session usage, pytest, Python module aliasing via `sys.modules`.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_creative_library_anchor_service_facade.py`
- Read: `server/app/services/anchor_service.py`
- Read: `server/app/domains/creative_library/reference_asset_service.py`
- Read: `server/app/domains/creative_library/README.md`

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-creative-anchor-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-creative-anchor-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/creative_library/anchor_service.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/anchor_service.py"
README_PATH = REPO_ROOT / "server/app/domains/creative_library/README.md"
REFERENCE_ASSET_PATH = REPO_ROOT / "server/app/domains/creative_library/reference_asset_service.py"


def test_anchor_service_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.creative_library.anchor_service",
        "app.services.anchor_service",
        "AssetAnchorManager",
        "reference_asset_service",
    ]:
        assert term in spec
        assert term in plan
```

- [x] **Step 2: Complete the boundary test**

```python
def test_anchor_service_domain_file_exists():
    assert DOMAIN_PATH.exists()


def test_legacy_anchor_service_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.creative_library" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "class AssetAnchorManager" not in text
    assert "def _resolve_seed" not in text
    assert _line_count(LEGACY_PATH) <= 12


def test_legacy_anchor_service_module_is_domain_module():
    legacy = importlib.import_module("app.services.anchor_service")
    domain = importlib.import_module("app.domains.creative_library.anchor_service")
    assert legacy is domain
    assert legacy.AssetAnchorManager is domain.AssetAnchorManager
    assert legacy._resolve_seed is domain._resolve_seed


def test_services_parent_package_anchor_service_attribute_is_domain_module():
    from app.services import anchor_service as parent_import

    domain = importlib.import_module("app.domains.creative_library.anchor_service")
    assert parent_import is domain


def test_domain_anchor_service_imports_domain_reference_asset_service():
    text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "app.domains.creative_library.reference_asset_service" in text
    assert "app.services.reference_asset_service" not in text


def test_same_domain_reference_asset_service_imports_domain_anchor_service():
    text = REFERENCE_ASSET_PATH.read_text(encoding="utf-8")
    assert "app.domains.creative_library.anchor_service" in text
    assert "app.services.anchor_service" not in text


def test_creative_library_docs_register_anchor_service_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "anchor_service.py",
        "AssetAnchorManager",
        "app.services.anchor_service",
        "app.domains.creative_library.anchor_service",
    ]:
        assert term in readme


def test_legacy_monkeypatch_is_visible_on_domain_module(monkeypatch):
    legacy = importlib.import_module("app.services.anchor_service")
    domain = importlib.import_module("app.domains.creative_library.anchor_service")

    def fake_resolve_seed(seed, existing_seed, fallback_key):
        return 123

    monkeypatch.setattr("app.services.anchor_service._resolve_seed", fake_resolve_seed)

    assert domain._resolve_seed(None, None, "x") == 123
    assert legacy._resolve_seed is domain._resolve_seed


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
```

- [x] **Step 3: Run the red test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_creative_library_anchor_service_facade.py -q
```

Expected: FAIL because the domain file, facade, direct same-domain import, and README registration are not in place.

### Task 2: Domain Migration

**Files:**
- Create: `server/app/domains/creative_library/anchor_service.py`
- Modify: `server/app/services/anchor_service.py`
- Modify: `server/app/domains/creative_library/reference_asset_service.py`

- [x] **Step 1: Move implementation**

Copy the current service body into:

```text
server/app/domains/creative_library/anchor_service.py
```

- [x] **Step 2: Update same-domain import**

In the domain module, replace:

```python
from app.services.reference_asset_service import (
```

with:

```python
from app.domains.creative_library.reference_asset_service import (
```

- [x] **Step 3: Replace legacy module with facade**

```python
"""Compatibility facade for creative library anchor services."""

import sys

from app.domains.creative_library import anchor_service as _domain_module

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [x] **Step 4: Update same-domain lazy imports**

In `server/app/domains/creative_library/reference_asset_service.py`, replace:

```python
from app.services.anchor_service import AssetAnchorManager
```

with:

```python
from app.domains.creative_library.anchor_service import AssetAnchorManager
```

### Task 3: Documentation

**Files:**
- Modify: `server/app/domains/creative_library/README.md`

- [x] **Step 1: Register ownership**

```markdown
- `anchor_service.py` owns `AssetAnchorManager`, character/scene anchor
  prompt construction, provider reference payload adaptation, and latest locked
  anchor lookup.
```

- [x] **Step 2: Register facade**

```markdown
| `app.services.anchor_service` | `app.domains.creative_library.anchor_service` | Domain modules import the domain service path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
```

### Task 4: Verification

- [x] **Step 1: Run boundary test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_creative_library_anchor_service_facade.py -q
```

Expected: PASS.

- [x] **Step 2: Run existing anchor service tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_anchor_service.py -q
```

Expected: PASS.

- [x] **Step 3: Run app import smoke**

```powershell
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
```

Expected: prints the app title.

- [x] **Step 4: Verify production legacy import inventory**

```powershell
rg -n "app\.services\.anchor_service" server/app -g "*.py"
```

Expected: only not-yet-moved utility or service modules keep approved compatibility imports.

- [x] **Step 5: Commit**

```powershell
git add -f docs/superpowers/specs/2026-06-20-creative-anchor-domain-design.md docs/superpowers/plans/2026-06-20-creative-anchor-domain-plan.md server/tests/test_creative_library_anchor_service_facade.py server/app/domains/creative_library/anchor_service.py server/app/services/anchor_service.py server/app/domains/creative_library/reference_asset_service.py server/app/domains/creative_library/README.md
git commit -m "refactor: move anchor service into creative library"
```

# Asset Lifecycle Domain Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Point `ai_video_series.router` at the creative-library asset lifecycle domain module.

**Architecture:** Asset lifecycle behavior already lives in `app.domains.creative_library.asset_lifecycle_service`. This change updates one cross-domain consumer and leaves the service facade intact.

**Tech Stack:** Python, pytest, existing `sys.modules` compatibility facade.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_asset_lifecycle_domain_import.py`
- Read: `server/app/domains/ai_video_series/router.py`

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-asset-lifecycle-domain-import-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-asset-lifecycle-domain-import-plan.md"
SERIES_ROUTER_PATH = REPO_ROOT / "server/app/domains/ai_video_series/router.py"


def test_asset_lifecycle_import_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.creative_library.asset_lifecycle_service",
        "app.services.asset_lifecycle_service",
        "ai_video_series.router",
    ]:
        assert term in spec
        assert term in plan
```

- [x] **Step 2: Complete the boundary test**

```python
def test_series_router_imports_asset_lifecycle_from_domain_path():
    text = SERIES_ROUTER_PATH.read_text(encoding="utf-8")
    assert "app.domains.creative_library.asset_lifecycle_service" in text
    assert "app.services.asset_lifecycle_service" not in text


def test_legacy_asset_lifecycle_facade_still_resolves_to_domain_module():
    legacy = importlib.import_module("app.services.asset_lifecycle_service")
    domain = importlib.import_module("app.domains.creative_library.asset_lifecycle_service")
    assert legacy is domain
    assert legacy.AssetLifecycleError is domain.AssetLifecycleError
    assert legacy.delete_or_archive_series is domain.delete_or_archive_series
```

- [x] **Step 3: Run the red test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_asset_lifecycle_domain_import.py -q
```

Expected: FAIL because `ai_video_series/router.py` still imports the legacy service facade.

### Task 2: Import Migration

**Files:**
- Modify: `server/app/domains/ai_video_series/router.py`

- [x] **Step 1: Replace legacy import**

```python
from app.domains.creative_library.asset_lifecycle_service import (
    AssetLifecycleError,
    delete_or_archive_series,
    unlink_character_from_series,
    unlink_scene_from_series,
)
```

- [x] **Step 2: Run verification**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_asset_lifecycle_domain_import.py server/tests/test_creative_library_asset_lifecycle_service_facade.py -q
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
rg -n "from app\.services\.asset_lifecycle_service" server/app/domains -g "*.py"
```

Expected: pytest passes, app import prints the title, and `rg` returns no domain matches.

- [x] **Step 3: Commit**

```powershell
git add -f docs/superpowers/specs/2026-06-20-asset-lifecycle-domain-import-design.md docs/superpowers/plans/2026-06-20-asset-lifecycle-domain-import-plan.md server/tests/test_asset_lifecycle_domain_import.py server/app/domains/ai_video_series/router.py
git commit -m "refactor: use asset lifecycle domain import"
```

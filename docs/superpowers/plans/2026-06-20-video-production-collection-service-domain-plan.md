# Video Production Collection Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move approved-episode collection creation into the video production domain while preserving the legacy service import path.

**Architecture:** `app.domains.video_production.production_collection_service` owns `create_collection_from_approved_episodes`. `app.services.production_collection_service` aliases that domain module for compatibility, and the video production router imports the domain helper directly.

**Tech Stack:** Python, SQLAlchemy ORM, FastAPI router, pytest.

---

### Task 1: Write The Boundary Test

**Files:**
- Create: `server/tests/test_video_production_collection_service_facade.py`

- [ ] **Step 1: Add this test file**

```python
import importlib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-video-production-collection-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-video-production-collection-service-domain-plan.md"
README_PATH = REPO_ROOT / "server/app/domains/video_production/README.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/video_production/production_collection_service.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/production_collection_service.py"
ROUTER_PATH = REPO_ROOT / "server/app/domains/video_production/video_production_router.py"


def test_collection_service_spec_plan_and_readme_document_boundary():
    combined = SPEC_PATH.read_text(encoding="utf-8") + PLAN_PATH.read_text(encoding="utf-8")
    for expected in (
        "app.domains.video_production.production_collection_service",
        "app.services.production_collection_service",
        "create_collection_from_approved_episodes",
    ):
        assert expected in combined

    readme = README_PATH.read_text(encoding="utf-8")
    assert "production_collection_service.py" in readme
    assert "app.domains.video_production.production_collection_service" in readme
    assert "app.services.production_collection_service" in readme


def test_collection_service_domain_file_owns_helper():
    text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "def create_collection_from_approved_episodes" in text
    assert "没有可打包剧集" in text


def test_legacy_collection_service_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.video_production import production_collection_service" in text
    assert "sys.modules[_LEGACY_MODULE_NAME] = _domain_module" in text
    assert "def create_collection_from_approved_episodes" not in text
    assert "db.query(Episode)" not in text


def test_legacy_collection_service_module_is_domain_module():
    for name in (
        "app.services.production_collection_service",
        "app.domains.video_production.production_collection_service",
    ):
        sys.modules.pop(name, None)

    legacy = importlib.import_module("app.services.production_collection_service")
    domain = importlib.import_module("app.domains.video_production.production_collection_service")

    assert legacy is domain
    assert legacy.create_collection_from_approved_episodes is domain.create_collection_from_approved_episodes


def test_video_production_router_imports_collection_service_from_domain():
    text = ROUTER_PATH.read_text(encoding="utf-8")
    assert "app.domains.video_production.production_collection_service" in text
    assert "app.services.production_collection_service" not in text
```

- [ ] **Step 2: Verify red**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_collection_service_facade.py -q
```

Expected: FAIL because the domain module and README registration do not exist and the legacy module still owns the helper body.

### Task 2: Move The Helper

**Files:**
- Create: `server/app/domains/video_production/production_collection_service.py`
- Modify: `server/app/services/production_collection_service.py`
- Modify: `server/app/domains/video_production/video_production_router.py`
- Modify: `server/app/domains/video_production/README.md`

- [ ] **Step 1: Copy current implementation to the domain module**

Copy the current `server/app/services/production_collection_service.py` content
to `server/app/domains/video_production/production_collection_service.py`.

- [ ] **Step 2: Replace the legacy service with this facade**

```python
"""Compatibility facade for video production collection helpers."""

import sys

from app.domains.video_production import production_collection_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
```

- [ ] **Step 3: Update the router import**

Change the collection route local import to:

```python
from app.domains.video_production.production_collection_service import create_collection_from_approved_episodes
```

- [ ] **Step 4: Update README ownership and facade register**

Add `production_collection_service.py` to Current Modules and this facade row:

```markdown
| `app.services.production_collection_service` | `app.domains.video_production.production_collection_service` | Domain router imports the domain helper directly, and legacy imports remain only in compatibility tests or older callers not yet migrated. |
```

- [ ] **Step 5: Verify green**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_collection_service_facade.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_collection_builder.py -q
git diff --check -- docs/superpowers/specs/2026-06-20-video-production-collection-service-domain-design.md docs/superpowers/plans/2026-06-20-video-production-collection-service-domain-plan.md server/tests/test_video_production_collection_service_facade.py server/app/domains/video_production/production_collection_service.py server/app/services/production_collection_service.py server/app/domains/video_production/video_production_router.py server/app/domains/video_production/README.md
```

Expected: both pytest commands pass and `git diff --check` exits 0.

- [ ] **Step 6: Commit target files only**

```powershell
git add -f docs/superpowers/specs/2026-06-20-video-production-collection-service-domain-design.md docs/superpowers/plans/2026-06-20-video-production-collection-service-domain-plan.md server/tests/test_video_production_collection_service_facade.py server/app/domains/video_production/production_collection_service.py server/app/services/production_collection_service.py server/app/domains/video_production/video_production_router.py server/app/domains/video_production/README.md
git commit --only docs/superpowers/specs/2026-06-20-video-production-collection-service-domain-design.md docs/superpowers/plans/2026-06-20-video-production-collection-service-domain-plan.md server/tests/test_video_production_collection_service_facade.py server/app/domains/video_production/production_collection_service.py server/app/services/production_collection_service.py server/app/domains/video_production/video_production_router.py server/app/domains/video_production/README.md -m "refactor: move collection builder into video production"
```

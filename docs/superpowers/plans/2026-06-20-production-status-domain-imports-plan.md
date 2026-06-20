# Production Status Domain Imports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Point domain modules at `app.domains.video_production.production_status` instead of the legacy service facade.

**Architecture:** The production status constants already live in the video production domain. This change keeps the service facade intact and only updates direct imports in domain-owned modules.

**Tech Stack:** Python, pytest, module compatibility through existing `sys.modules` facade.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_production_status_domain_imports.py`
- Read: `server/app/domains/ai_video_series/story_planning.py`
- Read: `server/app/domains/ai_video_series/style_lock.py`
- Read: `server/app/domains/agency_operations/agency_router.py`
- Read: `server/app/domains/creative_library/anchor_service.py`

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-production-status-domain-imports-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-production-status-domain-imports-plan.md"
DOMAIN_IMPORT_FILES = [
    REPO_ROOT / "server/app/domains/ai_video_series/story_planning.py",
    REPO_ROOT / "server/app/domains/ai_video_series/style_lock.py",
    REPO_ROOT / "server/app/domains/agency_operations/agency_router.py",
    REPO_ROOT / "server/app/domains/creative_library/anchor_service.py",
]


def test_production_status_import_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.video_production.production_status",
        "app.services.production_status",
        "style_lock",
        "story_planning",
    ]:
        assert term in spec
        assert term in plan
```

- [x] **Step 2: Complete the boundary test**

```python
def test_domain_modules_import_production_status_from_domain_path():
    for path in DOMAIN_IMPORT_FILES:
        text = path.read_text(encoding="utf-8")
        assert "app.domains.video_production.production_status" in text
        assert "app.services.production_status" not in text


def test_legacy_production_status_facade_still_resolves_to_domain_module():
    legacy = importlib.import_module("app.services.production_status")
    domain = importlib.import_module("app.domains.video_production.production_status")
    assert legacy is domain
    assert legacy.JOB_QUEUED == domain.JOB_QUEUED
    assert legacy.REFERENCE_CHARACTER_ANCHOR == domain.REFERENCE_CHARACTER_ANCHOR
```

- [x] **Step 3: Run the red test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_production_status_domain_imports.py -q
```

Expected: FAIL because the four domain modules still import `app.services.production_status`.

### Task 2: Import Migration

**Files:**
- Modify: `server/app/domains/ai_video_series/story_planning.py`
- Modify: `server/app/domains/ai_video_series/style_lock.py`
- Modify: `server/app/domains/agency_operations/agency_router.py`
- Modify: `server/app/domains/creative_library/anchor_service.py`

- [x] **Step 1: Replace legacy imports**

Replace each `from app.services.production_status import ...` line with:

```python
from app.domains.video_production.production_status import ...
```

- [x] **Step 2: Run verification**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_production_status_domain_imports.py -q
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
rg -n "from app\.services\.production_status import" server/app/domains -g "*.py"
```

Expected: pytest passes, app import prints the title, and `rg` returns no domain import matches.

- [x] **Step 3: Commit**

```powershell
git add -f docs/superpowers/specs/2026-06-20-production-status-domain-imports-design.md docs/superpowers/plans/2026-06-20-production-status-domain-imports-plan.md server/tests/test_production_status_domain_imports.py server/app/domains/ai_video_series/story_planning.py server/app/domains/ai_video_series/style_lock.py server/app/domains/agency_operations/agency_router.py server/app/domains/creative_library/anchor_service.py
git commit -m "refactor: use production status domain imports"
```

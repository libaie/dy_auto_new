# Visual Style Domain Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Point `ai_video_series.style_lock` at the creative-library visual style domain module.

**Architecture:** The implementation already lives in `app.domains.creative_library.visual_style_inference_service`; the legacy service remains a `sys.modules` facade.

**Tech Stack:** Python, pytest, existing compatibility facade.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_visual_style_domain_import.py`
- Read: `server/app/domains/ai_video_series/style_lock.py`

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-visual-style-domain-import-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-visual-style-domain-import-plan.md"
STYLE_LOCK_PATH = REPO_ROOT / "server/app/domains/ai_video_series/style_lock.py"


def test_visual_style_import_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.creative_library.visual_style_inference_service",
        "app.services.visual_style_inference_service",
        "style_lock",
    ]:
        assert term in spec
        assert term in plan
```

- [x] **Step 2: Complete the boundary test**

```python
def test_style_lock_imports_visual_style_from_domain_path():
    text = STYLE_LOCK_PATH.read_text(encoding="utf-8")
    assert "app.domains.creative_library.visual_style_inference_service" in text
    assert "app.services.visual_style_inference_service" not in text


def test_legacy_visual_style_facade_still_resolves_to_domain_module():
    legacy = importlib.import_module("app.services.visual_style_inference_service")
    domain = importlib.import_module("app.domains.creative_library.visual_style_inference_service")
    assert legacy is domain
    assert legacy.infer_visual_style_from_story is domain.infer_visual_style_from_story
    assert legacy.DEFAULT_NEGATIVE == domain.DEFAULT_NEGATIVE
```

- [x] **Step 3: Run the red test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_visual_style_domain_import.py -q
```

Expected: FAIL because `style_lock.py` still imports the legacy service facade.

### Task 2: Import Migration

**Files:**
- Modify: `server/app/domains/ai_video_series/style_lock.py`

- [x] **Step 1: Replace legacy import**

```python
from app.domains.creative_library.visual_style_inference_service import (
    append_visual_style_constraints,
    infer_visual_style_from_story,
    merge_visual_style,
    reference_prompt_matches_visual_style,
)
```

- [x] **Step 2: Run verification**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_visual_style_domain_import.py server/tests/test_creative_library_visual_style_service_facade.py -q
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
rg -n "from app\.services\.visual_style_inference_service" server/app/domains -g "*.py"
```

Expected: pytest passes, app import prints the title, and `rg` returns no domain matches.

- [x] **Step 3: Commit**

```powershell
git add -f docs/superpowers/specs/2026-06-20-visual-style-domain-import-design.md docs/superpowers/plans/2026-06-20-visual-style-domain-import-plan.md server/tests/test_visual_style_domain_import.py server/app/domains/ai_video_series/style_lock.py
git commit -m "refactor: use visual style domain import"
```

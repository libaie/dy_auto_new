# Creative Visual Style Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move creative visual style inference into the Creative Library domain while preserving legacy imports.

**Architecture:** `app.domains.creative_library.visual_style_inference_service` becomes the implementation owner. `app.services.visual_style_inference_service` becomes a `sys.modules` alias facade. `reference_asset_service` imports the domain path directly; one-sentence and AI video series callers keep compatibility imports.

**Tech Stack:** Python, pytest, Python module aliasing via `sys.modules`.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_creative_library_visual_style_service_facade.py`
- Read: `server/app/services/visual_style_inference_service.py`
- Read: `server/app/domains/creative_library/reference_asset_service.py`
- Read: `server/app/domains/creative_library/README.md`

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-creative-visual-style-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-creative-visual-style-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/creative_library/visual_style_inference_service.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/visual_style_inference_service.py"
REFERENCE_ASSET_PATH = REPO_ROOT / "server/app/domains/creative_library/reference_asset_service.py"
README_PATH = REPO_ROOT / "server/app/domains/creative_library/README.md"


def test_visual_style_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.creative_library.visual_style_inference_service",
        "app.services.visual_style_inference_service",
        "infer_visual_style_from_story",
        "DEFAULT_NEGATIVE",
    ]:
        assert term in spec
        assert term in plan
```

- [x] **Step 2: Complete the boundary test**

```python
def test_visual_style_domain_file_exists():
    assert DOMAIN_PATH.exists()


def test_legacy_visual_style_service_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.creative_library" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def infer_visual_style_from_story" not in text
    assert "DEFAULT_NEGATIVE =" not in text
    assert _line_count(LEGACY_PATH) <= 12


def test_legacy_visual_style_module_is_domain_module():
    legacy = importlib.import_module("app.services.visual_style_inference_service")
    domain = importlib.import_module("app.domains.creative_library.visual_style_inference_service")
    assert legacy is domain
    assert legacy.infer_visual_style_from_story is domain.infer_visual_style_from_story
    assert legacy.DEFAULT_NEGATIVE == domain.DEFAULT_NEGATIVE


def test_services_parent_package_visual_style_attribute_is_domain_module():
    from app.services import visual_style_inference_service as parent_import

    domain = importlib.import_module("app.domains.creative_library.visual_style_inference_service")
    assert parent_import is domain


def test_reference_asset_service_imports_domain_visual_style_service():
    text = REFERENCE_ASSET_PATH.read_text(encoding="utf-8")
    assert "app.domains.creative_library.visual_style_inference_service" in text
    assert "app.services.visual_style_inference_service" not in text


def test_creative_library_docs_register_visual_style_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "visual_style_inference_service.py",
        "infer_visual_style_from_story",
        "app.services.visual_style_inference_service",
        "app.domains.creative_library.visual_style_inference_service",
    ]:
        assert term in readme


def test_legacy_visual_style_behavior_stays_available():
    legacy = importlib.import_module("app.services.visual_style_inference_service")
    style = legacy.infer_visual_style_from_story("现实生活 普通中老年 控糖")
    assert style["medium"] == "photorealistic_live_action"
    assert "photorealistic live-action" in style["prompt"]
    assert "no anime" in style["negative_prompt"]


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
```

- [x] **Step 3: Run the red test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_creative_library_visual_style_service_facade.py -q
```

Expected: FAIL because the domain file, facade, direct reference asset import, and README registration are not in place.

### Task 2: Domain Migration

**Files:**
- Create: `server/app/domains/creative_library/visual_style_inference_service.py`
- Modify: `server/app/services/visual_style_inference_service.py`
- Modify: `server/app/domains/creative_library/reference_asset_service.py`

- [x] **Step 1: Move implementation**

Copy the current service body into:

```text
server/app/domains/creative_library/visual_style_inference_service.py
```

- [x] **Step 2: Replace legacy module with facade**

```python
"""Compatibility facade for creative library visual style inference."""

import sys

from app.domains.creative_library import visual_style_inference_service as _domain_module

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [x] **Step 3: Update reference asset import**

Replace:

```python
from app.services.visual_style_inference_service import (
```

with:

```python
from app.domains.creative_library.visual_style_inference_service import (
```

### Task 3: Documentation

**Files:**
- Modify: `server/app/domains/creative_library/README.md`

- [x] **Step 1: Register ownership**

```markdown
- `visual_style_inference_service.py` owns story-text style inference,
  visual style merging, prompt constraint appending, and stored prompt style
  matching.
```

- [x] **Step 2: Register facade**

```markdown
| `app.services.visual_style_inference_service` | `app.domains.creative_library.visual_style_inference_service` | Domain modules import the domain service path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
```

### Task 4: Verification

- [x] **Step 1: Run boundary test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_creative_library_visual_style_service_facade.py -q
```

Expected: PASS.

- [x] **Step 2: Run reference asset tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_reference_asset_service.py -q
```

Expected: PASS or report unrelated pre-existing dirty-test failure with output.

- [x] **Step 3: Run app import smoke**

```powershell
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
```

Expected: prints the app title.

- [x] **Step 4: Verify production legacy import inventory**

```powershell
rg -n "app\.services\.visual_style_inference_service" server/app -g "*.py"
```

Expected: only one-sentence and AI video series callers keep approved compatibility imports.

- [x] **Step 5: Commit**

```powershell
git add -f docs/superpowers/specs/2026-06-20-creative-visual-style-domain-design.md docs/superpowers/plans/2026-06-20-creative-visual-style-domain-plan.md server/tests/test_creative_library_visual_style_service_facade.py server/app/domains/creative_library/visual_style_inference_service.py server/app/services/visual_style_inference_service.py server/app/domains/creative_library/reference_asset_service.py server/app/domains/creative_library/README.md
git commit -m "refactor: move visual style inference into creative library"
```

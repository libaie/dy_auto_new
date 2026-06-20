# Script Pipeline Storyboard Timing Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move storyboard timing helpers into the Script Pipeline domain while preserving legacy imports.

**Architecture:** `app.domains.script_pipeline.storyboard_timing` becomes the implementation owner. `app.services.storyboard_timing` becomes a `sys.modules` alias facade. `script_pipeline_service` imports the domain path directly; production-run and one-sentence callers keep compatibility imports.

**Tech Stack:** Python, pytest, Python module aliasing via `sys.modules`.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_script_pipeline_storyboard_timing_facade.py`
- Read: `server/app/services/storyboard_timing.py`
- Read: `server/app/domains/script_pipeline/script_pipeline_service.py`
- Read: `server/app/domains/script_pipeline/README.md`

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-script-pipeline-storyboard-timing-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-script-pipeline-storyboard-timing-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/script_pipeline/storyboard_timing.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/storyboard_timing.py"
SERVICE_PATH = REPO_ROOT / "server/app/domains/script_pipeline/script_pipeline_service.py"
README_PATH = REPO_ROOT / "server/app/domains/script_pipeline/README.md"


def test_storyboard_timing_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.script_pipeline.storyboard_timing",
        "app.services.storyboard_timing",
        "annotate_storyboard_with_timing",
        "build_detailed_video_prompt",
    ]:
        assert term in spec
        assert term in plan
```

- [x] **Step 2: Complete the boundary test**

```python
def test_storyboard_timing_domain_file_exists():
    assert DOMAIN_PATH.exists()


def test_legacy_storyboard_timing_service_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.script_pipeline" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def annotate_storyboard_with_timing" not in text
    assert "DEFAULT_TIMED_SHOT_SECONDS =" not in text
    assert _line_count(LEGACY_PATH) <= 12


def test_legacy_storyboard_timing_module_is_domain_module():
    legacy = importlib.import_module("app.services.storyboard_timing")
    domain = importlib.import_module("app.domains.script_pipeline.storyboard_timing")
    assert legacy is domain
    assert legacy.annotate_storyboard_with_timing is domain.annotate_storyboard_with_timing
    assert legacy.build_detailed_video_prompt is domain.build_detailed_video_prompt


def test_services_parent_package_storyboard_timing_attribute_is_domain_module():
    from app.services import storyboard_timing as parent_import

    domain = importlib.import_module("app.domains.script_pipeline.storyboard_timing")
    assert parent_import is domain


def test_script_pipeline_service_imports_domain_storyboard_timing():
    text = SERVICE_PATH.read_text(encoding="utf-8")
    assert "app.domains.script_pipeline.storyboard_timing" in text
    assert "app.services.storyboard_timing" not in text


def test_script_pipeline_docs_register_storyboard_timing_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "storyboard_timing.py",
        "annotate_storyboard_with_timing",
        "app.services.storyboard_timing",
        "app.domains.script_pipeline.storyboard_timing",
    ]:
        assert term in readme


def test_legacy_storyboard_timing_behavior_stays_available():
    legacy = importlib.import_module("app.services.storyboard_timing")
    storyboard = legacy.annotate_storyboard_with_timing({
        "frames": [
            {"duration": 1.5, "narration": "hello"},
            {"duration": 0, "image_prompt": "frame"},
        ]
    })
    assert storyboard["frame_count"] == 2
    assert storyboard["total_duration"] == 3.5
    assert storyboard["frames"][0]["time_range"] == "0-1.5秒"
    assert storyboard["frames"][1]["duration"] == legacy.DEFAULT_TIMED_SHOT_SECONDS


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
```

- [x] **Step 3: Run the red test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_script_pipeline_storyboard_timing_facade.py -q
```

Expected: FAIL because the domain file, facade, direct script pipeline import, and README registration are not in place.

### Task 2: Domain Migration

**Files:**
- Create: `server/app/domains/script_pipeline/storyboard_timing.py`
- Modify: `server/app/services/storyboard_timing.py`
- Modify: `server/app/domains/script_pipeline/script_pipeline_service.py`

- [x] **Step 1: Move implementation**

Copy the current service body into:

```text
server/app/domains/script_pipeline/storyboard_timing.py
```

- [x] **Step 2: Replace legacy module with facade**

```python
"""Compatibility facade for script pipeline storyboard timing helpers."""

import sys

from app.domains.script_pipeline import storyboard_timing as _domain_module

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [x] **Step 3: Update script pipeline service import**

Replace:

```python
from app.services.storyboard_timing import (
```

with:

```python
from app.domains.script_pipeline.storyboard_timing import (
```

### Task 3: Documentation

**Files:**
- Modify: `server/app/domains/script_pipeline/README.md`

- [x] **Step 1: Register ownership**

```markdown
- `storyboard_timing.py` owns `annotate_storyboard_with_timing`, shot duration
  normalization, timed storyboard line rendering, and detailed image/video
  prompt timing text.
```

- [x] **Step 2: Register facade**

```markdown
| `app.services.storyboard_timing` | `app.domains.script_pipeline.storyboard_timing` | Domain modules import the domain service path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
```

- [x] **Step 3: Register compatibility boundary**

```markdown
- Non-domain service modules may keep importing `app.services.storyboard_timing`
  until their owning domains move.
```

- [x] **Step 4: Register cleanup gate**

```markdown
Do not remove the legacy storyboard timing facade until all of these are true:

- `rg "app\.services\.storyboard_timing" server/app server/tests` returns only
  compatibility tests and migration docs.
- `test_script_pipeline_storyboard_timing_facade.py` has been replaced with
  tests for direct domain imports.
- Domain-owned production modules import
  `app.domains.script_pipeline.storyboard_timing` directly.
```

### Task 4: Verification

- [x] **Step 1: Run boundary test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_script_pipeline_storyboard_timing_facade.py -q
```

Expected: PASS.

- [x] **Step 2: Run app import smoke**

```powershell
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
```

Expected: prints the app title.

- [x] **Step 3: Verify production legacy import inventory**

```powershell
rg -n "app\.services\.storyboard_timing" server/app -g "*.py"
```

Expected: only production-run and one-sentence callers keep approved compatibility imports.

- [x] **Step 4: Commit**

```powershell
git add -f docs/superpowers/specs/2026-06-20-script-pipeline-storyboard-timing-domain-design.md docs/superpowers/plans/2026-06-20-script-pipeline-storyboard-timing-domain-plan.md server/tests/test_script_pipeline_storyboard_timing_facade.py server/app/domains/script_pipeline/storyboard_timing.py server/app/services/storyboard_timing.py server/app/domains/script_pipeline/script_pipeline_service.py server/app/domains/script_pipeline/README.md
git commit -m "refactor: move storyboard timing into script pipeline"
```

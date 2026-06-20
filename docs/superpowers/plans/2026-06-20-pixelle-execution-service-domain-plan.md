# Pixelle Execution Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Pixelle video stage payload mapping into the Pixelle integration domain while preserving the legacy service import path.

**Architecture:** `app.domains.pixelle_integration.pixelle_execution_service` owns `build_video_stage_frame` and private helpers. `app.services.pixelle_execution_service` aliases the domain module for compatibility.

**Tech Stack:** Python, pytest.

---

### Task 1: Write The Boundary Test

**Files:**
- Create: `server/tests/test_pixelle_execution_service_facade.py`

- [ ] **Step 1: Add this test file**

```python
import importlib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-pixelle-execution-service-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-pixelle-execution-service-domain-plan.md"
README_PATH = REPO_ROOT / "server/app/domains/pixelle_integration/README.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/pixelle_integration/pixelle_execution_service.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/pixelle_execution_service.py"


def test_pixelle_execution_spec_plan_and_readme_document_boundary():
    combined = SPEC_PATH.read_text(encoding="utf-8") + PLAN_PATH.read_text(encoding="utf-8")
    for expected in (
        "app.domains.pixelle_integration.pixelle_execution_service",
        "app.services.pixelle_execution_service",
        "build_video_stage_frame",
        "input_image_url",
    ):
        assert expected in combined

    readme = README_PATH.read_text(encoding="utf-8")
    assert "pixelle_execution_service.py" in readme
    assert "app.domains.pixelle_integration.pixelle_execution_service" in readme
    assert "app.services.pixelle_execution_service" in readme


def test_pixelle_execution_domain_file_owns_payload_mapper():
    text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "def build_video_stage_frame" in text
    assert '"input_image_url"' in text
    assert "app.domains.video_production.production_status" in text
    assert "app.services.production_status" not in text


def test_legacy_pixelle_execution_service_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.pixelle_integration import pixelle_execution_service" in text
    assert "sys.modules[_LEGACY_MODULE_NAME] = _domain_module" in text
    assert "def build_video_stage_frame" not in text
    assert "reference_roles_json" not in text


def test_legacy_pixelle_execution_service_module_is_domain_module():
    for name in (
        "app.services.pixelle_execution_service",
        "app.domains.pixelle_integration.pixelle_execution_service",
    ):
        sys.modules.pop(name, None)

    legacy = importlib.import_module("app.services.pixelle_execution_service")
    domain = importlib.import_module("app.domains.pixelle_integration.pixelle_execution_service")

    assert legacy is domain
    assert legacy.build_video_stage_frame is domain.build_video_stage_frame


def test_pixelle_execution_frame_keeps_input_image_url_behavior():
    domain = importlib.import_module("app.domains.pixelle_integration.pixelle_execution_service")

    frame = domain.build_video_stage_frame(
        {
            "id": "segment-id",
            "continuity_mode": "narrative_cut",
            "input_image_url": "https://cdn.test/input.png",
        },
        approved_image_url="https://cdn.test/approved.png",
    )

    assert frame["approved_image_url"] == "https://cdn.test/approved.png"
    assert frame["input_image_url"] == "https://cdn.test/input.png"
```

- [ ] **Step 2: Verify red**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_pixelle_execution_service_facade.py -q
```

Expected: FAIL because the domain module and README registration do not exist and the legacy module still owns the helper body.

### Task 2: Move The Payload Mapper

**Files:**
- Create: `server/app/domains/pixelle_integration/pixelle_execution_service.py`
- Modify: `server/app/services/pixelle_execution_service.py`
- Modify: `server/app/domains/pixelle_integration/README.md`

- [ ] **Step 1: Copy the current implementation to the domain module**

Copy the current `server/app/services/pixelle_execution_service.py` content to
`server/app/domains/pixelle_integration/pixelle_execution_service.py`.

- [ ] **Step 2: Update the domain import**

In the new domain module, replace:

```python
from app.services.production_status import (
```

with:

```python
from app.domains.video_production.production_status import (
```

- [ ] **Step 3: Replace the legacy service with this facade**

```python
"""Compatibility facade for Pixelle execution payload mapping."""

import sys

from app.domains.pixelle_integration import pixelle_execution_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
```

- [ ] **Step 4: Update the Pixelle README**

Add `pixelle_execution_service.py` to Current Modules and this facade row:

```markdown
| `app.services.pixelle_execution_service` | `app.domains.pixelle_integration.pixelle_execution_service` | Legacy imports remain only in compatibility tests or older callers not yet migrated. |
```

- [ ] **Step 5: Verify green**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_pixelle_execution_service_facade.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_production_segment_continuity.py -q
git diff --check -- docs/superpowers/specs/2026-06-20-pixelle-execution-service-domain-design.md docs/superpowers/plans/2026-06-20-pixelle-execution-service-domain-plan.md server/tests/test_pixelle_execution_service_facade.py server/app/domains/pixelle_integration/pixelle_execution_service.py server/app/services/pixelle_execution_service.py server/app/domains/pixelle_integration/README.md
```

Expected: both pytest commands pass and `git diff --check` exits 0.

- [ ] **Step 6: Commit target files only**

```powershell
git add -f docs/superpowers/specs/2026-06-20-pixelle-execution-service-domain-design.md docs/superpowers/plans/2026-06-20-pixelle-execution-service-domain-plan.md server/tests/test_pixelle_execution_service_facade.py server/app/domains/pixelle_integration/pixelle_execution_service.py server/app/services/pixelle_execution_service.py server/app/domains/pixelle_integration/README.md
git commit --only docs/superpowers/specs/2026-06-20-pixelle-execution-service-domain-design.md docs/superpowers/plans/2026-06-20-pixelle-execution-service-domain-plan.md server/tests/test_pixelle_execution_service_facade.py server/app/domains/pixelle_integration/pixelle_execution_service.py server/app/services/pixelle_execution_service.py server/app/domains/pixelle_integration/README.md -m "refactor: move pixelle execution payload mapper into domain"
```

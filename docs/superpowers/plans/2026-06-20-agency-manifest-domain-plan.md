# Agency Manifest Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move agency manifest loading into the agency operations domain while preserving legacy imports.

**Architecture:** `app.domains.agency_operations.agency_manifest` becomes the implementation owner. `app.services.agency_manifest` becomes a `sys.modules` alias facade. Clean domain callers import the domain helper directly, while dirty service modules keep their approved compatibility imports.

**Tech Stack:** Python, pathlib, Pydantic, functools `lru_cache`, pytest, Python module aliasing via `sys.modules`.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_agency_operations_manifest_facade.py`
- Read: `server/app/services/agency_manifest.py`
- Read: `server/app/domains/agency_operations/agency_router.py`
- Read: `server/app/domains/ai_video_series/story_generator_expert.py`
- Read: `server/app/domains/agency_operations/README.md`

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-agency-manifest-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-agency-manifest-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/agency_operations/agency_manifest.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/agency_manifest.py"
AGENCY_ROUTER_PATH = REPO_ROOT / "server/app/domains/agency_operations/agency_router.py"
STORY_GENERATOR_PATH = REPO_ROOT / "server/app/domains/ai_video_series/story_generator_expert.py"
README_PATH = REPO_ROOT / "server/app/domains/agency_operations/README.md"


def test_agency_manifest_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.agency_operations.agency_manifest",
        "app.services.agency_manifest",
        "AgencyManifest",
        "verify_manifest",
    ]:
        assert term in spec
        assert term in plan
```

- [x] **Step 2: Complete the boundary test**

```python
def test_agency_manifest_domain_file_exists():
    assert DOMAIN_PATH.exists()


def test_legacy_agency_manifest_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "class AgencyManifest" not in text
    assert "def verify_manifest" not in text
    assert _line_count(LEGACY_PATH) <= 12


def test_legacy_agency_manifest_module_is_domain_module():
    legacy = importlib.import_module("app.services.agency_manifest")
    domain = importlib.import_module("app.domains.agency_operations.agency_manifest")
    assert legacy is domain
    assert legacy.AgencyManifest is domain.AgencyManifest
    assert legacy.verify_manifest is domain.verify_manifest
    assert legacy.load_manifest is domain.load_manifest


def test_services_parent_package_agency_manifest_attribute_is_domain_module():
    from app.services import agency_manifest as parent_import

    domain = importlib.import_module("app.domains.agency_operations.agency_manifest")
    assert parent_import is domain


def test_agency_manifest_data_root_stays_under_app_data():
    domain = importlib.import_module("app.domains.agency_operations.agency_manifest")
    assert domain.DATA_ROOT == REPO_ROOT / "server/app/data/agency_agents_zh"
    assert domain.MANIFEST_PATH == domain.DATA_ROOT / "manifest.json"


def test_clean_domain_callers_import_domain_agency_manifest():
    for path in [AGENCY_ROUTER_PATH, STORY_GENERATOR_PATH]:
        text = path.read_text(encoding="utf-8")
        assert "app.domains.agency_operations.agency_manifest" in text
        assert "app.services.agency_manifest" not in text


def test_agency_operations_docs_register_agency_manifest_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.agency_operations.agency_manifest",
        "app.services.agency_manifest",
        "AgencyManifest",
        "approved compatibility imports",
    ]:
        assert term in readme


def test_read_expert_markdown_stays_legacy_compatible():
    legacy = importlib.import_module("app.services.agency_manifest")
    text = legacy.read_expert_markdown("story_generator")
    assert len(text) > 500
    assert legacy.verify_manifest()["ok"] is True


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
```

- [x] **Step 3: Run the red test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_operations_manifest_facade.py -q
```

Expected: FAIL because the domain file, facade, direct domain imports, corrected data root, and README registration are not in place.

### Task 2: Domain Migration

**Files:**
- Create: `server/app/domains/agency_operations/agency_manifest.py`
- Modify: `server/app/services/agency_manifest.py`
- Modify: `server/app/domains/agency_operations/agency_router.py`
- Modify: `server/app/domains/ai_video_series/story_generator_expert.py`

- [x] **Step 1: Move implementation**

Move the current service body into:

```text
server/app/domains/agency_operations/agency_manifest.py
```

Use this data root from the new location:

```python
DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "agency_agents_zh"
```

- [x] **Step 2: Replace legacy module with facade**

```python
"""Compatibility facade for agency manifest helpers."""

import sys

from app.domains.agency_operations import agency_manifest as _domain_module

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [x] **Step 3: Update clean domain imports**

Replace `from app.services.agency_manifest import ...` with:

```python
from app.domains.agency_operations.agency_manifest import ...
```

### Task 3: Documentation

**Files:**
- Modify: `server/app/domains/agency_operations/README.md`

- [x] **Step 1: Register ownership**

```markdown
- `agency_manifest.py` owns `AgencyManifest`, `AgencyManifestError`,
  `EXPERT_IDS`, manifest loading, expert markdown hash checks, legacy expert
  lookup, and manifest verification.
```

- [x] **Step 2: Register facade**

```markdown
| `app.services.agency_manifest` | `app.domains.agency_operations.agency_manifest` | Keep while dirty service modules have approved compatibility imports; remove only after import inventory shows no production legacy imports. |
```

### Task 4: Verification

- [x] **Step 1: Run boundary test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_operations_manifest_facade.py -q
```

Expected: PASS.

- [x] **Step 2: Run existing manifest tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_manifest.py -q
```

Expected: PASS.

- [x] **Step 3: Run focused agency API import test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_api.py -q
```

Expected: PASS.

- [x] **Step 4: Verify production legacy import inventory**

```powershell
rg -n "app\.services\.agency_manifest" server/app -g "*.py"
```

Expected: only dirty or not-yet-moved service modules keep approved compatibility imports.

- [x] **Step 5: Commit**

```powershell
git add -f docs/superpowers/specs/2026-06-20-agency-manifest-domain-design.md docs/superpowers/plans/2026-06-20-agency-manifest-domain-plan.md server/tests/test_agency_operations_manifest_facade.py server/app/domains/agency_operations/agency_manifest.py server/app/services/agency_manifest.py server/app/domains/agency_operations/agency_router.py server/app/domains/ai_video_series/story_generator_expert.py server/app/domains/agency_operations/README.md
git commit -m "refactor: move agency manifest into agency operations"
```

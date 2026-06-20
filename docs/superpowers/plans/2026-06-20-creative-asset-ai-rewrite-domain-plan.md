# Creative Asset AI Rewrite Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move creative asset AI rewrite candidates into the Creative Library domain while preserving legacy imports.

**Architecture:** `app.domains.creative_library.asset_ai_rewrite_service` becomes the implementation owner. `app.services.asset_ai_rewrite_service` becomes a `sys.modules` alias facade. Creative Library routers import the domain path directly.

**Tech Stack:** Python, SQLAlchemy ORM session usage, pytest, Python module aliasing via `sys.modules`.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_creative_library_asset_ai_rewrite_service_facade.py`
- Read: `server/app/services/asset_ai_rewrite_service.py`
- Read: `server/app/domains/creative_library/characters_router.py`
- Read: `server/app/domains/creative_library/scenes_router.py`
- Read: `server/app/domains/creative_library/README.md`

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-creative-asset-ai-rewrite-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-creative-asset-ai-rewrite-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/creative_library/asset_ai_rewrite_service.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/asset_ai_rewrite_service.py"
CHARACTERS_ROUTER_PATH = REPO_ROOT / "server/app/domains/creative_library/characters_router.py"
SCENES_ROUTER_PATH = REPO_ROOT / "server/app/domains/creative_library/scenes_router.py"
README_PATH = REPO_ROOT / "server/app/domains/creative_library/README.md"


def test_asset_ai_rewrite_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.creative_library.asset_ai_rewrite_service",
        "app.services.asset_ai_rewrite_service",
        "AssetAiRewriteError",
        "generate_character_rewrite_candidate",
    ]:
        assert term in spec
        assert term in plan
```

- [x] **Step 2: Complete the boundary test**

```python
def test_asset_ai_rewrite_domain_file_exists():
    assert DOMAIN_PATH.exists()


def test_legacy_asset_ai_rewrite_service_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.creative_library" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def generate_character_rewrite_candidate" not in text
    assert "class AssetAiRewriteError" not in text
    assert _line_count(LEGACY_PATH) <= 12


def test_legacy_asset_ai_rewrite_module_is_domain_module():
    legacy = importlib.import_module("app.services.asset_ai_rewrite_service")
    domain = importlib.import_module("app.domains.creative_library.asset_ai_rewrite_service")
    assert legacy is domain
    assert legacy.AssetAiRewriteError is domain.AssetAiRewriteError
    assert legacy.generate_character_rewrite_candidate is domain.generate_character_rewrite_candidate


def test_services_parent_package_asset_ai_rewrite_attribute_is_domain_module():
    from app.services import asset_ai_rewrite_service as parent_import

    domain = importlib.import_module("app.domains.creative_library.asset_ai_rewrite_service")
    assert parent_import is domain


def test_creative_library_routers_import_domain_asset_ai_rewrite_service():
    for path in [CHARACTERS_ROUTER_PATH, SCENES_ROUTER_PATH]:
        text = path.read_text(encoding="utf-8")
        assert "app.domains.creative_library.asset_ai_rewrite_service" in text
        assert "app.services.asset_ai_rewrite_service" not in text


def test_creative_library_docs_register_asset_ai_rewrite_service_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "asset_ai_rewrite_service.py",
        "AssetAiRewriteError",
        "app.services.asset_ai_rewrite_service",
        "app.domains.creative_library.asset_ai_rewrite_service",
    ]:
        assert term in readme


def test_legacy_monkeypatch_is_visible_on_domain_module(monkeypatch):
    legacy = importlib.import_module("app.services.asset_ai_rewrite_service")
    domain = importlib.import_module("app.domains.creative_library.asset_ai_rewrite_service")

    def fake_parse_candidate(raw, allowed_fields):
        return {"name": "Candidate"}

    monkeypatch.setattr("app.services.asset_ai_rewrite_service._parse_candidate", fake_parse_candidate)

    assert domain._parse_candidate("raw", ("name",)) == {"name": "Candidate"}
    assert legacy._parse_candidate is domain._parse_candidate


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
```

- [x] **Step 3: Run the red test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_creative_library_asset_ai_rewrite_service_facade.py -q
```

Expected: FAIL because the domain file, facade, direct router imports, and README registration are not in place.

### Task 2: Domain Migration

**Files:**
- Create: `server/app/domains/creative_library/asset_ai_rewrite_service.py`
- Modify: `server/app/services/asset_ai_rewrite_service.py`
- Modify: `server/app/domains/creative_library/characters_router.py`
- Modify: `server/app/domains/creative_library/scenes_router.py`

- [x] **Step 1: Move implementation**

Copy the current service body into:

```text
server/app/domains/creative_library/asset_ai_rewrite_service.py
```

- [x] **Step 2: Replace legacy module with facade**

```python
"""Compatibility facade for creative library asset AI rewrite services."""

import sys

from app.domains.creative_library import asset_ai_rewrite_service as _domain_module

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [x] **Step 3: Update creative router imports**

Replace:

```python
from app.services.asset_ai_rewrite_service import (
```

with:

```python
from app.domains.creative_library.asset_ai_rewrite_service import (
```

### Task 3: Documentation

**Files:**
- Modify: `server/app/domains/creative_library/README.md`

- [x] **Step 1: Register ownership**

```markdown
- `asset_ai_rewrite_service.py` owns `AssetAiRewriteError`, character/scene
  candidate-only rewrites, allowed field filtering, and AI output parsing.
```

- [x] **Step 2: Register facade**

```markdown
| `app.services.asset_ai_rewrite_service` | `app.domains.creative_library.asset_ai_rewrite_service` | Domain modules import the domain service path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
```

### Task 4: Verification

- [x] **Step 1: Run boundary test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_creative_library_asset_ai_rewrite_service_facade.py -q
```

Expected: PASS.

- [x] **Step 2: Run existing asset AI rewrite tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_asset_ai_rewrite_service.py -q
```

Expected: PASS.

- [x] **Step 3: Run app import smoke**

```powershell
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
```

Expected: prints the app title.

- [x] **Step 4: Verify production legacy import inventory**

```powershell
rg -n "app\.services\.asset_ai_rewrite_service" server/app -g "*.py"
```

Expected: no production imports remain outside the legacy facade.

- [x] **Step 5: Commit**

```powershell
git add -f docs/superpowers/specs/2026-06-20-creative-asset-ai-rewrite-domain-design.md docs/superpowers/plans/2026-06-20-creative-asset-ai-rewrite-domain-plan.md server/tests/test_creative_library_asset_ai_rewrite_service_facade.py server/app/domains/creative_library/asset_ai_rewrite_service.py server/app/services/asset_ai_rewrite_service.py server/app/domains/creative_library/characters_router.py server/app/domains/creative_library/scenes_router.py server/app/domains/creative_library/README.md
git commit -m "refactor: move asset ai rewrite into creative library"
```

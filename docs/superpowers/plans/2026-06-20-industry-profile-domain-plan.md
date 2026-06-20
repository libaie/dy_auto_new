# Industry Profile Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move DM industry profile helpers into the content collection domain while preserving legacy imports.

**Architecture:** `app.domains.content_collection.industry_profile_service` becomes the implementation owner. `app.services.industry_profile_service` becomes a `sys.modules` alias facade. `content_collection.mutations` imports the domain helper directly, and JSON data stays in `server/app/data/industry_profiles`.

**Tech Stack:** Python, JSON files, `functools.lru_cache`, pytest, Python module aliasing via `sys.modules`.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_content_collection_industry_profile_facade.py`
- Read: `server/app/services/industry_profile_service.py`
- Read: `server/app/domains/content_collection/mutations.py`
- Read: `server/app/domains/content_collection/README.md`

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-industry-profile-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-industry-profile-domain-plan.md"
DOMAIN_PROFILE_PATH = REPO_ROOT / "server/app/domains/content_collection/industry_profile_service.py"
LEGACY_PROFILE_PATH = REPO_ROOT / "server/app/services/industry_profile_service.py"
MUTATIONS_PATH = REPO_ROOT / "server/app/domains/content_collection/mutations.py"
README_PATH = REPO_ROOT / "server/app/domains/content_collection/README.md"


def test_industry_profile_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.content_collection.industry_profile_service",
        "app.services.industry_profile_service",
        "load_profile",
    ]:
        assert term in spec
        assert term in plan
```

- [x] **Step 2: Complete the boundary test**

```python
def test_industry_profile_domain_file_exists():
    assert DOMAIN_PROFILE_PATH.exists()


def test_legacy_industry_profile_is_thin_facade():
    text = LEGACY_PROFILE_PATH.read_text(encoding="utf-8")
    assert "app.domains.content_collection" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def load_profile" not in text
    assert "def list_industries" not in text
    assert _line_count(LEGACY_PROFILE_PATH) <= 12


def test_legacy_industry_profile_module_is_domain_module():
    legacy = importlib.import_module("app.services.industry_profile_service")
    domain = importlib.import_module("app.domains.content_collection.industry_profile_service")
    assert legacy is domain
    assert legacy.load_profile is domain.load_profile
    assert legacy.list_industries is domain.list_industries


def test_services_parent_package_industry_profile_attribute_is_domain_module():
    from app.services import industry_profile_service as parent_import

    domain = importlib.import_module("app.domains.content_collection.industry_profile_service")
    assert parent_import is domain


def test_content_collection_mutations_import_domain_industry_profile_only():
    text = MUTATIONS_PATH.read_text(encoding="utf-8")
    assert "app.domains.content_collection.industry_profile_service" in text
    assert "app.services.industry_profile_service" not in text


def test_content_collection_docs_register_industry_profile_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.content_collection.industry_profile_service",
        "app.services.industry_profile_service",
        "load_profile",
        "server/app/data/industry_profiles",
    ]:
        assert term in readme


def test_industry_profile_fallback_and_list_stay_legacy_compatible():
    legacy = importlib.import_module("app.services.industry_profile_service")
    profile = legacy.load_profile("missing-industry")
    industries = legacy.list_industries()
    assert profile["industry"] == "general"
    assert any(item["key"] == "general" for item in industries)


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
```

- [x] **Step 3: Run the red test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_collection_industry_profile_facade.py -q
```

Expected: FAIL because the domain file, facade, and direct content collection imports are not in place.

### Task 2: Domain Migration

**Files:**
- Create: `server/app/domains/content_collection/industry_profile_service.py`
- Modify: `server/app/services/industry_profile_service.py`
- Modify: `server/app/domains/content_collection/mutations.py`

- [x] **Step 1: Move implementation**

Move the current service body into:

```text
server/app/domains/content_collection/industry_profile_service.py
```

Use this data path from the new location:

```python
PROFILES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "industry_profiles"
)
```

- [x] **Step 2: Replace legacy module with facade**

```python
"""Compatibility facade for content collection industry profiles."""

import sys

from app.domains.content_collection import industry_profile_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

- [x] **Step 3: Update mutation imports**

Replace `from app.services.industry_profile_service import load_profile` with:

```python
from app.domains.content_collection.industry_profile_service import load_profile
```

### Task 3: Documentation

**Files:**
- Modify: `server/app/domains/content_collection/README.md`

- [x] **Step 1: Register ownership**

```markdown
- `app.domains.content_collection.industry_profile_service` owns `load_profile`, `list_industries`, and DM industry compliance profile JSON loading from `server/app/data/industry_profiles`.
```

- [x] **Step 2: Register facade**

```markdown
| `app.services.industry_profile_service` | `app.domains.content_collection.industry_profile_service` | Industry profile domain slice | Remove only after import inventory shows no production imports of `app.services.industry_profile_service`. |
```

### Task 4: Verification

- [x] **Step 1: Run boundary test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_collection_industry_profile_facade.py -q
```

Expected: PASS.

- [x] **Step 2: Run content collection mutation tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_collection_mutations.py -q
```

Expected: PASS.

- [x] **Step 3: Verify production legacy import inventory**

```powershell
rg -n "app\.services\.industry_profile_service" server/app -g "*.py"
```

Expected: no production imports.

- [x] **Step 4: Commit**

```powershell
git add -f docs/superpowers/specs/2026-06-20-industry-profile-domain-design.md docs/superpowers/plans/2026-06-20-industry-profile-domain-plan.md server/tests/test_content_collection_industry_profile_facade.py server/app/domains/content_collection/industry_profile_service.py server/app/services/industry_profile_service.py server/app/domains/content_collection/mutations.py server/app/domains/content_collection/README.md
git commit -m "refactor: move industry profiles into content collection"
```

# Model Migration Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move legacy AI model migration helpers into `app.domains.model_configuration` with a legacy facade.

**Architecture:** Copy the current implementation into `server/app/domains/model_configuration/migration.py`, change its crypto import to the domain path, and replace `server/app/services/migration.py` with the existing `sys.modules` facade pattern.

**Tech Stack:** Python, SQLAlchemy, pytest.

---

## Files

- Create: `server/app/domains/model_configuration/migration.py`
- Modify: `server/app/services/migration.py`
- Modify: `server/app/domains/model_configuration/README.md`
- Create: `server/tests/test_model_configuration_migration_facade.py`

### Task 1: Boundary Test

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-model-migration-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-model-migration-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/model_configuration/migration.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/migration.py"
README_PATH = REPO_ROOT / "server/app/domains/model_configuration/README.md"


def test_model_migration_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.model_configuration.migration",
        "app.services.migration",
        "migrate_legacy_settings",
        "_normalize_model_name",
        "_find_existing",
    ]:
        assert term in spec
        assert term in plan


def test_model_migration_implementation_lives_in_model_configuration_domain():
    domain_text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "def migrate_legacy_settings" in domain_text
    assert "def _normalize_model_name" in domain_text
    assert "def _find_existing" in domain_text
    assert "app.domains.system_configuration.crypto" in domain_text
    assert "app.services.crypto" not in domain_text

    legacy_text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.model_configuration" in legacy_text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in legacy_text
    assert "def migrate_legacy_settings" not in legacy_text


def test_legacy_model_migration_facade_resolves_to_domain_module():
    domain = importlib.import_module("app.domains.model_configuration.migration")
    legacy = importlib.import_module("app.services.migration")
    assert legacy is domain
    assert legacy.migrate_legacy_settings is domain.migrate_legacy_settings
    assert legacy._normalize_model_name is domain._normalize_model_name
    assert legacy._find_existing is domain._find_existing


def test_model_configuration_readme_registers_migration_facade():
    text = README_PATH.read_text(encoding="utf-8")
    assert "app.domains.model_configuration.migration" in text
    assert "app.services.migration" in text
```

- [x] **Step 2: Verify RED**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_model_configuration_migration_facade.py -q
```

Expected: fails because the domain migration module does not exist and the
README has no facade row.

### Task 2: Minimal Migration

- [x] **Step 1: Copy implementation**

Run:

```powershell
Copy-Item -LiteralPath 'server/app/services/migration.py' -Destination 'server/app/domains/model_configuration/migration.py'
```

- [x] **Step 2: Update the canonical crypto import**

Change:

```python
from app.services.crypto import encrypt
```

to:

```python
from app.domains.system_configuration.crypto import encrypt
```

- [x] **Step 3: Replace legacy file with facade**

```python
"""Compatibility facade for model configuration migration helpers."""

import sys

from app.domains.model_configuration import migration as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
```

- [x] **Step 4: Register facade**

Add this README row:

```markdown
| `app.services.migration` | `app.domains.model_configuration.migration` | Keep while legacy tests or maintenance scripts import migration helpers from `app.services`; remove after import inventory is clean. |
```

- [x] **Step 5: Verify GREEN**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_model_configuration_migration_facade.py server/tests/test_ai_model_migration.py -q
```

Expected: all tests pass.

### Task 3: Final Checks

- [x] **Step 1: Import app**

Run from `server`:

```powershell
..\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
```

Expected: exits 0.

- [x] **Step 2: Diff check**

Run:

```powershell
git diff --check -- docs/superpowers/specs/2026-06-20-model-migration-domain-design.md docs/superpowers/plans/2026-06-20-model-migration-domain-plan.md server/tests/test_model_configuration_migration_facade.py server/app/domains/model_configuration/migration.py server/app/services/migration.py server/app/domains/model_configuration/README.md
```

Expected: exits 0.

- [x] **Step 3: Commit target files only**

Run:

```powershell
git add -f docs/superpowers/specs/2026-06-20-model-migration-domain-design.md docs/superpowers/plans/2026-06-20-model-migration-domain-plan.md server/tests/test_model_configuration_migration_facade.py server/app/domains/model_configuration/migration.py server/app/services/migration.py server/app/domains/model_configuration/README.md
git commit --only docs/superpowers/specs/2026-06-20-model-migration-domain-design.md docs/superpowers/plans/2026-06-20-model-migration-domain-plan.md server/tests/test_model_configuration_migration_facade.py server/app/domains/model_configuration/migration.py server/app/services/migration.py server/app/domains/model_configuration/README.md -m "refactor: move model migration into model configuration"
```

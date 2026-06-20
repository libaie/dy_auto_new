# Channel Service Domain Dependencies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Point account-operation channel service internals at content-collection and reporting domain helpers.

**Architecture:** Content template behavior lives in `app.domains.content_collection.content_service`; stats behavior lives in `app.domains.reporting.stats_service`. Legacy services remain compatibility facades.

**Tech Stack:** Python, pytest, existing compatibility facades.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_channel_service_domain_dependencies.py`
- Read: `server/app/domains/account_operations/channel_service.py`

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-channel-service-domain-dependencies-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-channel-service-domain-dependencies-plan.md"
CHANNEL_SERVICE_PATH = REPO_ROOT / "server/app/domains/account_operations/channel_service.py"


def test_channel_dependency_import_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.content_collection.content_service",
        "app.domains.reporting.stats_service",
        "app.services.content_service",
        "app.services.stats_service",
    ]:
        assert term in spec
        assert term in plan
```

- [x] **Step 2: Complete the boundary test**

```python
def test_channel_service_imports_dependencies_from_domain_paths():
    text = CHANNEL_SERVICE_PATH.read_text(encoding="utf-8")
    assert "app.domains.content_collection.content_service" in text
    assert "app.domains.reporting.stats_service" in text
    assert "app.services.content_service" not in text
    assert "app.services.stats_service" not in text


def test_legacy_content_and_stats_facades_resolve_to_domain_modules():
    content_legacy = importlib.import_module("app.services.content_service")
    content_domain = importlib.import_module("app.domains.content_collection.content_service")
    stats_legacy = importlib.import_module("app.services.stats_service")
    stats_domain = importlib.import_module("app.domains.reporting.stats_service")
    assert content_legacy is content_domain
    assert content_legacy.content_service is content_domain.content_service
    assert stats_legacy is stats_domain
    assert stats_legacy.stats_service is stats_domain.stats_service
```

- [x] **Step 3: Run the red test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_channel_service_domain_dependencies.py -q
```

Expected: FAIL because channel service still imports content/stats helpers from legacy service facades.

### Task 2: Import Migration

**Files:**
- Modify: `server/app/domains/account_operations/channel_service.py`
- Modify: `server/tests/test_content_service_domain_facade.py`
- Modify: `server/tests/test_reporting_stats_service_facade.py`

- [x] **Step 1: Replace legacy imports**

```python
from app.domains.content_collection.content_service import content_service as cs
from app.domains.reporting.stats_service import stats_service
```

- [x] **Step 2: Update existing facade boundary expectations**

Existing content and stats facade tests should now expect
`account_operations.channel_service` to use direct domain imports while other
legacy service modules may keep old imports.

- [x] **Step 3: Run verification**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_channel_service_domain_dependencies.py server/tests/test_content_service_domain_facade.py server/tests/test_reporting_stats_service_facade.py server/tests/test_channel_service_domain_facade.py -q
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
rg -n "from app\.services\.(content_service|stats_service)" server/app/domains/account_operations/channel_service.py
```

Expected: pytest passes, app import prints the title, and `rg` returns no channel-service content/stats legacy imports.

- [x] **Step 4: Commit**

```powershell
git add -f docs/superpowers/specs/2026-06-20-channel-service-domain-dependencies-design.md docs/superpowers/plans/2026-06-20-channel-service-domain-dependencies-plan.md server/tests/test_channel_service_domain_dependencies.py server/tests/test_content_service_domain_facade.py server/tests/test_reporting_stats_service_facade.py server/app/domains/account_operations/channel_service.py
git commit -m "refactor: use channel service domain dependencies"
```

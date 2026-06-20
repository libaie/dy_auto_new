# Device Reporting Domain Imports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Point device reporting at reporting and account-operation domain helpers.

**Architecture:** Stats behavior lives in `app.domains.reporting.stats_service`; channel behavior lives in `app.domains.account_operations.channel_service`. Legacy services remain compatibility facades.

**Tech Stack:** Python, pytest, existing compatibility facades.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_device_reporting_domain_imports.py`
- Read: `server/app/domains/device_operations/reporting.py`

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-device-reporting-domain-imports-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-device-reporting-domain-imports-plan.md"
REPORTING_PATH = REPO_ROOT / "server/app/domains/device_operations/reporting.py"


def test_device_reporting_import_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.reporting.stats_service",
        "app.domains.account_operations.channel_service",
        "app.services.stats_service",
        "app.services.channel_service",
    ]:
        assert term in spec
        assert term in plan
```

- [x] **Step 2: Complete the boundary test**

```python
def test_device_reporting_imports_helpers_from_domain_paths():
    text = REPORTING_PATH.read_text(encoding="utf-8")
    assert "app.domains.reporting.stats_service" in text
    assert "app.domains.account_operations.channel_service" in text
    assert "app.services.stats_service" not in text
    assert "app.services.channel_service" not in text


def test_legacy_reporting_and_channel_facades_resolve_to_domain_modules():
    stats_legacy = importlib.import_module("app.services.stats_service")
    stats_domain = importlib.import_module("app.domains.reporting.stats_service")
    channel_legacy = importlib.import_module("app.services.channel_service")
    channel_domain = importlib.import_module("app.domains.account_operations.channel_service")
    assert stats_legacy is stats_domain
    assert stats_legacy.stats_service is stats_domain.stats_service
    assert channel_legacy is channel_domain
    assert channel_legacy.channel_service is channel_domain.channel_service
```

- [x] **Step 3: Run the red test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_reporting_domain_imports.py -q
```

Expected: FAIL because device reporting still imports the legacy service facades.

### Task 2: Import Migration

**Files:**
- Modify: `server/app/domains/device_operations/reporting.py`
- Modify: `server/tests/test_channel_service_domain_facade.py`
- Modify: `server/tests/test_reporting_stats_service_facade.py`

- [x] **Step 1: Replace legacy imports**

```python
from app.domains.reporting.stats_service import stats_service
from app.domains.account_operations.channel_service import channel_service
```

- [x] **Step 2: Update existing facade boundary expectations**

Existing channel and stats facade tests should now expect device reporting to
use direct domain imports while task/service bridges may keep legacy imports.

- [x] **Step 3: Run verification**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_reporting_domain_imports.py server/tests/test_channel_service_domain_facade.py server/tests/test_reporting_stats_service_facade.py -q
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
rg -n "from app\.services\.(stats_service|channel_service)" server/app/domains/device_operations -g "*.py"
```

Expected: pytest passes, app import prints the title, and `rg` returns no device-operation matches.

- [x] **Step 4: Commit**

```powershell
git add -f docs/superpowers/specs/2026-06-20-device-reporting-domain-imports-design.md docs/superpowers/plans/2026-06-20-device-reporting-domain-imports-plan.md server/tests/test_device_reporting_domain_imports.py server/tests/test_channel_service_domain_facade.py server/tests/test_reporting_stats_service_facade.py server/app/domains/device_operations/reporting.py
git commit -m "refactor: use device reporting domain imports"
```

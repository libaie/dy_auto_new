# Provider Helper Domain Imports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Point domain code at video production provider helper modules instead of legacy service facades.

**Architecture:** `provider_cost_reservation_service` and `provider_capability_service` already live in `app.domains.video_production`. This change updates direct domain consumers and leaves service facades intact for compatibility.

**Tech Stack:** Python, pytest, existing `sys.modules` compatibility facades.

---

### Task 1: Boundary Test

**Files:**
- Create: `server/tests/test_provider_helper_domain_imports.py`
- Read: `server/app/domains/agency_operations/agency_router.py`
- Read: `server/app/domains/system_operations/system_health_router.py`

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-provider-helper-domain-imports-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-provider-helper-domain-imports-plan.md"
AGENCY_ROUTER_PATH = REPO_ROOT / "server/app/domains/agency_operations/agency_router.py"
SYSTEM_HEALTH_PATH = REPO_ROOT / "server/app/domains/system_operations/system_health_router.py"


def test_provider_helper_import_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.video_production.provider_cost_reservation_service",
        "app.domains.video_production.provider_capability_service",
        "app.services.provider_cost_reservation_service",
        "app.services.provider_capability_service",
    ]:
        assert term in spec
        assert term in plan
```

- [x] **Step 2: Complete the boundary test**

```python
def test_domain_modules_import_provider_helpers_from_domain_path():
    agency_router = AGENCY_ROUTER_PATH.read_text(encoding="utf-8")
    system_health = SYSTEM_HEALTH_PATH.read_text(encoding="utf-8")
    assert "app.domains.video_production.provider_cost_reservation_service" in agency_router
    assert "app.services.provider_cost_reservation_service" not in agency_router
    assert "app.domains.video_production.provider_capability_service" in system_health
    assert "app.services.provider_capability_service" not in system_health


def test_legacy_provider_helper_facades_still_resolve_to_domain_modules():
    cost_legacy = importlib.import_module("app.services.provider_cost_reservation_service")
    cost_domain = importlib.import_module("app.domains.video_production.provider_cost_reservation_service")
    capability_legacy = importlib.import_module("app.services.provider_capability_service")
    capability_domain = importlib.import_module("app.domains.video_production.provider_capability_service")
    assert cost_legacy is cost_domain
    assert cost_legacy.active_reserved_cost is cost_domain.active_reserved_cost
    assert capability_legacy is capability_domain
    assert capability_legacy.capability_from_model_config is capability_domain.capability_from_model_config
```

- [x] **Step 3: Run the red test**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_provider_helper_domain_imports.py -q
```

Expected: FAIL because the two domain files still import provider helpers from `app.services`.

### Task 2: Import Migration

**Files:**
- Modify: `server/app/domains/agency_operations/agency_router.py`
- Modify: `server/app/domains/system_operations/system_health_router.py`

- [x] **Step 1: Replace legacy imports**

```python
from app.domains.video_production.provider_cost_reservation_service import active_reserved_cost
from app.domains.video_production.provider_capability_service import capability_from_model_config
```

- [x] **Step 2: Run verification**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_provider_helper_domain_imports.py -q
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
rg -n "from app\.services\.(provider_cost_reservation_service|provider_capability_service)" server/app/domains -g "*.py"
```

Expected: pytest passes, app import prints the title, and `rg` returns no matches.

- [x] **Step 3: Commit**

```powershell
git add -f docs/superpowers/specs/2026-06-20-provider-helper-domain-imports-design.md docs/superpowers/plans/2026-06-20-provider-helper-domain-imports-plan.md server/tests/test_provider_helper_domain_imports.py server/app/domains/agency_operations/agency_router.py server/app/domains/system_operations/system_health_router.py
git commit -m "refactor: use provider helper domain imports"
```

# Agency Repair Orchestrator Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move agency repair orchestration into `app.domains.agency_operations` with a legacy facade.

**Architecture:** Copy the current implementation into `server/app/domains/agency_operations/agency_repair_orchestrator.py`, change imports to canonical domain paths, then replace `server/app/services/agency_repair_orchestrator.py` with a `sys.modules` facade. Dirty service modules keep legacy imports for this slice.

**Tech Stack:** Python, SQLAlchemy, pytest.

---

## Files

- Create: `server/app/domains/agency_operations/agency_repair_orchestrator.py`
- Modify: `server/app/services/agency_repair_orchestrator.py`
- Modify: `server/app/domains/agency_operations/README.md`
- Create: `server/tests/test_agency_repair_orchestrator_facade.py`

### Task 1: Boundary Test

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path

from app.db_models import AgencyExpertInvocation, ProductionAuditEvent, ProductionPlan, Series, VideoProductionRun


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-agency-repair-orchestrator-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-agency-repair-orchestrator-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/agency_operations/agency_repair_orchestrator.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/agency_repair_orchestrator.py"
README_PATH = REPO_ROOT / "server/app/domains/agency_operations/README.md"


def test_agency_repair_orchestrator_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.agency_operations.agency_repair_orchestrator",
        "app.services.agency_repair_orchestrator",
        "app.domains.agency_operations.agency_repair_contracts",
        "app.domains.video_production.production_status",
        "app.domains.video_production.provider_cost_reservation_service",
        "enqueue_repair_tasks_for_invocation",
    ]:
        assert term in spec
        assert term in plan


def test_agency_repair_orchestrator_implementation_lives_in_agency_operations_domain():
    domain_text = DOMAIN_PATH.read_text(encoding="utf-8")
    assert "def enqueue_repair_tasks_for_invocation" in domain_text
    assert "app.domains.agency_operations.agency_repair_contracts" in domain_text
    assert "app.domains.video_production.production_status" in domain_text
    assert "app.domains.video_production.provider_cost_reservation_service" in domain_text
    assert "app.services.agency_repair_contracts" not in domain_text
    assert "app.services.production_status" not in domain_text
    assert "app.services.provider_cost_reservation_service" not in domain_text

    legacy_text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations" in legacy_text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in legacy_text
    assert "def enqueue_repair_tasks_for_invocation" not in legacy_text


def test_legacy_agency_repair_orchestrator_facade_resolves_to_domain_module():
    domain = importlib.import_module("app.domains.agency_operations.agency_repair_orchestrator")
    legacy = importlib.import_module("app.services.agency_repair_orchestrator")
    assert legacy is domain
    assert legacy.enqueue_repair_tasks_for_invocation is domain.enqueue_repair_tasks_for_invocation


def test_legacy_agency_repair_orchestrator_manual_required_behavior(db):
    legacy = importlib.import_module("app.services.agency_repair_orchestrator")
    series = Series(title="Repair", logline="Repair", genre="test")
    db.add(series)
    db.flush()
    plan = ProductionPlan(series_id=series.id, status="ready", budget_limit=1.0, current_cost=0.0)
    db.add(plan)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id="episode-1",
        production_plan_id=plan.id,
        run_type="real_short_e2e",
        status="running",
        current_stage="style_lock",
    )
    db.add(run)
    db.flush()
    invocation = AgencyExpertInvocation(
        idempotency_key="repair-orchestrator-facade",
        series_id=series.id,
        run_id=run.id,
        production_plan_id=plan.id,
        stage="style_lock",
        expert_id="reviewer",
        role="reviewer",
        execution_status="completed",
        result_status="warning",
        output_summary_json={
            "repair_tasks": [{
                "type": "missing_character_reference",
                "stage": "style_lock",
                "target_type": "character",
                "target_id": "char-1",
                "auto_execute": True,
                "requires_paid_provider": True,
                "estimated_cost": 0.2,
            }],
        },
        source_repo="test",
        source_path="test.md",
        source_sha256="a" * 64,
    )
    db.add(invocation)
    db.flush()

    result = legacy.enqueue_repair_tasks_for_invocation(
        db,
        invocation,
        {
            "enabled": True,
            "max_rounds": 2,
            "budget_limit": 1,
            "allowed_stages": ["style_lock"],
            "allowed_types": ["missing_character_reference"],
        },
    )

    assert result["created"] == 0
    assert result["manual_required"] == 1
    db.flush()
    assert db.query(ProductionAuditEvent).filter_by(event_type="agency_repair_manual_required").count() == 1


def test_agency_operations_readme_registers_repair_orchestrator_facade():
    text = README_PATH.read_text(encoding="utf-8")
    assert "app.domains.agency_operations.agency_repair_orchestrator" in text
    assert "app.services.agency_repair_orchestrator" in text
```

- [x] **Step 2: Verify RED**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_repair_orchestrator_facade.py -q
```

Expected: fails because the domain module does not exist and the README has no
facade row.

### Task 2: Minimal Migration

- [x] **Step 1: Copy implementation**

Run:

```powershell
Copy-Item -LiteralPath 'server/app/services/agency_repair_orchestrator.py' -Destination 'server/app/domains/agency_operations/agency_repair_orchestrator.py'
```

- [x] **Step 2: Update canonical imports**

Use these imports in the domain file:

```python
from app.domains.agency_operations.agency_repair_contracts import AUTO_REPAIR_STAGE, AutoRepairPolicy, RepairTask
from app.domains.video_production.production_status import JOB_BLOCKED, JOB_LEASED, JOB_QUEUED, JOB_RETRY_WAIT, JOB_RUNNING
from app.domains.video_production.provider_cost_reservation_service import active_reserved_cost
```

- [x] **Step 3: Replace legacy file with facade**

```python
"""Compatibility facade for agency repair orchestration."""

import sys

from app.domains.agency_operations import agency_repair_orchestrator as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
```

- [x] **Step 4: Register facade**

Add this README row:

```markdown
| `app.services.agency_repair_orchestrator` | `app.domains.agency_operations.agency_repair_orchestrator` | Keep while dirty service modules import repair orchestration from `app.services`; remove after import inventory is clean. |
```

- [x] **Step 5: Verify GREEN**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_repair_orchestrator_facade.py server/tests/test_agency_repair_orchestrator.py server/tests/test_agency_auto_repair_e2e.py server/tests/test_agency_repair_loop.py -q
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
git diff --check -- docs/superpowers/specs/2026-06-20-agency-repair-orchestrator-domain-design.md docs/superpowers/plans/2026-06-20-agency-repair-orchestrator-domain-plan.md server/tests/test_agency_repair_orchestrator_facade.py server/app/domains/agency_operations/agency_repair_orchestrator.py server/app/services/agency_repair_orchestrator.py server/app/domains/agency_operations/README.md
```

Expected: exits 0.

- [x] **Step 3: Commit target files only**

Run:

```powershell
git add -f docs/superpowers/specs/2026-06-20-agency-repair-orchestrator-domain-design.md docs/superpowers/plans/2026-06-20-agency-repair-orchestrator-domain-plan.md server/tests/test_agency_repair_orchestrator_facade.py server/app/domains/agency_operations/agency_repair_orchestrator.py server/app/services/agency_repair_orchestrator.py server/app/domains/agency_operations/README.md
git commit --only docs/superpowers/specs/2026-06-20-agency-repair-orchestrator-domain-design.md docs/superpowers/plans/2026-06-20-agency-repair-orchestrator-domain-plan.md server/tests/test_agency_repair_orchestrator_facade.py server/app/domains/agency_operations/agency_repair_orchestrator.py server/app/services/agency_repair_orchestrator.py server/app/domains/agency_operations/README.md -m "refactor: move agency repair orchestrator into agency operations"
```

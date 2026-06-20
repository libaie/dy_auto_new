# Agency Debate Audit Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move agency debate audit logic into `app.domains.agency_operations`.

**Architecture:** The domain module owns the implementation. The old
`app.services.agency_debate_audit` path stays as a module alias for
compatibility.

**Tech Stack:** Python stdlib, SQLAlchemy, pytest.

---

### Task 1: Move Implementation

**Files:**

- Move: `server/app/services/agency_debate_audit.py` to `server/app/domains/agency_operations/agency_debate_audit.py`
- Create: `server/app/services/agency_debate_audit.py`
- Modify: `server/tests/test_domain_service_import_inventory.py`

- [ ] **Step 1: Move the implementation file**

```powershell
Move-Item -LiteralPath 'server/app/services/agency_debate_audit.py' -Destination 'server/app/domains/agency_operations/agency_debate_audit.py'
```

- [ ] **Step 2: Use direct domain imports for already migrated modules**

```python
from app.domains.agency_operations.agency_scorecard_contracts import normalize_scorecard, scorecard_blocks_stage
from app.domains.video_production.production_status import JOB_LEASED, JOB_QUEUED, JOB_RETRY_WAIT, JOB_RUNNING
```

- [ ] **Step 3: Add the compatibility alias**

```python
from __future__ import annotations

import sys

from app.domains.agency_operations import agency_debate_audit as _impl

sys.modules[__name__] = _impl
```

- [ ] **Step 4: Record remaining service imports**

```python
("server/app/domains/agency_operations/agency_debate_audit.py", "agency_orchestrator"),
("server/app/domains/agency_operations/agency_debate_audit.py", "production_queue_service"),
```

### Task 2: Verify And Commit

**Files:**

- Add: `docs/superpowers/specs/2026-06-20-agency-debate-audit-domain-design.md`
- Add: `docs/superpowers/plans/2026-06-20-agency-debate-audit-domain-plan.md`
- Add: `server/app/domains/agency_operations/agency_debate_audit.py`
- Modify: `server/app/domains/agency_operations/README.md`
- Add: `server/app/services/agency_debate_audit.py`
- Modify: `server/tests/test_domain_service_import_inventory.py`

- [ ] **Step 1: Run final checks**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/tests/test_agency_debate_audit.py -q
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
```

- [ ] **Step 2: Commit target files only**

```powershell
git add -f docs/superpowers/specs/2026-06-20-agency-debate-audit-domain-design.md docs/superpowers/plans/2026-06-20-agency-debate-audit-domain-plan.md server/app/domains/agency_operations/agency_debate_audit.py server/app/domains/agency_operations/README.md server/app/services/agency_debate_audit.py server/tests/test_domain_service_import_inventory.py
git commit --only docs/superpowers/specs/2026-06-20-agency-debate-audit-domain-design.md docs/superpowers/plans/2026-06-20-agency-debate-audit-domain-plan.md server/app/domains/agency_operations/agency_debate_audit.py server/app/domains/agency_operations/README.md server/app/services/agency_debate_audit.py server/tests/test_domain_service_import_inventory.py -m "refactor: move agency debate audit into domain"
```

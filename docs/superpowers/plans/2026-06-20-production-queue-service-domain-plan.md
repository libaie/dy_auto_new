# Production Queue Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move production job queue logic into `app.domains.video_production`.

**Architecture:** The domain module owns queue implementation. The old
`app.services.production_queue_service` path stays as a module alias for
compatibility.

**Tech Stack:** Python stdlib, SQLAlchemy, pytest.

---

### Task 1: Red Import Inventory

**Files:**

- Modify: `server/tests/test_domain_service_import_inventory.py`

- [ ] **Step 1: Remove queue service domain import allowlist entries**

Remove entries like:

```python
("server/app/domains/video_production/mock_scale_scheduler_service.py", "production_queue_service"),
```

- [ ] **Step 2: Run red**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py -q
```

Expected: FAIL with domain modules still importing
`app.services.production_queue_service`.

### Task 2: Move Queue Implementation

**Files:**

- Move: `server/app/services/production_queue_service.py` to `server/app/domains/video_production/production_queue_service.py`
- Create: `server/app/services/production_queue_service.py`
- Modify: domain modules that imported `app.services.production_queue_service`
- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Move the implementation file**

```powershell
Move-Item -LiteralPath 'server/app/services/production_queue_service.py' -Destination 'server/app/domains/video_production/production_queue_service.py'
```

- [ ] **Step 2: Import status constants from the domain**

```python
from app.domains.video_production.production_status import (
    JOB_BLOCKED,
    JOB_CANCELLED,
    JOB_COMPLETED,
    JOB_FAILED,
    JOB_LEASED,
    JOB_QUEUED,
    JOB_RETRY_WAIT,
    JOB_RUNNING,
    PLAN_READY,
    PLAN_RUNNING,
)
```

- [ ] **Step 3: Update domain queue imports**

```python
from app.domains.video_production.production_queue_service import enqueue_job
```

```python
from app.domains.video_production.production_queue_service import claim_next_job, fail_job, mark_job_completed
```

```python
from app.domains.video_production.production_queue_service import pause_plan_jobs
from app.domains.video_production.production_queue_service import resume_plan_jobs
```

- [ ] **Step 4: Add the compatibility alias**

```python
from __future__ import annotations

import sys

from app.domains.video_production import production_queue_service as _impl

sys.modules[__name__] = _impl
```

- [ ] **Step 5: Remove queue from service implementation inventory**

```python
"production_queue_service.py"
```

### Task 3: Verify And Commit

**Files:**

- Add: `docs/superpowers/specs/2026-06-20-production-queue-service-domain-design.md`
- Add: `docs/superpowers/plans/2026-06-20-production-queue-service-domain-plan.md`
- Modify: `server/app/domains/agency_operations/agency_backtrack_policy.py`
- Modify: `server/app/domains/agency_operations/agency_debate_audit.py`
- Modify: `server/app/domains/ai_video_series/story_planning.py`
- Modify: `server/app/domains/ai_video_series/style_lock.py`
- Add: `server/app/domains/video_production/production_queue_service.py`
- Modify: `server/app/domains/video_production/mock_scale_scheduler_service.py`
- Modify: `server/app/domains/video_production/production_retry_service.py`
- Modify: `server/app/domains/video_production/provider_stage_executor.py`
- Modify: `server/app/domains/video_production/README.md`
- Modify: `server/app/domains/video_production/video_production_router.py`
- Add: `server/app/services/production_queue_service.py`
- Modify: `server/tests/test_domain_service_import_inventory.py`
- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Run final checks**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/tests/test_production_queue_service.py server/tests/test_agency_backtrack_policy.py server/tests/test_agency_debate_audit.py server/tests/test_provider_stage_executor.py -q
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
```

- [ ] **Step 2: Commit target files only**

```powershell
git add -f docs/superpowers/specs/2026-06-20-production-queue-service-domain-design.md docs/superpowers/plans/2026-06-20-production-queue-service-domain-plan.md server/app/domains/agency_operations/agency_backtrack_policy.py server/app/domains/agency_operations/agency_debate_audit.py server/app/domains/ai_video_series/story_planning.py server/app/domains/ai_video_series/style_lock.py server/app/domains/video_production/production_queue_service.py server/app/domains/video_production/mock_scale_scheduler_service.py server/app/domains/video_production/production_retry_service.py server/app/domains/video_production/provider_stage_executor.py server/app/domains/video_production/README.md server/app/domains/video_production/video_production_router.py server/app/services/production_queue_service.py server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py
git commit --only docs/superpowers/specs/2026-06-20-production-queue-service-domain-design.md docs/superpowers/plans/2026-06-20-production-queue-service-domain-plan.md server/app/domains/agency_operations/agency_backtrack_policy.py server/app/domains/agency_operations/agency_debate_audit.py server/app/domains/ai_video_series/story_planning.py server/app/domains/ai_video_series/style_lock.py server/app/domains/video_production/production_queue_service.py server/app/domains/video_production/mock_scale_scheduler_service.py server/app/domains/video_production/production_retry_service.py server/app/domains/video_production/provider_stage_executor.py server/app/domains/video_production/README.md server/app/domains/video_production/video_production_router.py server/app/services/production_queue_service.py server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py -m "refactor: move production queue service into domain"
```

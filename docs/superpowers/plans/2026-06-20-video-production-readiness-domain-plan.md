# Video Production Readiness Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move video production readiness gating into `app.domains.video_production`.

**Architecture:** The domain module owns readiness logic. The old `app.services.video_production_readiness` path stays as a module alias for compatibility.

**Tech Stack:** Python stdlib, FastAPI, SQLAlchemy, pytest.

---

### Task 1: Red Import Inventory

**Files:**

- Modify: `server/tests/test_domain_service_import_inventory.py`

- [ ] **Step 1: Remove the router-to-service readiness import from the allowlist**

```python
("server/app/domains/video_production/video_production_router.py", "video_production_readiness"),
```

- [ ] **Step 2: Run red**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py -q
```

Expected: FAIL with `video_production_router.py` still importing
`video_production_readiness` from `app.services`.

### Task 2: Move Readiness Implementation

**Files:**

- Move: `server/app/services/video_production_readiness.py` to `server/app/domains/video_production/video_production_readiness.py`
- Create: `server/app/services/video_production_readiness.py`
- Modify: `server/app/domains/video_production/video_production_router.py`
- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Move the implementation file**

```powershell
Move-Item -LiteralPath 'server/app/services/video_production_readiness.py' -Destination 'server/app/domains/video_production/video_production_readiness.py'
```

- [ ] **Step 2: Use direct domain imports**

```python
from app.domains.video_production.production_status import JOB_BLOCKED
from app.domains.video_production.video_production_run_types import get_run_type
from app.domains.video_production.video_production_state import (
    IMAGE_READY_STATUS,
    VIDEO_READY_STATUS,
    latest_assets_by_frame,
    production_segment_frame_ids,
)
```

- [ ] **Step 3: Import readiness from the domain router**

```python
from app.domains.video_production.video_production_readiness import build_run_readiness
```

- [ ] **Step 4: Add the compatibility alias**

```python
from __future__ import annotations

import sys

from app.domains.video_production import video_production_readiness as _impl

sys.modules[__name__] = _impl
```

- [ ] **Step 5: Remove readiness from service implementation inventory**

```python
"video_production_readiness.py"
```

### Task 3: Verify And Commit

**Files:**

- Add: `docs/superpowers/specs/2026-06-20-video-production-readiness-domain-design.md`
- Add: `docs/superpowers/plans/2026-06-20-video-production-readiness-domain-plan.md`
- Add: `server/app/domains/video_production/video_production_readiness.py`
- Modify: `server/app/domains/video_production/video_production_router.py`
- Modify: `server/app/domains/video_production/README.md`
- Add: `server/app/services/video_production_readiness.py`
- Modify: `server/tests/test_domain_service_import_inventory.py`
- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Run final checks**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/tests/test_video_production_readiness.py server/tests/test_one_sentence_video.py -q
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
```

- [ ] **Step 2: Commit target files only**

```powershell
git add -f docs/superpowers/specs/2026-06-20-video-production-readiness-domain-design.md docs/superpowers/plans/2026-06-20-video-production-readiness-domain-plan.md server/app/domains/video_production/video_production_readiness.py server/app/domains/video_production/video_production_router.py server/app/domains/video_production/README.md server/app/services/video_production_readiness.py server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py
git commit --only docs/superpowers/specs/2026-06-20-video-production-readiness-domain-design.md docs/superpowers/plans/2026-06-20-video-production-readiness-domain-plan.md server/app/domains/video_production/video_production_readiness.py server/app/domains/video_production/video_production_router.py server/app/domains/video_production/README.md server/app/services/video_production_readiness.py server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py -m "refactor: move video production readiness into domain"
```

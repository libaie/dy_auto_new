# One-Sentence Video Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move one-sentence-to-video orchestration into `video_production` while preserving the legacy service import.

**Architecture:** `app.domains.video_production.one_sentence_video_service` owns one-sentence video orchestration. `app.services.one_sentence_video_service` aliases the domain module until callers move to the domain path.

**Tech Stack:** Python, SQLAlchemy ORM, pytest.

---

### Task 1: Inventory Red

**Files:**
- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Remove `one_sentence_video_service.py` from the service implementation allowlist**

```python
EXPECTED_NON_FACADE_SERVICE_FILES = {
    "video_agency_team.py",
}
```

Also remove the `"one_sentence_video_service.py": "video_production"` entry
from `EXPECTED_SERVICE_DOMAIN_TARGETS`.

- [ ] **Step 2: Verify red**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_service_implementation_inventory.py -q
```

Expected: FAIL with `one_sentence_video_service.py` as an extra non-facade service file.

### Task 2: Move One-Sentence Orchestration

**Files:**
- Create: `server/app/domains/video_production/one_sentence_video_service.py`
- Modify: `server/app/services/one_sentence_video_service.py`
- Modify: `server/tests/test_domain_service_import_inventory.py`
- Modify: `server/app/domains/video_production/README.md`
- Modify: `server/tests/test_service_implementation_inventory.py`

- [ ] **Step 1: Move the implementation**

Move the current implementation from
`server/app/services/one_sentence_video_service.py` to
`server/app/domains/video_production/one_sentence_video_service.py`.

- [ ] **Step 2: Point migrated dependencies at domain paths**

Use domain imports for agency orchestrator, production run, production plan,
production errors, production observability, reference assets, AI text
artifacts, runtime model config, series planning, storyboard timing, run types,
visual style inference, and mock scale scheduler.

- [ ] **Step 3: Keep not-yet-migrated dependencies as explicit legacy imports**

Add these tuples to `EXPECTED_DOMAIN_SERVICE_IMPORTS`:

```python
("server/app/domains/video_production/one_sentence_video_service.py", "video_agency_team"),
("server/app/domains/video_production/one_sentence_video_service.py", "video_production_service"),
```

- [ ] **Step 4: Replace the legacy service with this facade**

```python
"""Compatibility facade for one-sentence video orchestration."""

from __future__ import annotations

import sys

from app.domains.video_production import one_sentence_video_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_domain_module.__name__] = _domain_module
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
```

- [ ] **Step 5: Verify green**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/tests/test_one_sentence_video.py server/tests/test_one_sentence_video_run_types.py server/tests/test_video_production_real_short_mocked_e2e.py server/tests/test_mock_scale_scheduler_service.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit target files only**

```powershell
git add -f docs/superpowers/specs/2026-06-20-one-sentence-video-service-domain-design.md docs/superpowers/plans/2026-06-20-one-sentence-video-service-domain-plan.md server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/app/domains/video_production/one_sentence_video_service.py server/app/services/one_sentence_video_service.py server/app/domains/video_production/README.md
git commit --only docs/superpowers/specs/2026-06-20-one-sentence-video-service-domain-design.md docs/superpowers/plans/2026-06-20-one-sentence-video-service-domain-plan.md server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/app/domains/video_production/one_sentence_video_service.py server/app/services/one_sentence_video_service.py server/app/domains/video_production/README.md -m "refactor: move one sentence video service into domain"
```

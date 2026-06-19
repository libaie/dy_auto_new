# AI Text Artifact Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `AITextArtifactService` into the AI text artifacts domain while preserving old imports through a compatibility facade.

**Architecture:** The implementation lives in `app.domains.ai_text_artifacts.ai_text_artifact_service`. `app.services.ai_text_artifact_service` becomes a `sys.modules` facade so old callers and monkeypatches resolve to the same module object.

**Tech Stack:** Python, SQLAlchemy ORM, FastAPI route modules, pytest.

---

## File Structure

- Create: `server/app/domains/ai_text_artifacts/ai_text_artifact_service.py`
  - Owns `AITextArtifactService`, `SERIES_RUN_ARTIFACT_TYPES`, `EPISODE_RUN_ARTIFACT_TYPES`, and `ARTIFACT_CONSUMPTION_ORDER`.
- Modify: `server/app/services/ai_text_artifact_service.py`
  - Becomes a thin compatibility facade.
- Modify: `server/app/domains/ai_text_artifacts/ai_text_artifacts_router.py`
  - Imports the service from the domain path.
- Modify: `server/app/domains/ai_video_series/artifacts.py`
  - Imports the service from the domain path.
- Modify: `server/app/domains/ai_video_series/read_models.py`
  - Imports the service from the domain path.
- Modify: `server/app/domains/ai_video_series/series_planning_service.py`
  - Imports the service from the domain path.
- Modify: `server/app/domains/ai_video_series/style_lock.py`
  - Imports the service from the domain path.
- Modify: `server/app/domains/director_planning/director_router.py`
  - Imports the service from the domain path.
- Modify: `server/app/domains/video_production/video_production_router.py`
  - Imports the service from the domain path.
- Modify: `server/app/domains/ai_text_artifacts/README.md`
  - Documents service ownership, facade mapping, and cleanup gates.
- Create: `server/tests/test_ai_text_artifact_service_domain_facade.py`
  - Proves service boundary and compatibility.

### Task 1: Red Boundary Test

**Files:**

- Create: `server/tests/test_ai_text_artifact_service_domain_facade.py`
- Create: `docs/superpowers/specs/2026-06-20-ai-text-artifact-service-domain-design.md`
- Create: `docs/superpowers/plans/2026-06-20-ai-text-artifact-service-domain-plan.md`

- [ ] **Step 1: Write the failing test**

Create tests asserting the domain service file exists, the legacy module is a facade, old and new imports are the same module object, domain-owned modules import the domain path, and the README records the service facade.

- [ ] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_text_artifact_service_domain_facade.py -q
```

Expected: FAIL because `server/app/domains/ai_text_artifacts/ai_text_artifact_service.py` does not exist yet, the old service file still contains `class AITextArtifactService`, and domain-owned modules still import `app.services.ai_text_artifact_service`.

### Task 2: Move The Service

**Files:**

- Create: `server/app/domains/ai_text_artifacts/ai_text_artifact_service.py`
- Modify: `server/app/services/ai_text_artifact_service.py`

- [ ] **Step 1: Copy the implementation**

Copy the current contents of `server/app/services/ai_text_artifact_service.py` into `server/app/domains/ai_text_artifacts/ai_text_artifact_service.py` without changing behavior.

- [ ] **Step 2: Replace the legacy service with a facade**

Use this facade shape:

```python
"""Compatibility facade for AI text artifact domain services.

The implementation now lives in app.domains.ai_text_artifacts.ai_text_artifact_service.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.ai_text_artifacts import ai_text_artifact_service as _ai_text_artifact_service

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _ai_text_artifact_service
globals().update(_ai_text_artifact_service.__dict__)
```

### Task 3: Update Domain Imports And Docs

**Files:**

- Modify: `server/app/domains/ai_text_artifacts/ai_text_artifacts_router.py`
- Modify: `server/app/domains/ai_video_series/artifacts.py`
- Modify: `server/app/domains/ai_video_series/read_models.py`
- Modify: `server/app/domains/ai_video_series/series_planning_service.py`
- Modify: `server/app/domains/ai_video_series/style_lock.py`
- Modify: `server/app/domains/director_planning/director_router.py`
- Modify: `server/app/domains/video_production/video_production_router.py`
- Modify: `server/app/domains/ai_text_artifacts/README.md`

- [ ] **Step 1: Change domain imports**

Replace:

```python
from app.services.ai_text_artifact_service import AITextArtifactService
```

With:

```python
from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService
```

- [ ] **Step 2: Update README**

Record `app.services.ai_text_artifact_service` as a facade targeting `app.domains.ai_text_artifacts.ai_text_artifact_service`, and add a cleanup gate requiring only compatibility tests and migration docs to reference the legacy path before removal.

### Task 4: Verify And Commit

**Files:**

- All files listed above.

- [ ] **Step 1: Run the new boundary test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_text_artifact_service_domain_facade.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run focused regression**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_text_artifact_service_domain_facade.py server/tests/test_ai_text_artifacts_domain_boundary.py server/tests/test_ai_text_artifact_service.py server/tests/test_ai_text_artifacts_api.py server/tests/test_series_planning_service.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Commit only touched files**

Use an isolated Git index if the working tree contains unrelated WIP. Commit message:

```text
refactor: move ai text artifact service into domain
```

# AI Video Series Story Generator Expert Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the story generator expert runtime into the AI video series domain while preserving the legacy service import path.

**Architecture:** The implementation lives in `app.domains.ai_video_series.story_generator_expert`. `app.services.story_generator_expert` becomes a `sys.modules` compatibility facade so old imports and monkeypatches resolve to the same module object.

**Tech Stack:** Python, FastAPI service modules, SQLAlchemy session usage, pytest.

---

## File Structure

- Create: `server/app/domains/ai_video_series/story_generator_expert.py`
  - Owns the existing story generator expert runtime, including `StoryGeneratorResult` and `generate_story_plan_with_expert`.
- Modify: `server/app/services/story_generator_expert.py`
  - Becomes a thin compatibility facade to the domain module.
- Modify: `server/app/domains/ai_video_series/series_planning_service.py`
  - Imports `generate_story_plan_with_expert` from the domain module.
- Modify: `server/app/domains/ai_video_series/README.md`
  - Adds the facade register row and cleanup gate.
- Create: `server/tests/test_ai_video_series_story_generator_expert_facade.py`
  - Proves the boundary and compatibility contract.

### Task 1: Red Boundary Test

**Files:**

- Create: `server/tests/test_ai_video_series_story_generator_expert_facade.py`

- [ ] **Step 1: Write the failing test**

Create tests that assert the domain file exists, the legacy module is thin, old and new imports are identical, the domain series planning service imports the domain path, and the README registers the facade.

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_story_generator_expert_facade.py -q
```

Expected: FAIL because `server/app/domains/ai_video_series/story_generator_expert.py` does not exist yet and `series_planning_service.py` still imports from `app.services.story_generator_expert`.

### Task 2: Move Implementation

**Files:**

- Create: `server/app/domains/ai_video_series/story_generator_expert.py`
- Modify: `server/app/services/story_generator_expert.py`
- Modify: `server/app/domains/ai_video_series/series_planning_service.py`

- [ ] **Step 1: Copy the current implementation**

Copy the existing contents of `server/app/services/story_generator_expert.py` into `server/app/domains/ai_video_series/story_generator_expert.py` without changing runtime behavior.

- [ ] **Step 2: Replace the legacy service with a facade**

Use this facade shape:

```python
"""Compatibility facade for AI video series story generator expert services.

The implementation now lives in app.domains.ai_video_series.story_generator_expert.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.ai_video_series import story_generator_expert as _story_generator_expert

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _story_generator_expert
globals().update(_story_generator_expert.__dict__)
```

- [ ] **Step 3: Update the domain series planning import**

Change:

```python
from app.services.story_generator_expert import generate_story_plan_with_expert
```

To:

```python
from app.domains.ai_video_series.story_generator_expert import generate_story_plan_with_expert
```

### Task 3: Documentation And Verification

**Files:**

- Modify: `server/app/domains/ai_video_series/README.md`

- [ ] **Step 1: Register the facade**

Add a facade register row for `app.services.story_generator_expert` targeting `app.domains.ai_video_series.story_generator_expert`.

- [ ] **Step 2: Add cleanup gate text**

Add a cleanup gate requiring `rg "app\.services\.story_generator_expert" server/app server/tests` to return only compatibility tests and migration docs before removing the facade.

- [ ] **Step 3: Run focused tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_story_generator_expert_facade.py server/tests/test_series_planning_service.py server/tests/test_ai_video_series_domain_boundary.py -q
```

Expected: all selected tests pass.

- [ ] **Step 4: Commit only touched files**

Use an isolated Git index if the working tree contains unrelated WIP, and commit only:

```text
docs/superpowers/specs/2026-06-20-ai-video-series-story-generator-expert-domain-design.md
docs/superpowers/plans/2026-06-20-ai-video-series-story-generator-expert-domain-plan.md
server/app/domains/ai_video_series/README.md
server/app/domains/ai_video_series/story_generator_expert.py
server/app/domains/ai_video_series/series_planning_service.py
server/app/services/story_generator_expert.py
server/tests/test_ai_video_series_story_generator_expert_facade.py
```

Commit message:

```text
refactor: move story generator expert into domain
```

### Task 4: Use Domain Agency Persistence Import

**Files:**

- Modify: `server/app/domains/ai_video_series/story_generator_expert.py`
- Test: `server/tests/test_ai_video_series_story_generator_expert_facade.py`

- [ ] **Step 1: Add the failing boundary test**

```python
def test_story_generator_expert_imports_agency_persistence_domain_path():
    text = DOMAIN_SERVICE_PATH.read_text(encoding="utf-8")

    assert "app.domains.agency_operations.agency_persistence" in text
    assert "app.services.agency_persistence" not in text
```

- [ ] **Step 2: Change only the import**

```python
from app.domains.agency_operations.agency_persistence import create_or_resume_invocation, finalize_invocation_and_audit
```

- [ ] **Step 3: Run focused verification**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_story_generator_expert_facade.py server/tests/test_series_planning_service.py -q
```

Expected: all selected tests pass.

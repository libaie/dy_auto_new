# Script Pipeline Service Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the script generation pipeline runtime into the script pipeline domain while preserving old service imports.

**Architecture:** The implementation lives in `app.domains.script_pipeline.script_pipeline_service`. `app.services.script_pipeline` becomes a `sys.modules` facade so old callers and monkeypatches resolve to the same module object.

**Tech Stack:** Python, SQLAlchemy ORM, pytest, existing prompt template files.

---

## File Structure

- Create: `server/app/domains/script_pipeline/script_pipeline_service.py`
  - Owns `DynamicPromptBuilder`, `ScriptGenerationPipeline`, `PipelineManager`, `ScriptGenerationError`, and stage runtime helpers.
- Modify: `server/app/services/script_pipeline.py`
  - Becomes a thin compatibility facade.
- Modify: `server/app/domains/script_pipeline/README.md`
  - Documents service ownership, facade mapping, and cleanup gates.
- Modify: `server/tests/test_script_pipeline_domain_boundary.py`
  - Updates the old service-layer assertion to account for the facade.
- Create: `server/tests/test_script_pipeline_service_domain_facade.py`
  - Proves service boundary and compatibility.

### Task 1: Red Boundary Test

**Files:**

- Create: `server/tests/test_script_pipeline_service_domain_facade.py`
- Create: `docs/superpowers/specs/2026-06-20-script-pipeline-service-domain-design.md`
- Create: `docs/superpowers/plans/2026-06-20-script-pipeline-service-domain-plan.md`

- [ ] **Step 1: Write the failing test**

Create tests asserting the domain service file exists, the legacy service module is a facade, old and new imports are the same module object, and README cleanup gates document the facade.

- [ ] **Step 2: Run the red test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_script_pipeline_service_domain_facade.py -q
```

Expected: FAIL because `server/app/domains/script_pipeline/script_pipeline_service.py` does not exist yet and the old service file still contains the runtime classes.

### Task 2: Move The Runtime

**Files:**

- Create: `server/app/domains/script_pipeline/script_pipeline_service.py`
- Modify: `server/app/services/script_pipeline.py`

- [ ] **Step 1: Copy the implementation**

Copy the current contents of `server/app/services/script_pipeline.py` into `server/app/domains/script_pipeline/script_pipeline_service.py` without changing behavior.

- [ ] **Step 2: Replace the legacy service with a facade**

Use this facade shape:

```python
"""Compatibility facade for script pipeline domain services.

The implementation now lives in app.domains.script_pipeline.script_pipeline_service.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.script_pipeline import script_pipeline_service as _script_pipeline_service

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _script_pipeline_service
globals().update(_script_pipeline_service.__dict__)
```

### Task 3: Update Documentation And Boundary Test

**Files:**

- Modify: `server/app/domains/script_pipeline/README.md`
- Modify: `server/tests/test_script_pipeline_domain_boundary.py`

- [ ] **Step 1: Update README**

Record `app.services.script_pipeline` as a facade targeting `app.domains.script_pipeline.script_pipeline_service`, and document that the service runtime remains router-free.

- [ ] **Step 2: Update boundary test**

Change the old service-layer assertion so it verifies the legacy service file contains no `pipeline_router` or `APIRouter(` while allowing the domain service facade import.

### Task 4: Verify And Commit

**Files:**

- All files listed above.

- [ ] **Step 1: Run the new boundary test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_script_pipeline_service_domain_facade.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run focused regression**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_script_pipeline_service_domain_facade.py server/tests/test_script_pipeline_domain_boundary.py server/tests/test_script_prompt_builder.py server/tests/test_script_pipeline.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Commit only touched files**

Use an isolated Git index if the working tree contains unrelated WIP. Commit message:

```text
refactor: move script pipeline service into domain
```

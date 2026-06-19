# Script Pipeline Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `/api/pipeline/*` into `app.domains.script_pipeline` while preserving legacy imports and route behavior.

**Architecture:** This is a facade-first router migration. The current `app.routers.pipeline` code becomes `app.domains.script_pipeline.pipeline_router`; the old module path becomes a `sys.modules` facade, and `app.main` imports the domain router directly.

**Tech Stack:** FastAPI, pytest, SQLAlchemy ORM models already in `app.db_models`, existing services in `app.services`.

---

## File Structure

- Create `server/app/domains/script_pipeline/__init__.py`: domain metadata.
- Create `server/app/domains/script_pipeline/README.md`: ownership, facade, and cleanup gates.
- Create `server/app/domains/script_pipeline/pipeline_router.py`: moved implementation from `server/app/routers/pipeline.py`.
- Modify `server/app/routers/pipeline.py`: compatibility facade pointing to the domain module.
- Modify `server/app/main.py`: import `pipeline_router` from the domain and include `pipeline_router.router`.
- Create `server/tests/test_script_pipeline_domain_boundary.py`: documentation, facade, main wiring, and import smoke tests.
- Create `server/tests/test_script_pipeline_router_facade.py`: legacy/domain module identity and router snapshot.
- Create `server/tests/test_script_pipeline_auth_parity.py`: FastAPI route table snapshot.

The move preserves route-local contracts such as `PipelineStartRequest`,
`PipelineRun` serialization, saved `Episode.storyboard_json` startup behavior,
`_run_all_layers`, and the separation from service-layer
`app.services.script_pipeline`.

### Task 1: Domain Spec, Plan, And Red Boundary Tests

**Files:**
- Create: `docs/superpowers/specs/2026-06-20-script-pipeline-domain-design.md`
- Create: `docs/superpowers/plans/2026-06-20-script-pipeline-domain-plan.md`
- Create: `server/tests/test_script_pipeline_domain_boundary.py`
- Create: `server/tests/test_script_pipeline_router_facade.py`
- Create: `server/tests/test_script_pipeline_auth_parity.py`

- [ ] **Step 1: Write the failing tests**

```python
EXPECTED_SCRIPT_PIPELINE_ROUTES = [
    ("POST", "/api/pipeline/start", "pipeline_start"),
    ("GET", "/api/pipeline/runs/{series_id}", "list_pipeline_runs"),
    ("GET", "/api/pipeline/runs/by-id/{run_id}", "get_pipeline_run_by_id"),
    ("GET", "/api/pipeline/runs/{series_id}/{run_id}", "get_pipeline_run"),
]
```

The tests expect `app.domains.script_pipeline.pipeline_router` to exist,
`app.routers.pipeline` to be a facade, and `app.main` to register endpoints from
`app.domains.script_pipeline.pipeline_router`.

- [ ] **Step 2: Run red tests**

Run from `server/`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_script_pipeline_domain_boundary.py tests/test_script_pipeline_router_facade.py tests/test_script_pipeline_auth_parity.py -q
```

Expected: FAIL because `app.domains.script_pipeline` does not exist and
`app.main` still wires `app.routers.pipeline`.

### Task 2: Move Router Into Domain And Preserve Legacy Facade

**Files:**
- Create: `server/app/domains/script_pipeline/__init__.py`
- Create: `server/app/domains/script_pipeline/README.md`
- Create: `server/app/domains/script_pipeline/pipeline_router.py`
- Modify: `server/app/routers/pipeline.py`

- [ ] **Step 1: Create domain metadata**

```python
"""Script pipeline domain package."""

DOMAIN_NAME = "script_pipeline"
PUBLIC_ROUTE_PREFIX = "/api/pipeline"
```

- [ ] **Step 2: Move implementation**

Copy the full current implementation from `server/app/routers/pipeline.py` to
`server/app/domains/script_pipeline/pipeline_router.py` without changing route
logic.

- [ ] **Step 3: Replace legacy router with facade**

```python
"""Compatibility facade for script pipeline routes.

The implementation now lives in app.domains.script_pipeline.pipeline_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.script_pipeline import pipeline_router as _pipeline_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _pipeline_router
globals().update(_pipeline_router.__dict__)
```

- [ ] **Step 4: Run facade tests**

Run from `server/`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_script_pipeline_domain_boundary.py tests/test_script_pipeline_router_facade.py -q
```

Expected: facade and domain tests pass except any explicit `app.main` direct
wiring assertion if Task 3 has not run yet.

- [ ] **Step 5: Commit domain move**

```powershell
git add -f docs/superpowers/specs/2026-06-20-script-pipeline-domain-design.md docs/superpowers/plans/2026-06-20-script-pipeline-domain-plan.md server/app/domains/script_pipeline/__init__.py server/app/domains/script_pipeline/README.md server/app/domains/script_pipeline/pipeline_router.py server/app/routers/pipeline.py server/tests/test_script_pipeline_domain_boundary.py server/tests/test_script_pipeline_router_facade.py server/tests/test_script_pipeline_auth_parity.py
git commit --only -m "refactor: move script pipeline router into domain" -- docs/superpowers/specs/2026-06-20-script-pipeline-domain-design.md docs/superpowers/plans/2026-06-20-script-pipeline-domain-plan.md server/app/domains/script_pipeline/__init__.py server/app/domains/script_pipeline/README.md server/app/domains/script_pipeline/pipeline_router.py server/app/routers/pipeline.py server/tests/test_script_pipeline_domain_boundary.py server/tests/test_script_pipeline_router_facade.py server/tests/test_script_pipeline_auth_parity.py
```

### Task 3: Wire FastAPI App Directly To Domain Router

**Files:**
- Modify: `server/app/main.py`
- Modify: `server/tests/test_script_pipeline_domain_boundary.py` if the direct
  wiring assertion was temporarily relaxed during Task 2.

- [ ] **Step 1: Update imports**

Add:

```python
from app.domains.script_pipeline import pipeline_router
```

Remove `pipeline` from:

```python
from app.routers import pixelle, seedance, ai_config, series, pipeline, audit, director, video_production, agency, ai_text_artifacts, storyboard_images
```

- [ ] **Step 2: Update include_router call**

Replace:

```python
app.include_router(pipeline.router)
```

with:

```python
app.include_router(pipeline_router.router)
```

- [ ] **Step 3: Run focused tests**

Run from `server/`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_script_pipeline_domain_boundary.py tests/test_script_pipeline_router_facade.py tests/test_script_pipeline_auth_parity.py tests/test_pipeline_saved_storyboard_compat.py tests/test_agency_console.py::test_agency_console_records_pipeline_stage_trace tests/test_series_style_lock_pipeline.py::test_style_lock_pipeline_run_uses_saved_storyboard -q
```

Expected: all selected tests pass, or any unrelated pre-existing WIP failure is
reported with exact failing test and reason.

- [ ] **Step 4: Commit direct wiring with isolated main.py staging**

Because `server/app/main.py` may contain unrelated local WIP, stage only the
script-pipeline import/include hunk via an isolated temporary index or
equivalent exact-path commit process. Do not stage unrelated `main.py` changes.

Commit message:

```powershell
git commit -m "refactor: wire script pipeline router from domain"
```

### Self-Review

- The spec covers ownership, non-ownership, compatibility, tests, and cleanup
  gates.
- The plan covers each file touched and includes exact commands.
- No task changes business behavior beyond router ownership and import wiring.

# Director Planning Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `/api/director/*` and route-local director helpers into `app.domains.director_planning` while preserving legacy monkeypatch compatibility.

**Architecture:** This is a facade-first router migration. The current `app.routers.director` code becomes `app.domains.director_planning.director_router`; the old module path becomes a `sys.modules` facade, and `app.main` imports the domain router directly.

**Tech Stack:** FastAPI, pytest, SQLAlchemy `Episode` and `Series`, existing AI generator, agency orchestrator, AI text artifact, and production plan services.

---

## File Structure

- Create `server/app/domains/director_planning/__init__.py`: domain metadata.
- Create `server/app/domains/director_planning/README.md`: owned routes, non-owned services, facade, and cleanup gates.
- Create `server/app/domains/director_planning/director_router.py`: moved implementation from `server/app/routers/director.py`.
- Modify `server/app/routers/director.py`: compatibility facade pointing at the domain module.
- Modify `server/app/main.py`: import and include `director_router`.
- Create `server/tests/test_director_planning_domain_boundary.py`: spec, README, facade, main wiring, and import smoke tests.
- Create `server/tests/test_director_planning_router_facade.py`: legacy/domain module identity and router snapshot.
- Create `server/tests/test_director_planning_auth_parity.py`: FastAPI route table snapshot.

The move preserves `DirectorScene`, `DirectorPlanRequest`,
`DirectorAutoPlanRequest`, `EpisodeProductionPlanRequest`, `EpisodePlanRequest`,
`ShotSegmentsRequest`, `generate_auto_storyboard`, `_normalize_auto_frames`,
`AITextArtifactService` usage, route-local timeout constants, and legacy
`app.routers.director` monkeypatch compatibility.

### Task 1: Write Spec, Plan, And Red Boundary Tests

**Files:**
- Create: `docs/superpowers/specs/2026-06-20-director-planning-domain-design.md`
- Create: `docs/superpowers/plans/2026-06-20-director-planning-domain-plan.md`
- Create: `server/tests/test_director_planning_domain_boundary.py`
- Create: `server/tests/test_director_planning_router_facade.py`
- Create: `server/tests/test_director_planning_auth_parity.py`

- [ ] **Step 1: Write failing tests**

```python
EXPECTED_DIRECTOR_PLANNING_ROUTES = [
    ("POST", "/api/director/auto-plan", "auto_plan_episode"),
    ("POST", "/api/director/episode-production-plan", "create_episode_production_plan_endpoint"),
    ("POST", "/api/director/episode-plan", "create_episode_plan_endpoint"),
    ("POST", "/api/director/shot-segments", "create_shot_segments_endpoint"),
    ("POST", "/api/director/plan", "build_plan"),
]
```

The tests expect `app.domains.director_planning.director_router` to exist,
`app.routers.director` to be a facade, and `app.main` to register endpoints
from `app.domains.director_planning.director_router`.

- [ ] **Step 2: Run red tests**

Run from `server/`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_director_planning_domain_boundary.py tests/test_director_planning_router_facade.py tests/test_director_planning_auth_parity.py -q
```

Expected: FAIL because `app.domains.director_planning` does not exist and
`app.main` still wires `app.routers.director`.

### Task 2: Move Router Into Domain And Keep Facade

**Files:**
- Create: `server/app/domains/director_planning/__init__.py`
- Create: `server/app/domains/director_planning/README.md`
- Create: `server/app/domains/director_planning/director_router.py`
- Modify: `server/app/routers/director.py`

- [ ] **Step 1: Create domain metadata**

```python
"""Director planning domain package."""

DOMAIN_NAME = "director_planning"
PUBLIC_ROUTE_PREFIX = "/api/director"
```

- [ ] **Step 2: Move implementation**

Copy the full current implementation from `server/app/routers/director.py` to
`server/app/domains/director_planning/director_router.py` without changing route
logic, storyboard generation behavior, artifact persistence, or helper names.

- [ ] **Step 3: Replace legacy module with facade**

```python
"""Compatibility facade for director planning routes.

The implementation now lives in app.domains.director_planning.director_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.director_planning import director_router as _director_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _director_router
globals().update(_director_router.__dict__)
```

### Task 3: Wire Main Directly To The Domain

**Files:**
- Modify: `server/app/main.py`

- [ ] **Step 1: Update main imports**

Add:

```python
from app.domains.director_planning import director_router
```

Remove `director` from the `from app.routers import ...` import list.

- [ ] **Step 2: Update main include**

Replace:

```python
app.include_router(director.router)
```

with:

```python
app.include_router(director_router.router)
```

### Task 4: Verify And Commit

**Files:**
- All files above.

- [ ] **Step 1: Run focused tests**

Run from `server/`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_director_planning_domain_boundary.py tests/test_director_planning_router_facade.py tests/test_director_planning_auth_parity.py tests/test_director_episode_plan.py tests/test_director_shot_segments.py tests/test_production_plan_service.py tests/test_series_style_lock_pipeline.py -q
```

Expected: all selected tests pass, or any unrelated pre-existing WIP failure is
reported with exact failing test and reason.

- [ ] **Step 2: Commit with isolated `main.py` staging**

Because `server/app/main.py` may contain unrelated local WIP, stage only the
director-planning import/include changes through an isolated temporary index.
Do not stage unrelated `main.py` changes.

Commit message:

```powershell
git commit -m "refactor: move director planning router into domain"
```

### Self-Review

- The spec covers ownership, non-ownership, compatibility, tests, and cleanup
  gates.
- The plan covers each file and exact verification commands.
- The migration preserves current director route behavior and monkeypatch paths.

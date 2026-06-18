<!-- /autoplan restore point: C:\Users\szm\.gstack\projects\dy_auto_new\codex-bailian-high-quality-video-pipeline-autoplan-restore-20260618-112516.md -->

# Server Business Modularization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved `ai_video_series` vertical slice so series routes, use cases, read models, ORM imports, production truth, tests, and compatibility facades move out of the flat server layout without changing public API behavior.

**Architecture:** Use PR-sized migrations. PR1 is behavior-neutral and creates the domain skeleton, facade register, boundary tests, auth characterization, and import smoke checks. Later PRs move the existing series router as a compatibility-preserving module alias, split domain responsibilities into focused modules, introduce ORM import boundaries with one SQLAlchemy `Base`, add a batched production status read model, and retire temporary facades only after tests prove all callers moved.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Pytest, existing `AITextArtifactService`, existing `ProductionAuditEvent`, existing `record_production_event`, existing `VideoProductionRun` and `ProductionJob` models.

---

## Scope And Coverage

This plan implements every approved scheme from the server modularization reviews for the `ai_video_series` vertical slice.

| Approved scheme | Implemented by |
|---|---|
| Domain skeleton first, no behavior movement in PR1 | Tasks 1-2 |
| Boundary tests and import smoke | Tasks 1-2 |
| Auth parity characterization for `/api/series/*` | Task 1 |
| Compatibility facade register with exit conditions | Tasks 2, 11 |
| Move series route-level business logic under `app.domains.ai_video_series` | Tasks 3-4 |
| Keep old public `app.routers.series` import paths working; migrate private monkeypatch paths before worker extraction | Tasks 3-4, 6 |
| Split router responsibilities into schemas, read models, artifact helpers, story planning, style lock, workers | Tasks 5-6 |
| Introduce `app.db.models.*` ORM boundary while preserving `app.db_models` | Tasks 7-8 |
| Keep one SQLAlchemy `Base` and no schema migration during model boundary work | Tasks 7-8 |
| Production truth/status matrix with batched evidence loading | Tasks 9-10 |
| Existing audit path reuse through `ProductionAuditEvent` and `record_production_event` | Task 9 |
| Facade cleanup with explicit removal gates | Task 11 |
| Repeat playbook for independent domains without silently merging them into this PR chain | Task 12 |

The independent device/content/account modularization work is not dropped. Task 12 requires child implementation plans before coding those domains because the writing-plans scope rule says independent subsystems need their own plans.

## CEO Review Corrections

The `/plan-ceo-review` pass on 2026-06-18 approved the direction with two corrections that must be preserved during implementation:

- Task 6 must not rely on private monkeypatch compatibility after moving worker function bodies out of `router.py`. The Task 3-4 module alias keeps the old router module identity only while the copied router still owns the function globals. Once `style_lock.py` and `story_planning.py` own those globals, tests that patch private helpers must patch the owning domain module directly.
- Task 8 must not physically move ORM class bodies in the same PR as shared `Base` extraction. `Series` is coupled to `Character`, `Scene`, `series_characters`, and `series_scenes`, and the production model family includes `ProductionJob`, `ProductionPlanVersion`, `ProductionScene`, `ProductionShot`, and `ProductionSegment`. This plan now establishes the safe import boundary and writes a required ORM graph extraction child plan instead of pretending the class move is mechanical.

## File Map

### New Files

- `server/app/domains/__init__.py`
  - Marks the server domain package.
- `server/app/domains/ai_video_series/__init__.py`
  - Public domain metadata and supported compatibility exports.
- `server/app/domains/ai_video_series/README.md`
  - Migration checklist, facade register, route ownership rules, test commands, and facade retirement gates.
- `server/app/domains/ai_video_series/router.py`
  - Owns `/api/series/*` route assembly after Task 4.
- `server/app/domains/ai_video_series/schemas.py`
  - Owns Pydantic request/response classes currently in `app.routers.series`.
- `server/app/domains/ai_video_series/read_models.py`
  - Owns series, episode, asset-scope, and active-run response builders.
- `server/app/domains/ai_video_series/artifacts.py`
  - Owns AI text artifact recording and story-plan artifact summaries.
- `server/app/domains/ai_video_series/story_planning.py`
  - Owns story-plan state, queueing, completed-payload detection, and worker functions.
- `server/app/domains/ai_video_series/style_lock.py`
  - Owns style-lock state, reference progress, reference generation, and style-lock worker functions.
- `server/app/domains/ai_video_series/status_read_model.py`
  - Owns batched episode production status/readiness evidence.
- `server/app/db/__init__.py`
  - Marks the database package.
- `server/app/db/base.py`
  - Owns `Base` and `_uuid` once the ORM boundary phase starts.
- `server/app/db/models/__init__.py`
  - Re-exports domain model modules.
- `server/app/db/models/ai_video_series.py`
  - Facade over `app.db_models` for this plan; physical ORM class-body extraction is gated behind the dedicated ORM graph child plan.
- `server/tests/test_ai_video_series_domain_boundary.py`
  - Architecture and docs boundary tests.
- `server/tests/test_ai_video_series_auth_parity.py`
  - Current `/api/series/*` route/dependency snapshot.
- `server/tests/test_ai_video_series_router_facade.py`
  - Router parity, legacy import identity, and monkeypatch compatibility tests.
- `server/tests/test_ai_video_series_read_models.py`
  - Domain read-model tests.
- `server/tests/test_ai_video_series_orm_boundary.py`
  - Single-Base and facade re-export tests.
- `server/tests/test_ai_video_series_status_read_model.py`
  - Production status matrix and batching tests.
- `docs/superpowers/plans/2026-06-18-ai-video-series-orm-graph-extraction.md`
  - Required child plan for physical ORM class-body extraction after graph/import ownership is proven.

### Modified Files

- `server/app/routers/series.py`
  - Becomes a compatibility alias to `app.domains.ai_video_series.router` after Task 4.
- `server/app/db_models.py`
  - Imports shared `Base`/`_uuid` from `app.db.base` while preserving legacy ORM class ownership in this plan.
- `server/tests/conftest.py`
  - Imports ORM classes from `app.db_models` must continue passing through the facade.
- `docs/superpowers/specs/2026-06-17-server-business-modularization-design.md`
  - Add implementation-plan link and facade status update.
- `TODOS.md`
  - Add child-plan queue entries for independent domains after the `ai_video_series` slice lands.

## Global Rules

- Do not combine route migration, ORM extraction, and production status work in one commit.
- PR1 may not move behavior.
- No public `/api/series/*` route path, HTTP method, auth dependency, or response shape may change unless a task explicitly updates the route snapshot and existing API tests.
- Any old import path under `app.routers.series.*` must keep working until Task 11 removes it with a test.
- Private monkeypatches against helpers inside `app.routers.series` must be migrated to the owning domain modules in Task 6 before worker bodies move.
- Use existing `ProductionAuditEvent` and `record_production_event`. Do not add audit tables.
- Use one SQLAlchemy `Base`. Do not create a second `DeclarativeBase`.

---

## Task 1: PR1 Boundary And Auth Characterization Tests

**Files:**

- Create `server/tests/test_ai_video_series_domain_boundary.py`
- Create `server/tests/test_ai_video_series_auth_parity.py`

**Success criteria:**

- The test suite captures the approved PR1 boundary before any behavior moves.
- The `/api/series/*` route table and auth dependencies are snapshotted.
- The app import smoke test proves `app.main.app` can be imported after skeleton creation.

- [ ] **Step 1: Write domain boundary tests**

Create `server/tests/test_ai_video_series_domain_boundary.py`:

```python
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_ai_video_series_domain_package_imports():
    import app.domains.ai_video_series as domain

    assert domain.DOMAIN_NAME == "ai_video_series"
    assert domain.PUBLIC_ROUTE_PREFIX == "/api/series"


def test_ai_video_series_readme_contains_facade_register_and_pr1_gates():
    readme = REPO_ROOT / "server" / "app" / "domains" / "ai_video_series" / "README.md"
    text = readme.read_text(encoding="utf-8")

    assert "Facade Register" in text
    assert "PR1 allowed" in text
    assert "PR1 not allowed" in text
    assert "app.routers.series" in text
    assert "Do not move route behavior in PR1" in text


def test_app_import_smoke():
    from app.main import app

    route_paths = {getattr(route, "path", "") for route in app.routes}
    assert "/api/series" in route_paths
```

- [ ] **Step 2: Write auth parity characterization tests**

Create `server/tests/test_ai_video_series_auth_parity.py`:

```python
from app.main import app


EXPECTED_SERIES_ROUTE_DEPENDENCIES = [
    ("POST", "/api/series/{series_id}/auto-generate", ("get_db", "verify_admin_token")),
    ("GET", "/api/series", ("get_db", "verify_admin_token")),
    ("GET", "/api/series/{series_id}/style-lock", ("get_db", "verify_admin_token")),
    ("GET", "/api/series/{series_id}/agency-console", ("get_db", "checker")),
    ("POST", "/api/series/style-lock/worker-step", ("get_db", "checker")),
    ("POST", "/api/series/story-plan/worker-step", ("get_db", "checker")),
    ("POST", "/api/series/{series_id}/style-lock", ("get_db", "verify_admin_token")),
    ("POST", "/api/series", ("get_db", "verify_admin_token")),
    ("GET", "/api/series/{series_id}", ("get_db", "verify_admin_token")),
    ("POST", "/api/series/{series_id}/ensure-episodes", ("get_db", "verify_admin_token")),
    ("POST", "/api/series/{series_id}/story-plan", ("get_db", "verify_admin_token")),
    ("PUT", "/api/series/{series_id}", ("get_db", "verify_admin_token")),
    ("DELETE", "/api/series/{series_id}", ("get_db", "verify_admin_token")),
    ("POST", "/api/series/{series_id}/characters/{character_id}", ("get_db", "verify_admin_token")),
    ("DELETE", "/api/series/{series_id}/characters/{character_id}", ("get_db", "verify_admin_token")),
    ("POST", "/api/series/{series_id}/scenes/{scene_id}", ("get_db", "verify_admin_token")),
    ("DELETE", "/api/series/{series_id}/scenes/{scene_id}", ("get_db", "verify_admin_token")),
    ("POST", "/api/series/{series_id}/episodes/{episode_id}/script", ("get_db", "verify_admin_token")),
    ("PUT", "/api/series/{series_id}/episodes/{episode_id}", ("get_db", "verify_admin_token")),
]


def _dependency_names(route) -> tuple[str, ...]:
    return tuple(
        getattr(dependency.call, "__name__", repr(dependency.call))
        for dependency in route.dependant.dependencies
    )


def _series_route_snapshot() -> list[tuple[str, str, tuple[str, ...]]]:
    snapshot = []
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/api/series"):
            continue
        for method in sorted(getattr(route, "methods", []) or []):
            snapshot.append((method, path, _dependency_names(route)))
    return snapshot


def test_series_route_auth_dependency_snapshot():
    assert _series_route_snapshot() == EXPECTED_SERIES_ROUTE_DEPENDENCIES
```

- [ ] **Step 3: Run tests and verify the expected PR1 red state**

Run from repository root:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_domain_boundary.py server/tests/test_ai_video_series_auth_parity.py -q
```

Expected:

- `test_ai_video_series_auth_parity.py` passes because it characterizes current behavior.
- `test_ai_video_series_domain_boundary.py::test_ai_video_series_domain_package_imports` fails with `ModuleNotFoundError: No module named 'app.domains'`.
- README test fails because the README does not exist yet.

- [ ] **Step 4: Commit only the tests**

```powershell
git add server/tests/test_ai_video_series_domain_boundary.py server/tests/test_ai_video_series_auth_parity.py
git commit -m "test: characterize ai video series domain boundary"
```

---

## Task 2: PR1 Domain Skeleton And Facade Register

**Files:**

- Create `server/app/domains/__init__.py`
- Create `server/app/domains/ai_video_series/__init__.py`
- Create `server/app/domains/ai_video_series/README.md`
- Modify `docs/superpowers/specs/2026-06-17-server-business-modularization-design.md`

**Success criteria:**

- PR1 remains behavior-neutral.
- Domain imports work.
- README contains facade register, PR gates, commands, and ownership rules.
- No route behavior, `db_models.py`, production behavior, or frontend UI changes.

- [ ] **Step 1: Create `server/app/domains/__init__.py`**

```python
"""Business-domain packages for the server application."""
```

- [ ] **Step 2: Create `server/app/domains/ai_video_series/__init__.py`**

```python
"""AI video series domain package.

This package will own the `/api/series/*` business flow once the migration
passes the compatibility gates documented in README.md.
"""

DOMAIN_NAME = "ai_video_series"
PUBLIC_ROUTE_PREFIX = "/api/series"

__all__ = ["DOMAIN_NAME", "PUBLIC_ROUTE_PREFIX"]
```

- [ ] **Step 3: Create `server/app/domains/ai_video_series/README.md`**

````markdown
# AI Video Series Domain

This domain will own the multi-episode AI video series business flow.

## PR1 allowed

- Create `server/app/domains/__init__.py`.
- Create `server/app/domains/ai_video_series/__init__.py`.
- Create this README.
- Add architecture, auth parity, and app import smoke tests.
- Document the facade register and migration checklist.

## PR1 not allowed

- Do not move route behavior in PR1.
- Do not split `server/app/db_models.py` in PR1.
- Do not change `/api/series/*` paths, methods, auth dependencies, or response shape.
- Do not change production run behavior.
- Do not change frontend UI.

## Ownership Rules

- New `/api/series/*` business logic belongs in `app.domains.ai_video_series`.
- `app.routers.series` is a compatibility entrypoint during migration.
- Domain rules and read models must not import FastAPI.
- Domain code may use existing services as adapters while migration is in progress.
- Use `ProductionAuditEvent` and `record_production_event` for production audit trails.

## Facade Register

| Facade | Target | Introduced | Exit condition |
|---|---|---|---|
| `app.routers.series` | `app.domains.ai_video_series.router` | PR2 | All imports and monkeypatches use domain paths or explicit compatibility exports. |
| `app.db_models` series ORM names | `app.db.models.ai_video_series` | PR4 | All production code imports series/video-series ORM names through `app.db.models.ai_video_series`; tests still prove legacy imports. |

## Migration Checklist

1. Add skeleton and tests without behavior changes.
2. Move the existing series route module into the domain package with legacy module identity preserved.
3. Split schemas, read models, artifact helpers, story planning, style lock, and worker logic into focused modules.
4. Add the ORM import boundary while preserving one SQLAlchemy `Base`.
5. Add the production status read model with batched evidence loading.
6. Remove facades only after compatibility tests prove no old callers remain.

## Test Commands

Run the PR1 skeleton and migration boundary checks:

Immediately after the PR1 skeleton, auth parity, domain import, README, and app import smoke checks should pass. The router-thinning and domain-router migration gates stay red until PR2 moves and thins the router.

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_auth_parity.py server/tests/test_ai_video_series_domain_boundary.py -q
```

Run the existing series route contract tests:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_series_api.py server/tests/test_series_style_lock_pipeline.py server/tests/test_style_lock_background_worker.py server/tests/test_series_auto_generate_assets.py -q
```

Run the production contract tests touched by this domain:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_start_flow_contract.py server/tests/test_video_production_readiness.py server/tests/test_video_production_observability_events.py -q
```
````

- [ ] **Step 4: Link the implementation plan from the spec**

Add this line under the `## Completion Definition` section in `docs/superpowers/specs/2026-06-17-server-business-modularization-design.md`:

```markdown
- Implementation plan: `docs/superpowers/plans/2026-06-18-server-business-modularization.md`.
```

- [ ] **Step 5: Run PR1 tests and smoke import**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_auth_parity.py server/tests/test_ai_video_series_domain_boundary.py -q
```

Expected after the PR1 skeleton:

- Auth parity, domain import, README, and app import smoke checks pass.
- `test_legacy_series_router_stays_thin_after_migration` remains red until Task 4/PR2 thins `app.routers.series`.
- `test_domain_router_is_not_the_long_term_business_logic_home` remains red until Task 4/PR2 creates `server/app/domains/ai_video_series/router.py`.

Task 4 is where the combined route/auth/domain boundary command is expected to pass.

- [ ] **Step 6: Run existing series API smoke tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_series_api.py::TestSeriesAPI::test_create_series server/tests/test_series_api.py::TestSeriesAPI::test_get_series_with_episodes server/tests/test_series_api.py::TestSeriesAPI::test_get_series_requires_admin_auth -q
```

Expected: PASS.

- [ ] **Step 7: Commit PR1 skeleton**

```powershell
git add server/app/domains/__init__.py server/app/domains/ai_video_series/__init__.py server/app/domains/ai_video_series/README.md docs/superpowers/specs/2026-06-17-server-business-modularization-design.md
git commit -m "chore: add ai video series domain skeleton"
```

---

## Task 3: PR2 Router Migration Tests

**Files:**

- Create `server/tests/test_ai_video_series_router_facade.py`

**Success criteria:**

- The new domain router has the same `/api/series/*` route snapshot.
- Legacy `app.routers.series` imports resolve to the same module object as `app.domains.ai_video_series.router`.
- Existing monkeypatch-heavy tests keep working because old and new module globals are identical.

- [ ] **Step 1: Write router facade tests**

Create `server/tests/test_ai_video_series_router_facade.py`:

```python
import importlib


EXPECTED_SERIES_ROUTER_SNAPSHOT = [
    ("POST", "/api/series/{series_id}/auto-generate"),
    ("GET", "/api/series"),
    ("GET", "/api/series/{series_id}/style-lock"),
    ("GET", "/api/series/{series_id}/agency-console"),
    ("POST", "/api/series/style-lock/worker-step"),
    ("POST", "/api/series/story-plan/worker-step"),
    ("POST", "/api/series/{series_id}/style-lock"),
    ("POST", "/api/series"),
    ("GET", "/api/series/{series_id}"),
    ("POST", "/api/series/{series_id}/ensure-episodes"),
    ("POST", "/api/series/{series_id}/story-plan"),
    ("PUT", "/api/series/{series_id}"),
    ("DELETE", "/api/series/{series_id}"),
    ("POST", "/api/series/{series_id}/characters/{character_id}"),
    ("DELETE", "/api/series/{series_id}/characters/{character_id}"),
    ("POST", "/api/series/{series_id}/scenes/{scene_id}"),
    ("DELETE", "/api/series/{series_id}/scenes/{scene_id}"),
    ("POST", "/api/series/{series_id}/episodes/{episode_id}/script"),
    ("PUT", "/api/series/{series_id}/episodes/{episode_id}"),
]


def _router_snapshot(router):
    snapshot = []
    for route in router.routes:
        path = getattr(route, "path", "")
        for method in sorted(getattr(route, "methods", []) or []):
            snapshot.append((method, path))
    return snapshot


def test_domain_router_matches_existing_series_route_snapshot():
    domain_router = importlib.import_module("app.domains.ai_video_series.router")

    assert _router_snapshot(domain_router.router) == EXPECTED_SERIES_ROUTER_SNAPSHOT


def test_legacy_series_router_module_is_domain_router_module():
    legacy_router = importlib.import_module("app.routers.series")
    domain_router = importlib.import_module("app.domains.ai_video_series.router")

    assert legacy_router is domain_router
    assert legacy_router.router is domain_router.router


def test_legacy_monkeypatch_paths_share_domain_globals():
    legacy_router = importlib.import_module("app.routers.series")
    domain_router = importlib.import_module("app.domains.ai_video_series.router")

    assert legacy_router._run_style_lock_job.__globals__ is domain_router.__dict__
    assert legacy_router._run_story_plan_worker_step.__globals__ is domain_router.__dict__
    assert legacy_router._fill_reference_assets.__globals__ is domain_router.__dict__
```

- [ ] **Step 2: Run test to verify it fails before migration**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_router_facade.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.domains.ai_video_series.router'`.

- [ ] **Step 3: Commit router migration tests**

```powershell
git add server/tests/test_ai_video_series_router_facade.py
git commit -m "test: lock series router compatibility migration"
```

---

## Task 4: PR2 Move Series Router Into Domain With Legacy Module Identity

**Files:**

- Create `server/app/domains/ai_video_series/router.py`
- Replace `server/app/routers/series.py`
- Carry the copied router's pre-existing direct dependency closure because the
  current working-tree router already imports these symbols:
  - `server/app/services/ai_text_artifact_service.py`
  - `server/app/services/storyboard_timing.py`
  - `server/app/services/production_run_service.py`
  - `server/app/services/production_errors.py`
  - `server/app/services/one_sentence_video_service.py`
  - `server/app/services/script_pipeline.py`
  - `server/app/models/script.py`
  - `server/app/services/reference_asset_service.py`
  - `server/app/services/anchor_service.py`
  - `server/app/models/asset_anchor.py`
  - `server/tests/test_anchor_service.py`
  - `server/tests/test_asset_anchor_models.py`
  - `server/app/db_models.py` for the `AITextArtifact` and
    `AITextArtifactConsumer` ORM names imported by `AITextArtifactService`
  - `server/app/data/agency_agents_zh/manifest.json`
  - `server/app/data/agency_agents_zh/creative/story-generator.md`
  - `server/app/services/agency_manifest.py`
  - `server/app/services/video_agency_team.py`
  - `server/tests/test_agency_manifest.py`
  - `server/tests/test_agency_orchestrator.py`
  - `server/tests/test_agency_console.py`
  - `server/tests/test_series_style_lock_pipeline.py`
  - `server/tests/test_agency_invocation_models.py`
  - `server/tests/test_image_production_migration.py`
  - `server/alembic/versions/8f9a0b1c2d3e_add_ai_video_core_tables.py`
  - `server/alembic/versions/9f1a2b3c4d5e_add_video_production_tables.py`
  - `server/alembic/versions/1b2c3d4e5f60_add_asset_anchor_tables.py`
  - `server/alembic/versions/2c3d4e5f6071_add_agency_creative_patches.py`
  - `server/alembic/versions/3d4e5f607182_expand_production_job_stage_length.py`
  - `server/alembic/versions/4e5f60718293_add_ai_text_artifacts.py`
  - `server/alembic/versions/5f60718293a4_add_source_comment_content_to_collected_users.py`

**Success criteria:**

- `app.main` still imports `series.router`.
- `import app.routers.series` returns the domain router module.
- The copied current router imports cleanly with its direct route dependency
  closure.
- The story-generator expert data and Alembic revisions required by the carried
  dependency closure are present in a clean commit checkout.
- Existing route tests and style-lock monkeypatch tests pass.

- [ ] **Step 1: Copy the current router module into the domain package**

Run this exact command from repository root:

```powershell
Copy-Item -LiteralPath server/app/routers/series.py -Destination server/app/domains/ai_video_series/router.py
```

- [ ] **Step 2: Replace `server/app/routers/series.py` with a module alias facade**

Replace the entire file with:

```python
"""Compatibility facade for the AI video series domain router.

Do not add business logic here. Importing `app.routers.series` must return the
same module object as `app.domains.ai_video_series.router` so legacy monkeypatch
paths keep changing the real domain module globals during migration.
"""

import sys

from app.domains.ai_video_series import router as _domain_router_module

sys.modules[__name__] = _domain_router_module
```

- [ ] **Step 3: Run router facade tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_router_facade.py -q
```

Expected: PASS.

- [ ] **Step 4: Run route/auth characterization tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_auth_parity.py server/tests/test_ai_video_series_domain_boundary.py -q
```

Expected: PASS.

The domain router size guard remains transitional in Task 4: the router is a
copied migration router under a generous cap so legacy monkeypatch globals stay
identical. Task 6 tightens this to route assembly after schemas, read models,
and worker logic are split out.

- [ ] **Step 5: Run existing series and worker compatibility tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_series_api.py server/tests/test_style_lock_background_worker.py server/tests/test_series_style_lock_pipeline.py -q
```

Expected: PASS.

- [ ] **Step 6: Run dependency-closure clean verification tests**

```powershell
$env:PYTHONPATH = "server"
.\server\.venv\Scripts\python.exe -c "import app.main; import app.domains.ai_video_series.router as d; import app.routers.series as l; assert l is d; print('clean-import-ok', len(d.router.routes))"
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_series_planning_service.py server/tests/test_agency_manifest.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_script_pipeline.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_start_flow_contract.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_one_sentence_video.py server/tests/test_one_sentence_video_run_types.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_reference_asset_service.py server/tests/test_anchor_service.py server/tests/test_asset_anchor_models.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_orchestrator.py server/tests/test_agency_console.py server/tests/test_series_style_lock_pipeline.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_invocation_models.py server/tests/test_image_production_migration.py -q
Push-Location server
$env:DATABASE_URL = "sqlite:///$((Join-Path $env:TEMP 'dy-task4-alembic-upgrade.db') -replace '\\','/')"
.\.venv\Scripts\python.exe -m alembic upgrade head
Pop-Location
```

Expected: PASS.

- [ ] **Step 7: Commit router migration**

```powershell
git add server/app/domains/ai_video_series/router.py server/app/routers/series.py server/tests/test_ai_video_series_domain_boundary.py docs/superpowers/plans/2026-06-18-server-business-modularization.md server/app/services/ai_text_artifact_service.py server/app/services/storyboard_timing.py server/app/services/production_run_service.py server/app/services/production_errors.py server/app/services/one_sentence_video_service.py server/app/services/script_pipeline.py server/app/models/script.py server/app/services/reference_asset_service.py server/app/services/anchor_service.py server/app/models/asset_anchor.py server/tests/test_anchor_service.py server/tests/test_asset_anchor_models.py server/app/db_models.py server/app/data/agency_agents_zh/manifest.json server/app/data/agency_agents_zh/creative/story-generator.md server/app/services/agency_manifest.py server/app/services/video_agency_team.py server/tests/test_agency_manifest.py server/tests/test_agency_orchestrator.py server/tests/test_agency_console.py server/tests/test_series_style_lock_pipeline.py server/tests/test_agency_invocation_models.py server/tests/test_image_production_migration.py server/alembic/versions/8f9a0b1c2d3e_add_ai_video_core_tables.py server/alembic/versions/9f1a2b3c4d5e_add_video_production_tables.py server/alembic/versions/1b2c3d4e5f60_add_asset_anchor_tables.py server/alembic/versions/2c3d4e5f6071_add_agency_creative_patches.py server/alembic/versions/3d4e5f607182_expand_production_job_stage_length.py server/alembic/versions/4e5f60718293_add_ai_text_artifacts.py server/alembic/versions/5f60718293a4_add_source_comment_content_to_collected_users.py
git commit -m "refactor: move series router into ai video series domain"
```

---

## Task 5: PR3 Split Schemas, Read Models, And Artifact Helpers

**Files:**

- Create `server/app/domains/ai_video_series/schemas.py`
- Create `server/app/domains/ai_video_series/read_models.py`
- Create `server/app/domains/ai_video_series/artifacts.py`
- Modify `server/app/domains/ai_video_series/router.py`
- Create `server/tests/test_ai_video_series_read_models.py`
- Modify `server/tests/test_ai_video_series_domain_boundary.py`

**Success criteria:**

- Pydantic classes no longer live in `router.py`.
- Response-shaping helpers no longer live in `router.py`.
- AI text artifact side effects no longer live in `router.py`.
- Old `app.routers.series.SeriesCreate`, `_series_dict`, and `_record_episode_update_text_artifacts` still resolve during migration.

- [ ] **Step 1: Add split-boundary tests**

Append to `server/tests/test_ai_video_series_domain_boundary.py`:

```python
def _line_count(path: str) -> int:
    return len((REPO_ROOT / path).read_text(encoding="utf-8").splitlines())


def test_domain_router_is_not_the_long_term_business_logic_home():
    assert _line_count("server/app/domains/ai_video_series/router.py") <= 900


def test_domain_non_router_modules_do_not_import_fastapi():
    module_paths = [
        "server/app/domains/ai_video_series/read_models.py",
        "server/app/domains/ai_video_series/artifacts.py",
    ]
    for module_path in module_paths:
        text = (REPO_ROOT / module_path).read_text(encoding="utf-8")
        assert "from fastapi" not in text
        assert "import fastapi" not in text
```

- [ ] **Step 2: Add read-model tests**

Create `server/tests/test_ai_video_series_read_models.py`:

```python
from app.db_models import Episode, Series, VideoProductionRun
from app.domains.ai_video_series.read_models import (
    active_video_runs_by_episode,
    episode_dict_with_video_run,
    series_dict,
)


def test_series_dict_preserves_public_shape(db):
    series = Series(
        title="Read Model Series",
        logline="A clear public shape.",
        genre="drama",
        total_episodes=2,
        target_duration=90,
        mode="step_by_step",
        pilot_first=True,
        status="draft",
    )
    db.add(series)
    db.commit()

    payload = series_dict(series)

    assert payload["id"] == series.id
    assert payload["title"] == "Read Model Series"
    assert payload["logline"] == "A clear public shape."
    assert payload["genre"] == "drama"
    assert payload["total_episodes"] == 2
    assert payload["target_duration"] == 90
    assert payload["mode"] == "step_by_step"
    assert payload["pilot_first"] is True
    assert payload["status"] == "draft"


def test_episode_payload_includes_active_video_run(db):
    series = Series(title="Episode Read Model", logline="Status", genre="drama")
    episode = Episode(series=series, episode_number=1, title="Pilot", status="pending")
    db.add_all([series, episode])
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="running",
        current_stage="image_batch_running",
        run_type="real_short_e2e",
    )
    db.add(run)
    db.commit()

    active_runs = active_video_runs_by_episode(db, series.id)
    payload = episode_dict_with_video_run(episode, active_runs[episode.id])

    assert payload["id"] == episode.id
    assert payload["episode_number"] == 1
    assert payload["video_run"]["id"] == run.id
    assert payload["video_run"]["status"] == "running"
    assert payload["video_run"]["current_stage"] == "image_batch_running"
    assert payload["video_run"]["run_type"] == "real_short_e2e"
```

- [ ] **Step 3: Run new tests to verify they fail before the split**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_read_models.py server/tests/test_ai_video_series_domain_boundary.py -q
```

Expected:

- Read-model import fails because `app.domains.ai_video_series.read_models` does not exist.
- Boundary test fails because the non-router modules do not exist.

- [ ] **Step 4: Move Pydantic classes into `schemas.py`**

Move these exact classes from `server/app/domains/ai_video_series/router.py` to `server/app/domains/ai_video_series/schemas.py` without changing field names or defaults:

```text
SeriesCreate
SeriesUpdate
EpisodeUpdate
StyleLockResponse
StyleLockWorkerStepRequest
StoryPlanWorkerStepRequest
EpisodeScriptGenerationRequest
```

Add these imports to `router.py`:

```python
from app.domains.ai_video_series.schemas import (
    EpisodeScriptGenerationRequest,
    EpisodeUpdate,
    SeriesCreate,
    SeriesUpdate,
    StoryPlanWorkerStepRequest,
    StyleLockResponse,
    StyleLockWorkerStepRequest,
)
```

Re-export the moved names at the bottom of `router.py`:

```python
__all__ = [
    "router",
    "SeriesCreate",
    "SeriesUpdate",
    "EpisodeUpdate",
    "StyleLockResponse",
    "StyleLockWorkerStepRequest",
    "StoryPlanWorkerStepRequest",
    "EpisodeScriptGenerationRequest",
]
```

- [ ] **Step 5: Move read-model helpers into `read_models.py`**

Move these exact helper functions from `router.py` to `read_models.py` without changing return keys:

```text
_series_char_dict -> series_char_dict
_series_scene_dict -> series_scene_dict
_series_dict -> series_dict
_episode_dict -> episode_dict
_episode_asset_usage_items -> episode_asset_usage_items
_episode_asset_scope_payload -> episode_asset_scope_payload
_active_video_runs_by_episode -> active_video_runs_by_episode
_episode_dict_with_video_run -> episode_dict_with_video_run
_character_reference_urls -> character_reference_urls
_scene_reference_urls -> scene_reference_urls
_reference_status -> reference_status
```

Add compatibility aliases in `router.py` after importing the public names:

```python
from app.domains.ai_video_series.read_models import (
    active_video_runs_by_episode,
    episode_asset_scope_payload,
    episode_dict_with_video_run,
    series_dict,
)

_active_video_runs_by_episode = active_video_runs_by_episode
_episode_asset_scope_payload = episode_asset_scope_payload
_episode_dict_with_video_run = episode_dict_with_video_run
_series_dict = series_dict
```

Update route handlers to call the public names:

```python
return {"ok": True, "series": [series_dict(s) for s in all_series]}
```

```python
active_runs = active_video_runs_by_episode(db, series_id)
payload = episode_dict_with_video_run(episode, active_runs.get(episode.id))
payload["asset_scope"] = episode_asset_scope_payload(db, episode)
```

- [ ] **Step 6: Move artifact helpers into `artifacts.py`**

Move these exact functions from `router.py` to `artifacts.py`:

```text
_actor_id -> actor_id
_storyboard_text_values -> storyboard_text_values
_record_episode_update_text_artifacts -> record_episode_update_text_artifacts
_story_plan_artifact_summary -> story_plan_artifact_summary
_completed_story_plan_payload -> completed_story_plan_payload
```

Add compatibility aliases in `router.py`:

```python
from app.domains.ai_video_series.artifacts import (
    actor_id,
    completed_story_plan_payload,
    record_episode_update_text_artifacts,
    story_plan_artifact_summary,
)

_actor_id = actor_id
_completed_story_plan_payload = completed_story_plan_payload
_record_episode_update_text_artifacts = record_episode_update_text_artifacts
_story_plan_artifact_summary = story_plan_artifact_summary
```

Update route handlers to call public names:

```python
record_episode_update_text_artifacts(db, ep, payload, user)
```

```python
completed_payload = completed_story_plan_payload(db, series)
```

- [ ] **Step 7: Run focused tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_read_models.py server/tests/test_ai_video_series_domain_boundary.py server/tests/test_ai_video_series_router_facade.py -q
```

Expected: PASS.

- [ ] **Step 8: Run existing series tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_series_api.py server/tests/test_series_style_lock_pipeline.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit read-model and artifact split**

```powershell
git add server/app/domains/ai_video_series/schemas.py server/app/domains/ai_video_series/read_models.py server/app/domains/ai_video_series/artifacts.py server/app/domains/ai_video_series/router.py server/tests/test_ai_video_series_domain_boundary.py server/tests/test_ai_video_series_read_models.py
git commit -m "refactor: split ai video series schemas and read models"
```

---

## Task 6: PR3 Split Style Lock And Story Planning Workers

**Files:**

- Create `server/app/domains/ai_video_series/style_lock.py`
- Create `server/app/domains/ai_video_series/story_planning.py`
- Modify `server/app/domains/ai_video_series/router.py`
- Modify `server/tests/test_ai_video_series_domain_boundary.py`

**Success criteria:**

- Style-lock and story-planning business logic no longer live in `router.py`.
- Public worker exports keep legacy imports working for `app.main`; private test monkeypatches target the owning domain modules.
- `router.py` becomes route assembly plus compatibility aliases.

- [ ] **Step 1: Inventory private monkeypatch paths before moving worker globals**

Run:

```powershell
rg "series_router\.(_generate_reference_image|generate_reference_url|claim_next_job|generate_series_story_plan)|app\.routers\.series\.AgencyOrchestrator|_run_style_lock_job|_run_story_plan_worker_step" server/tests/test_series_style_lock_pipeline.py server/tests/test_style_lock_background_worker.py server/tests/test_series_api.py
```

Expected: every private patch target is assigned to its owning module:

- `server/app/domains/ai_video_series/style_lock.py` owns reference generation, style-lock jobs, style-lock review, and style-lock queue claims.
- `server/app/domains/ai_video_series/story_planning.py` owns story-plan jobs, story-plan generation, and story-plan queue claims.
- `server/app/domains/ai_video_series/router.py` may keep public compatibility aliases for `app.main`, but tests must not depend on those aliases to patch moved function globals.

- [ ] **Step 2: Tighten router size and non-FastAPI boundary tests**

Replace `test_domain_router_is_not_the_long_term_business_logic_home` in `server/tests/test_ai_video_series_domain_boundary.py` with:

```python
def test_domain_router_is_route_assembly_not_business_logic_home():
    assert _line_count("server/app/domains/ai_video_series/router.py") <= 400
```

Replace the `module_paths` list in `test_domain_non_router_modules_do_not_import_fastapi` with:

```python
    module_paths = [
        "server/app/domains/ai_video_series/read_models.py",
        "server/app/domains/ai_video_series/artifacts.py",
        "server/app/domains/ai_video_series/story_planning.py",
        "server/app/domains/ai_video_series/style_lock.py",
    ]
```

- [ ] **Step 3: Run boundary test to verify it fails before the split**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_domain_boundary.py::test_domain_router_is_route_assembly_not_business_logic_home -q
```

Expected: FAIL because `router.py` is still too large.

- [ ] **Step 4: Move story planning functions into `story_planning.py`**

Move these exact functions and constants from `router.py` to `story_planning.py`:

```text
_story_planning_in_progress_error -> story_planning_in_progress_error
_active_story_plan_job -> active_story_plan_job
_set_story_planning_state -> set_story_planning_state
_enqueue_story_plan_job -> enqueue_story_plan_job
_run_story_plan_job -> run_story_plan_job
_run_story_plan_worker_step -> run_story_plan_worker_step
```

Import the public functions into `router.py`:

```python
from app.domains.ai_video_series.story_planning import (
    active_story_plan_job,
    enqueue_story_plan_job,
    run_story_plan_job,
    run_story_plan_worker_step,
    set_story_planning_state,
    story_planning_in_progress_error,
)
```

Add legacy aliases in `router.py`:

```python
_active_story_plan_job = active_story_plan_job
_enqueue_story_plan_job = enqueue_story_plan_job
_run_story_plan_job = run_story_plan_job
_run_story_plan_worker_step = run_story_plan_worker_step
_set_story_planning_state = set_story_planning_state
_story_planning_in_progress_error = story_planning_in_progress_error
```

Update route handlers to call public names:

```python
return await run_story_plan_worker_step(db, lease_id=body.lease_id, batch_size=body.batch_size)
```

- [ ] **Step 5: Move style-lock functions into `style_lock.py`**

Move these exact functions and constants from `router.py` to `style_lock.py`:

```text
_missing_agency_trace -> missing_agency_trace
_timeout_agency_trace -> timeout_agency_trace
_agency_trace_blocks -> agency_trace_blocks
_utc_now_iso -> utc_now_iso
_style_lock_status -> style_lock_status
_upsert_reference_progress_item -> upsert_reference_progress_item
_record_reference_slot_progress -> record_reference_slot_progress
_stored_reference_prompt_matches -> stored_reference_prompt_matches
_set_style_lock_state -> set_style_lock_state
_record_style_lock_series_bible_artifact -> record_style_lock_series_bible_artifact
_style_lock_in_progress_error -> style_lock_in_progress_error
_active_style_lock_job -> active_style_lock_job
_enqueue_style_lock_job -> enqueue_style_lock_job
_parse_json_with_key -> parse_json_with_key
_generate_reference_image -> generate_reference_image
_generate_reference_image_isolated -> generate_reference_image_isolated
_ensure_series_assets -> ensure_series_assets
_fill_reference_assets -> fill_reference_assets
_build_story_bible -> build_story_bible
_run_style_lock_job -> run_style_lock_job
_run_style_lock_worker_step -> run_style_lock_worker_step
```

Import the public functions into `router.py`:

```python
from app.domains.ai_video_series.style_lock import (
    active_style_lock_job,
    build_story_bible,
    fill_reference_assets,
    generate_reference_image,
    run_style_lock_job,
    run_style_lock_worker_step,
    set_style_lock_state,
    style_lock_in_progress_error,
)
```

Add legacy aliases in `router.py`:

```python
_active_style_lock_job = active_style_lock_job
_build_story_bible = build_story_bible
_fill_reference_assets = fill_reference_assets
_generate_reference_image = generate_reference_image
_run_style_lock_job = run_style_lock_job
_run_style_lock_worker_step = run_style_lock_worker_step
_set_style_lock_state = set_style_lock_state
_style_lock_in_progress_error = style_lock_in_progress_error
```

Update route handlers to call public names:

```python
return await run_style_lock_worker_step(db, lease_id=body.lease_id, batch_size=body.batch_size)
```

- [ ] **Step 6: Migrate private monkeypatch tests to owning modules**

Update existing tests so private helper patches target the module that owns the helper after the split:

```python
from app.domains.ai_video_series import style_lock
from app.domains.ai_video_series import story_planning
```

Use these replacements where applicable:

```text
series_router._generate_reference_image -> style_lock.generate_reference_image
series_router.generate_reference_url -> style_lock.generate_reference_url
series_router.claim_next_job for style-lock worker tests -> style_lock.claim_next_job
series_router.claim_next_job for story-plan worker tests -> story_planning.claim_next_job
series_router.generate_series_story_plan -> story_planning.generate_series_story_plan
app.routers.series.AgencyOrchestrator.run_style_lock_review -> app.domains.ai_video_series.style_lock.AgencyOrchestrator.run_style_lock_review
```

Do not add a router-level patch synchronization layer. It creates hidden coupling and makes later facade removal harder.

- [ ] **Step 7: Run existing style-lock tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_series_style_lock_pipeline.py server/tests/test_style_lock_background_worker.py -q
```

Expected: PASS.

- [ ] **Step 8: Run boundary and router facade tests**

Append to `server/tests/test_ai_video_series_domain_boundary.py`:

```python
def test_worker_modules_expose_patchable_dependency_points():
    from app.domains.ai_video_series import story_planning, style_lock

    assert hasattr(style_lock, "claim_next_job")
    assert hasattr(style_lock, "generate_reference_url")
    assert hasattr(style_lock, "AgencyOrchestrator")
    assert hasattr(story_planning, "claim_next_job")
    assert hasattr(story_planning, "generate_series_story_plan")
```

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_domain_boundary.py server/tests/test_ai_video_series_router_facade.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit worker split**

```powershell
git add server/app/domains/ai_video_series/style_lock.py server/app/domains/ai_video_series/story_planning.py server/app/domains/ai_video_series/router.py server/tests/test_ai_video_series_domain_boundary.py server/tests/test_series_style_lock_pipeline.py server/tests/test_style_lock_background_worker.py
git commit -m "refactor: split ai video series workers from router"
```

---

## Task 7: PR4 ORM Boundary Facade

**Files:**

- Create `server/app/db/__init__.py`
- Create `server/app/db/models/__init__.py`
- Create `server/app/db/models/ai_video_series.py`
- Create `server/tests/test_ai_video_series_orm_boundary.py`

**Success criteria:**

- New code can import series/video-series ORM names from `app.db.models.ai_video_series`.
- Existing imports from `app.db_models` keep working.
- All names share the same class objects and metadata.

- [ ] **Step 1: Write ORM boundary tests**

Create `server/tests/test_ai_video_series_orm_boundary.py`:

```python
from app.db_models import (
    AITextArtifact,
    AITextArtifactConsumer,
    Base,
    Episode,
    EpisodeScript,
    ProductionAuditEvent,
    ProductionEpisode,
    ProductionJob,
    ProductionPlan,
    ProductionPlanVersion,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    Series,
    VideoProductionRun,
    series_characters,
    series_scenes,
)


def test_ai_video_series_model_facade_reexports_legacy_classes():
    from app.db.models import ai_video_series as models

    assert models.Base is Base
    assert models.Series is Series
    assert models.Episode is Episode
    assert models.ProductionPlan is ProductionPlan
    assert models.ProductionEpisode is ProductionEpisode
    assert models.VideoProductionRun is VideoProductionRun
    assert models.AITextArtifact is AITextArtifact
    assert models.AITextArtifactConsumer is AITextArtifactConsumer
    assert models.ProductionAuditEvent is ProductionAuditEvent
    assert models.EpisodeScript is EpisodeScript
    assert models.ProductionJob is ProductionJob
    assert models.ProductionPlanVersion is ProductionPlanVersion
    assert models.ProductionScene is ProductionScene
    assert models.ProductionShot is ProductionShot
    assert models.ProductionSegment is ProductionSegment
    assert models.series_characters is series_characters
    assert models.series_scenes is series_scenes


def test_ai_video_series_model_facade_uses_one_metadata_object():
    from app.db.models import ai_video_series as models

    assert models.Series.metadata is Base.metadata
    assert models.Episode.metadata is Base.metadata
    assert models.VideoProductionRun.metadata is Base.metadata
    assert "series" in Base.metadata.tables
    assert "episodes" in Base.metadata.tables
    assert "video_production_runs" in Base.metadata.tables
```

- [ ] **Step 2: Run test to verify it fails before facade module exists**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_orm_boundary.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.db'`.

- [ ] **Step 3: Create database package files**

Create `server/app/db/__init__.py`:

```python
"""Database package boundaries."""
```

Create `server/app/db/models/__init__.py`:

```python
"""ORM model import boundaries."""
```

Create `server/app/db/models/ai_video_series.py`:

```python
"""AI video series ORM import boundary.

This module starts as a compatibility facade over `app.db_models`. A dedicated
ORM graph extraction child plan may later move definitions while preserving
these public names.
"""

from app.db_models import (
    AITextArtifact,
    AITextArtifactConsumer,
    Base,
    Episode,
    EpisodeScript,
    ProductionAuditEvent,
    ProductionEpisode,
    ProductionJob,
    ProductionPlan,
    ProductionPlanVersion,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    Series,
    VideoProductionRun,
    series_characters,
    series_scenes,
)

__all__ = [
    "Base",
    "Series",
    "Episode",
    "ProductionPlan",
    "ProductionEpisode",
    "VideoProductionRun",
    "AITextArtifact",
    "AITextArtifactConsumer",
    "ProductionAuditEvent",
    "EpisodeScript",
    "ProductionJob",
    "ProductionPlanVersion",
    "ProductionScene",
    "ProductionShot",
    "ProductionSegment",
    "series_characters",
    "series_scenes",
]
```

- [ ] **Step 4: Update new domain modules to import ORM names through the boundary**

In `server/app/domains/ai_video_series/read_models.py`, `artifacts.py`, `story_planning.py`, `style_lock.py`, and `status_read_model.py`, replace series/video-series model imports from `app.db_models` with:

```python
from app.db.models.ai_video_series import (
    AITextArtifact,
    Episode,
    ProductionAuditEvent,
    ProductionJob,
    ProductionPlan,
    Series,
    VideoProductionRun,
)
```

If a module needs a name not exported by `ai_video_series.py`, either add that exact name to the facade with a test or leave the import from `app.db_models` and add a comment:

```python
# Cross-domain model: keep on app.db_models until its owning domain exists.
```

- [ ] **Step 5: Run ORM boundary tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_orm_boundary.py -q
```

Expected: PASS.

- [ ] **Step 6: Run domain tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_domain_boundary.py server/tests/test_ai_video_series_read_models.py server/tests/test_ai_video_series_router_facade.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit ORM boundary facade**

```powershell
git add server/app/db/__init__.py server/app/db/models/__init__.py server/app/db/models/ai_video_series.py server/tests/test_ai_video_series_orm_boundary.py server/app/domains/ai_video_series
git commit -m "refactor: add ai video series orm boundary facade"
```

---

## Task 8: PR4 Extract Shared ORM Base And Lock ORM Graph Gate

**Files:**

- Create `server/app/db/base.py`
- Modify `server/app/db_models.py`
- Modify `server/app/db/models/ai_video_series.py`
- Modify `server/tests/test_ai_video_series_orm_boundary.py`
- Create `docs/superpowers/plans/2026-06-18-ai-video-series-orm-graph-extraction.md`
- Modify `TODOS.md`

**Success criteria:**

- `Base` and `_uuid` live in `app.db.base`.
- `app.db.models.ai_video_series` exports the full series/video-production ORM surface needed by new domain modules.
- `app.db_models` still owns and re-exports every legacy ORM class body used by `server/tests/conftest.py`.
- No ORM class body is moved in this task.
- The physical ORM extraction is represented by a required child plan that maps `Series`/`Character`/`Scene` relationship ownership before any class move.
- No Alembic migration is added in this task.

- [ ] **Step 1: Add Base extraction tests**

Append to `server/tests/test_ai_video_series_orm_boundary.py`:

```python
def test_base_is_owned_by_app_db_base():
    from app.db.base import Base as SharedBase
    from app.db_models import Base as LegacyBase

    assert SharedBase is LegacyBase


def test_db_models_reexports_ai_video_series_facade_names():
    import app.db_models as legacy
    from app.db.models import ai_video_series as models

    for name in models.__all__:
        assert getattr(legacy, name) is getattr(models, name)


def test_ai_video_series_model_boundary_imports_in_clean_process():
    import subprocess
    import sys

    code = (
        "from app.db.models.ai_video_series import ProductionJob, Series; "
        "import app.db_models as legacy; "
        "assert legacy.Series is Series; "
        "assert legacy.ProductionJob is ProductionJob"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd="server",
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
```

- [ ] **Step 2: Run test to verify it fails before `app.db.base` exists**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_orm_boundary.py::test_base_is_owned_by_app_db_base -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.db.base'`.

- [ ] **Step 3: Create `server/app/db/base.py`**

```python
"""Shared SQLAlchemy declarative base."""

import uuid

from sqlalchemy.orm import DeclarativeBase


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 4: Modify `server/app/db_models.py` to import shared Base**

At the top of `server/app/db_models.py`, remove:

```python
import uuid
```

Remove:

```python
from sqlalchemy.orm import DeclarativeBase, relationship
```

Add:

```python
from sqlalchemy.orm import relationship

from app.db.base import Base, _uuid
```

Remove the old local definitions:

```python
def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 5: Keep `ai_video_series.py` as a full facade**

Confirm `server/app/db/models/ai_video_series.py` imports and exports these names from `app.db_models`:

```text
Base
series_characters
series_scenes
Series
Episode
ProductionPlan
ProductionPlanVersion
ProductionEpisode
ProductionScene
ProductionShot
ProductionSegment
ProductionJob
AITextArtifact
AITextArtifactConsumer
ProductionAuditEvent
EpisodeScript
VideoProductionRun
```

Do not move the class definitions in this PR. The facade is the boundary; physical ownership comes after the ORM graph child plan.

- [ ] **Step 6: Run full model import tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_orm_boundary.py server/tests/test_database.py server/tests/test_models.py server/tests/test_series_production_models.py -q
```

Expected: PASS.

- [ ] **Step 7: Create required ORM graph extraction child plan**

Create `docs/superpowers/plans/2026-06-18-ai-video-series-orm-graph-extraction.md`:

```markdown
# AI Video Series ORM Graph Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Physically move `ai_video_series` ORM class bodies only after the relationship graph, import order, Alembic model loading, and legacy facade behavior are proven with tests.

**Architecture:** Start from the shared `app.db.base.Base` and `app.db.models.ai_video_series` facade created by the server modularization plan. Map ownership for `Series`, `Episode`, `ProductionPlan`, `ProductionPlanVersion`, `ProductionEpisode`, `ProductionScene`, `ProductionShot`, `ProductionSegment`, `ProductionJob`, `AITextArtifact`, `AITextArtifactConsumer`, `ProductionAuditEvent`, `EpisodeScript`, `VideoProductionRun`, `series_characters`, and `series_scenes`. Do not move class bodies until the plan accounts for `Character.series_list`, `Scene.series_list`, Alembic imports, subprocess import order, and existing test fixtures.

**Tech Stack:** SQLAlchemy ORM, Alembic, Pytest, existing `app.db_models` compatibility facade.

---

## First Tasks

- [ ] Draw the ORM dependency graph for `Series`, `Character`, `Scene`, association tables, and production models.
- [ ] Decide whether `Character` and `Scene` move with `Series` or stay cross-domain with explicit late-bound relationships.
- [ ] Add subprocess import tests for `app.db_models`, `app.db.models.ai_video_series`, and Alembic metadata loading in both import orders.
- [ ] Move ORM class bodies only in dependency-safe batches after failing tests exist.
- [ ] Keep `app.db_models` re-exports until all legacy imports are retired by cleanup gates.
- [ ] Run model, migration-head, series API, and production start-flow tests after each batch.
```

- [ ] **Step 8: Update root TODOs with the ORM graph gate**

Under `## Server Business Modularization Deferred Scope`, add:

```markdown
- AI video series ORM graph extraction. Required child plan: `docs/superpowers/plans/2026-06-18-ai-video-series-orm-graph-extraction.md`; do not move ORM class bodies until the relationship/import graph is tested.
```

- [ ] **Step 9: Run full series and production start contract tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_series_api.py server/tests/test_video_production_start_flow_contract.py server/tests/test_video_production_readiness.py -q
```

Expected: PASS.

- [ ] **Step 10: Commit Base extraction and ORM graph gate**

```powershell
git add server/app/db/base.py server/app/db_models.py server/app/db/models/ai_video_series.py server/tests/test_ai_video_series_orm_boundary.py docs/superpowers/plans/2026-06-18-ai-video-series-orm-graph-extraction.md TODOS.md
git commit -m "refactor: extract shared orm base for ai video series boundary"
```

---

## Task 9: PR5 Episode Production Status Read Model

**Files:**

- Create `server/app/domains/ai_video_series/status_read_model.py`
- Create `server/tests/test_ai_video_series_status_read_model.py`
- Modify `server/app/domains/ai_video_series/read_models.py`
- Modify `server/app/domains/ai_video_series/router.py`

**Success criteria:**

- Each episode detail payload exposes a named production status derived from artifacts, runs, jobs, and audit evidence.
- A run marked `running` without active evidence is not shown as confidently producing.
- Script/storyboard artifact presence is visible in the episode payload.
- Status evidence loads in batches per series.

- [ ] **Step 1: Write status matrix tests**

Create `server/tests/test_ai_video_series_status_read_model.py`:

```python
from app.db.models.ai_video_series import AITextArtifact, Episode, ProductionJob, Series, VideoProductionRun
from app.domains.ai_video_series.status_read_model import build_episode_status_matrix


def _series_with_episode(db):
    series = Series(title="Status Matrix", logline="Truth", genre="drama", total_episodes=1)
    episode = Episode(series=series, episode_number=1, title="Pilot", status="pending")
    db.add_all([series, episode])
    db.flush()
    return series, episode


def test_episode_without_artifacts_or_run_is_not_started(db):
    series, episode = _series_with_episode(db)
    db.commit()

    matrix = build_episode_status_matrix(db, series.id)

    assert matrix[episode.id]["production_status"] == "not_started"
    assert matrix[episode.id]["has_episode_script"] is False
    assert matrix[episode.id]["has_storyboard"] is False
    assert matrix[episode.id]["active_run_id"] is None
    assert matrix[episode.id]["blocking_code"] == "NO_ACTIVE_RUN"


def test_episode_with_script_and_storyboard_is_ready_for_production(db):
    series, episode = _series_with_episode(db)
    db.add_all([
        AITextArtifact(
            series_id=series.id,
            episode_id=episode.id,
            target_type="episode",
            target_id=episode.id,
            artifact_type="episode_script",
            version=1,
            status="approved",
            source_type="ai",
            content_json={"script": "approved"},
        ),
        AITextArtifact(
            series_id=series.id,
            episode_id=episode.id,
            target_type="episode",
            target_id=episode.id,
            artifact_type="storyboard",
            version=1,
            status="approved",
            source_type="ai",
            content_json={"frames": [{"frame_id": "f1"}]},
        ),
    ])
    db.commit()

    matrix = build_episode_status_matrix(db, series.id)

    assert matrix[episode.id]["production_status"] == "ready_for_production"
    assert matrix[episode.id]["has_episode_script"] is True
    assert matrix[episode.id]["has_storyboard"] is True
    assert matrix[episode.id]["blocking_code"] is None


def test_running_run_without_active_job_is_blocked_with_named_code(db):
    series, episode = _series_with_episode(db)
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="running",
        current_stage="image_batch_running",
        run_type="real_short_e2e",
    )
    db.add(run)
    db.commit()

    matrix = build_episode_status_matrix(db, series.id)

    assert matrix[episode.id]["production_status"] == "blocked"
    assert matrix[episode.id]["active_run_id"] == run.id
    assert matrix[episode.id]["blocking_code"] == "RUNNING_WITHOUT_ACTIVE_JOB"


def test_running_run_with_active_job_is_producing(db):
    series, episode = _series_with_episode(db)
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="running",
        current_stage="image_batch_running",
        run_type="real_short_e2e",
    )
    db.add(run)
    db.flush()
    db.add(ProductionJob(
        run_id=run.id,
        target_type="episode",
        target_id=episode.id,
        stage="image_generation",
        status="running",
    ))
    db.commit()

    matrix = build_episode_status_matrix(db, series.id)

    assert matrix[episode.id]["production_status"] == "producing"
    assert matrix[episode.id]["active_run_id"] == run.id
    assert matrix[episode.id]["active_job_count"] == 1
    assert matrix[episode.id]["blocking_code"] is None


def test_completed_run_is_completed(db):
    series, episode = _series_with_episode(db)
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="completed",
        current_stage="completed",
        run_type="real_short_e2e",
    )
    db.add(run)
    db.commit()

    matrix = build_episode_status_matrix(db, series.id)

    assert matrix[episode.id]["production_status"] == "completed"
    assert matrix[episode.id]["active_run_id"] == run.id
    assert matrix[episode.id]["blocking_code"] is None
```

- [ ] **Step 2: Run tests to verify status module is missing**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_status_read_model.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.domains.ai_video_series.status_read_model'`.

- [ ] **Step 3: Implement `status_read_model.py`**

Create `server/app/domains/ai_video_series/status_read_model.py`:

```python
from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from app.db.models.ai_video_series import AITextArtifact, Episode, ProductionJob, VideoProductionRun


ACTIVE_JOB_STATUSES = {"queued", "leased", "running", "retry_wait"}
ACTIVE_RUN_STATUSES = {
    "running",
    "reference_generation_running",
    "image_batch_running",
    "video_batch_running",
    "composing",
    "final_review_pending",
}


def build_episode_status_matrix(db: Session, series_id: str) -> dict[str, dict]:
    episodes = (
        db.query(Episode)
        .filter(Episode.series_id == series_id)
        .order_by(Episode.episode_number.asc())
        .all()
    )
    episode_ids = [episode.id for episode in episodes]
    runs_by_episode = _latest_runs_by_episode(db, episode_ids)
    active_jobs_by_run = _active_jobs_by_run(db, [run.id for run in runs_by_episode.values()])
    artifact_types_by_episode = _artifact_types_by_episode(db, episode_ids)

    matrix = {}
    for episode in episodes:
        run = runs_by_episode.get(episode.id)
        artifact_types = artifact_types_by_episode.get(episode.id, set())
        active_jobs = active_jobs_by_run.get(run.id, []) if run else []
        matrix[episode.id] = _episode_status_payload(episode, run, active_jobs, artifact_types)
    return matrix


def _latest_runs_by_episode(db: Session, episode_ids: list[str]) -> dict[str, VideoProductionRun]:
    if not episode_ids:
        return {}
    runs = (
        db.query(VideoProductionRun)
        .filter(VideoProductionRun.episode_id.in_(episode_ids))
        .order_by(VideoProductionRun.created_at.desc())
        .all()
    )
    latest = {}
    for run in runs:
        latest.setdefault(run.episode_id, run)
    return latest


def _active_jobs_by_run(db: Session, run_ids: list[str]) -> dict[str, list[ProductionJob]]:
    if not run_ids:
        return {}
    rows = (
        db.query(ProductionJob)
        .filter(ProductionJob.run_id.in_(run_ids))
        .filter(ProductionJob.status.in_(ACTIVE_JOB_STATUSES))
        .all()
    )
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.run_id].append(row)
    return dict(grouped)


def _artifact_types_by_episode(db: Session, episode_ids: list[str]) -> dict[str, set[str]]:
    if not episode_ids:
        return {}
    rows = (
        db.query(AITextArtifact.episode_id, AITextArtifact.artifact_type)
        .filter(AITextArtifact.episode_id.in_(episode_ids))
        .filter(AITextArtifact.status == "approved")
        .filter(AITextArtifact.artifact_type.in_(("episode_script", "storyboard")))
        .all()
    )
    grouped = defaultdict(set)
    for episode_id, artifact_type in rows:
        grouped[episode_id].add(artifact_type)
    return dict(grouped)


def _episode_status_payload(episode: Episode, run, active_jobs: list[ProductionJob], artifact_types: set[str]) -> dict:
    has_script = "episode_script" in artifact_types or bool(episode.script_json)
    has_storyboard = "storyboard" in artifact_types or bool(episode.storyboard_json)
    payload = {
        "episode_id": episode.id,
        "episode_number": episode.episode_number,
        "has_episode_script": has_script,
        "has_storyboard": has_storyboard,
        "active_run_id": run.id if run else None,
        "active_job_count": len(active_jobs),
        "blocking_code": None,
    }
    if run and run.status == "completed":
        payload["production_status"] = "completed"
    elif run and run.status in ACTIVE_RUN_STATUSES and active_jobs:
        payload["production_status"] = "producing"
    elif run and run.status in ACTIVE_RUN_STATUSES and not active_jobs:
        payload["production_status"] = "blocked"
        payload["blocking_code"] = "RUNNING_WITHOUT_ACTIVE_JOB"
    elif has_script and has_storyboard:
        payload["production_status"] = "ready_for_production"
    else:
        payload["production_status"] = "not_started"
        payload["blocking_code"] = "NO_ACTIVE_RUN"
    return payload
```

- [ ] **Step 4: Attach status matrix to episode payloads**

In `server/app/domains/ai_video_series/router.py`, import:

```python
from app.domains.ai_video_series.status_read_model import build_episode_status_matrix
```

In the `get_series` route, before iterating episodes, add:

```python
status_matrix = build_episode_status_matrix(db, series_id)
```

Inside the episode loop, after `asset_scope` is added, add:

```python
payload["production_status"] = status_matrix.get(episode.id, {})
```

- [ ] **Step 5: Run status tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_status_read_model.py -q
```

Expected: PASS.

- [ ] **Step 6: Run existing series detail tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_series_api.py::TestSeriesAPI::test_get_series_with_episodes server/tests/test_video_production_start_flow_contract.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit status read model**

```powershell
git add server/app/domains/ai_video_series/status_read_model.py server/app/domains/ai_video_series/router.py server/tests/test_ai_video_series_status_read_model.py
git commit -m "feat: add ai video series production status read model"
```

---

## Task 10: PR5 Batch Loading Performance Guard

**Files:**

- Modify `server/tests/test_ai_video_series_status_read_model.py`
- Modify `server/app/domains/ai_video_series/status_read_model.py`

**Success criteria:**

- Building the status matrix for 10 episodes does not issue per-episode queries.
- The implementation remains batched by episodes, runs, jobs, and artifacts.

- [ ] **Step 1: Add query-count regression test**

Append to `server/tests/test_ai_video_series_status_read_model.py`:

```python
from sqlalchemy import event


def test_status_matrix_loads_evidence_in_batches(db):
    series = Series(title="Batch Status", logline="Batch", genre="drama", total_episodes=10)
    db.add(series)
    db.flush()
    for index in range(10):
        episode = Episode(series_id=series.id, episode_number=index + 1, title=f"Episode {index + 1}")
        db.add(episode)
        db.flush()
        run = VideoProductionRun(
            series_id=series.id,
            episode_id=episode.id,
            status="running",
            current_stage="image_batch_running",
            run_type="real_short_e2e",
        )
        db.add(run)
        db.flush()
        db.add(ProductionJob(
            run_id=run.id,
            target_type="episode",
            target_id=episode.id,
            stage="image_generation",
            status="running",
        ))
    db.commit()

    statements = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(db.bind, "before_cursor_execute", before_cursor_execute)
    try:
        matrix = build_episode_status_matrix(db, series.id)
    finally:
        event.remove(db.bind, "before_cursor_execute", before_cursor_execute)

    assert len(matrix) == 10
    assert len(statements) <= 4
```

- [ ] **Step 2: Run performance guard**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_status_read_model.py::test_status_matrix_loads_evidence_in_batches -q
```

Expected: PASS. If it fails, remove per-episode DB lookups from `build_episode_status_matrix`.

- [ ] **Step 3: Run status and readiness tests together**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_status_read_model.py server/tests/test_video_production_readiness.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit batching guard**

```powershell
git add server/tests/test_ai_video_series_status_read_model.py server/app/domains/ai_video_series/status_read_model.py
git commit -m "test: guard ai video series status batching"
```

---

## Task 11: PR6 Compatibility Facade Cleanup Gates

**Files:**

- Modify `server/app/domains/ai_video_series/README.md`
- Modify `server/tests/test_ai_video_series_router_facade.py`
- Modify `server/tests/test_ai_video_series_orm_boundary.py`
- Modify `TODOS.md`

**Success criteria:**

- Facades have explicit removal gates.
- Legacy paths remain tested until intentionally removed.
- Cleanup does not happen in the same PR that introduces the replacement.

- [ ] **Step 1: Add compatibility cleanup section to README**

Append to `server/app/domains/ai_video_series/README.md`:

```markdown
## Compatibility Cleanup Gates

Do not remove `app.routers.series` until all of these are true:

- `rg "app\.routers\.series|from app\.routers import series" server/app server/tests` returns only this README and compatibility tests.
- `server/tests/test_ai_video_series_router_facade.py` has been replaced with tests for the new public import path.
- `app.main` imports worker functions from `app.domains.ai_video_series`.
- Release notes mention the import-path migration.

Do not remove `app.db_models` re-exports until all of these are true:

- `rg "from app\.db_models import .*Series|from app\.db_models import .*Episode|from app\.db_models import .*VideoProductionRun" server/app server/tests` returns only compatibility tests.
- `server/tests/conftest.py` imports series/video-series ORM names through `app.db.models.ai_video_series` or an explicit shared test fixture module.
- Alembic environment imports all model modules through `app.db.models`.
```

- [ ] **Step 2: Add facade register tests**

Append to `server/tests/test_ai_video_series_router_facade.py`:

```python
from pathlib import Path


def test_router_facade_cleanup_gates_are_documented():
    readme = Path("server/app/domains/ai_video_series/README.md").read_text(encoding="utf-8")

    assert "Compatibility Cleanup Gates" in readme
    assert "Do not remove `app.routers.series` until all of these are true" in readme
```

Append to `server/tests/test_ai_video_series_orm_boundary.py`:

```python
from pathlib import Path


def test_db_models_facade_cleanup_gates_are_documented():
    readme = Path("server/app/domains/ai_video_series/README.md").read_text(encoding="utf-8")

    assert "Do not remove `app.db_models` re-exports until all of these are true" in readme
```

- [ ] **Step 3: Update `TODOS.md` with explicit child-plan queue**

Under `## Server Business Modularization Deferred Scope`, add:

```markdown

## Required Follow-up Plans After ai_video_series

These are not optional omissions. They are separate plans because each touches an independent subsystem.

- `device_operations` domain plan: split `server/app/routers/device.py` after `ai_video_series` proves the facade playbook.
- `content_collection` domain plan: split content generation, collection reports, and DM claim flows after device boundaries are stable.
- `account_operations` domain plan: split account, account group, channel, and task-chain ownership after content/device call sites are mapped.
- `ai_video_series` ORM graph extraction plan: move ORM class bodies only after `Series`/`Character`/`Scene`, production model ownership, Alembic imports, and legacy fixtures are mapped.
- Frontend consumption plan: update UI only after backend read models are stable and covered by API contract tests.
```

- [ ] **Step 4: Run facade cleanup tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_router_facade.py server/tests/test_ai_video_series_orm_boundary.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit cleanup gates**

```powershell
git add server/app/domains/ai_video_series/README.md server/tests/test_ai_video_series_router_facade.py server/tests/test_ai_video_series_orm_boundary.py TODOS.md
git commit -m "docs: add ai video series facade cleanup gates"
```

---

## Task 12: Program Follow-up Plans For Independent Domains

**Files:**

- Create `docs/superpowers/plans/2026-06-18-device-operations-domain-plan.md`
- Create `docs/superpowers/plans/2026-06-18-content-collection-domain-plan.md`
- Create `docs/superpowers/plans/2026-06-18-account-operations-domain-plan.md`

**Success criteria:**

- No approved broad modularization scheme is lost.
- Independent domains are not coded inside the `ai_video_series` PR chain.
- Each follow-up plan starts with the required `writing-plans` header and has its own file map, tests, and PR sequence.

- [ ] **Step 1: Create device operations child plan**

Create `docs/superpowers/plans/2026-06-18-device-operations-domain-plan.md` with this header and initial scope:

```markdown
# Device Operations Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move device pairing, websocket status, task polling, content generation, collection reports, DM claims, and asset upload endpoints out of the flat device router after the `ai_video_series` facade pattern is proven.

**Architecture:** Start with behavior-neutral boundary tests and auth characterization for `server/app/routers/device.py`, then move the router under `app.domains.device_operations` with legacy module identity, split polling/reporting/upload use cases, and add cleanup gates.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Pytest, existing task/device/account services.

---

## First Tasks

- [ ] Characterize current `/api/device/*` route methods and auth dependencies.
- [ ] Create `server/app/domains/device_operations`.
- [ ] Move `app.routers.device` behind a compatibility module alias.
- [ ] Split device polling, collection reporting, and upload handlers into focused modules.
- [ ] Add facade cleanup gates before removing old imports.
```

- [ ] **Step 2: Create content collection child plan**

Create `docs/superpowers/plans/2026-06-18-content-collection-domain-plan.md` with this header and initial scope:

```markdown
# Content Collection Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move content generation, collected-user/comment flows, DM claim/release flows, and collection read models into a focused content collection domain after device operations boundaries are mapped.

**Architecture:** Start with route and service characterization, then introduce `app.domains.content_collection` as a compatibility-preserving vertical slice. Reuse existing services as adapters before moving persistence or model ownership.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Pytest, existing content, data, DM sequence, and task services.

---

## First Tasks

- [ ] Characterize content/data/DM routes and response shapes.
- [ ] Create `server/app/domains/content_collection`.
- [ ] Move route modules through compatibility aliases.
- [ ] Split read models from mutation use cases.
- [ ] Add cleanup gates and child tests for old import paths.
```

- [ ] **Step 3: Create account operations child plan**

Create `docs/superpowers/plans/2026-06-18-account-operations-domain-plan.md` with this header and initial scope:

```markdown
# Account Operations Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move account, account group, channel, and task-chain ownership into an account operations domain after device/content dependencies are explicit.

**Architecture:** Keep existing API routes stable, add boundary tests, introduce `app.domains.account_operations`, then move account/group/channel/task-chain use cases behind compatibility facades.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Pytest, existing account, account group, channel, and chain services.

---

## First Tasks

- [ ] Characterize account/account-group/channel/chain routes and auth dependencies.
- [ ] Create `server/app/domains/account_operations`.
- [ ] Move route modules through compatibility aliases.
- [ ] Split orchestration use cases from read models.
- [ ] Add cleanup gates for legacy imports.
```

- [ ] **Step 4: Expand each child plan to implementation-plan completeness**

Before treating Task 12 as complete, each child plan must include these headings with concrete content:

```markdown
## File Map

## PR Sequence

## Boundary And Compatibility Tests

## Facade Cleanup Gates

## Final Verification

## GSTACK REVIEW REPORT
```

The `First Tasks` skeleton is only the seed. Do not start coding a child domain from a plan that lacks its own file map, route/auth characterization tests, compatibility facade strategy, and verification commands.

- [ ] **Step 5: Run Markdown/file existence and completeness check**

```powershell
Test-Path docs/superpowers/plans/2026-06-18-device-operations-domain-plan.md
Test-Path docs/superpowers/plans/2026-06-18-content-collection-domain-plan.md
Test-Path docs/superpowers/plans/2026-06-18-account-operations-domain-plan.md
rg -n "## File Map|## PR Sequence|## Boundary And Compatibility Tests|## Facade Cleanup Gates|## Final Verification|## GSTACK REVIEW REPORT" docs/superpowers/plans/2026-06-18-device-operations-domain-plan.md docs/superpowers/plans/2026-06-18-content-collection-domain-plan.md docs/superpowers/plans/2026-06-18-account-operations-domain-plan.md
```

Expected:

```text
True
True
True
```

Expected: each child plan reports all six required headings.

- [ ] **Step 6: Commit child plans**

```powershell
git add docs/superpowers/plans/2026-06-18-device-operations-domain-plan.md docs/superpowers/plans/2026-06-18-content-collection-domain-plan.md docs/superpowers/plans/2026-06-18-account-operations-domain-plan.md
git commit -m "docs: plan follow-up server domains"
```

---

## Task 13: Final Verification Before PR Review

**Files:**

- No new files.
- Verify all files touched by Tasks 1-12.

**Success criteria:**

- Architecture tests pass.
- Existing series behavior tests pass.
- Production readiness and start-flow tests pass.
- No whitespace errors.

- [ ] **Step 1: Run all new domain tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_domain_boundary.py server/tests/test_ai_video_series_auth_parity.py server/tests/test_ai_video_series_router_facade.py server/tests/test_ai_video_series_read_models.py server/tests/test_ai_video_series_orm_boundary.py server/tests/test_ai_video_series_status_read_model.py -q
```

Expected: PASS.

- [ ] **Step 2: Run existing series behavior tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_series_api.py server/tests/test_series_style_lock_pipeline.py server/tests/test_style_lock_background_worker.py server/tests/test_series_auto_generate_assets.py server/tests/test_series_planning_service.py -q
```

Expected: PASS.

- [ ] **Step 3: Run production contract tests touched by this domain**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_start_flow_contract.py server/tests/test_video_production_readiness.py server/tests/test_video_production_observability_events.py server/tests/test_video_production_run_type.py -q
```

Expected: PASS.

- [ ] **Step 4: Run model/import tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_database.py server/tests/test_models.py server/tests/test_models_package_imports.py server/tests/test_series_production_models.py server/tests/test_video_production_boundary_models.py -q
```

Expected: PASS.

- [ ] **Step 5: Run whitespace check**

```powershell
git diff --check
```

Expected: no whitespace errors. Existing LF-to-CRLF warnings are acceptable only if no file content is corrupted.

- [ ] **Step 6: Inspect old import path inventory**

```powershell
rg "app\.routers\.series|from app\.routers import series" server/app server/tests
rg "from app\.db_models import .*Series|from app\.db_models import .*Episode|from app\.db_models import .*VideoProductionRun" server/app server/tests
```

Expected:

- Legacy route imports may remain only where facade cleanup gates explicitly allow them.
- Legacy ORM imports may remain only where Task 11 documents cleanup gates or where broad test fixtures still intentionally exercise the compatibility facade.

- [ ] **Step 7: Commit final verification docs if any file changed**

If Task 13 changes only verification state, do not commit. If documentation changed during verification, commit exact files:

```powershell
git add docs/superpowers/specs/2026-06-17-server-business-modularization-design.md server/app/domains/ai_video_series/README.md TODOS.md
git commit -m "docs: update ai video series modularization verification"
```

---

## Self-Review

### Spec Coverage

- Domain skeleton: Task 2.
- PR1 behavior-neutral gate: Tasks 1-2.
- Route migration: Tasks 3-4.
- Compatibility for `app.routers.series`: Tasks 3-4 and Task 11.
- Split route-level business logic: Tasks 5-6.
- ORM boundary, shared `Base`, and `db_models.py` compatibility: Tasks 7-8.
- Physical ORM class-body extraction: Task 8 creates a required child plan instead of moving coupled model bodies in the same PR.
- Auth parity: Task 1.
- Production truth/status matrix: Tasks 9-10.
- Batched evidence loading: Task 10.
- Existing audit path reuse: Task 9 keeps status evidence in existing production model surface and Task 13 runs observability tests.
- Facade retirement gates: Task 11.
- Other domain schemes: Task 12 creates required child implementation plans instead of hiding them.

No approved `ai_video_series` scheme is omitted. The unsafe physical ORM class-body move is represented as a required child plan with explicit graph/import gates.

### Placeholder Scan

The plan uses concrete file paths, code blocks, commands, expected outputs, and named follow-up plan files. Deferred work is represented by concrete child plan files in Tasks 8 and 12.

### Type And Name Consistency

- Domain metadata names are `DOMAIN_NAME` and `PUBLIC_ROUTE_PREFIX`.
- Router compatibility target is `app.domains.ai_video_series.router`.
- ORM boundary module is `app.db.models.ai_video_series`.
- Status public function is `build_episode_status_matrix`.
- Read model public functions are `series_dict`, `episode_dict_with_video_run`, `episode_asset_scope_payload`, and `active_video_runs_by_episode`.
- Legacy aliases keep old underscore names during migration.

## Autoplan Full Review Report

Generated: 2026-06-18.
Mode: CEO SELECTIVE EXPANSION, Eng FULL_REVIEW, DX POLISH.
Final gate: approved by the user's standing approval instruction.

### Phase 0 Intake

Plan summary: incremental backend modularization for the `ai_video_series` vertical slice. The plan moves route-level series behavior into `app.domains.ai_video_series`, preserves public API behavior through facades, creates an ORM import boundary, adds a batched production status read model, and creates required child plans for independent domains.

UI scope: no. The UI term scan matched review/report/routing words and the deferred frontend plan, but this implementation plan changes backend modules and tests only.

DX scope: yes. The primary users are future coding agents and maintainers executing this plan. The plan contains commands, imports, compatibility surfaces, child plans, and developer-facing failure modes.

External references used:

- FastAPI's "Bigger Applications" documentation supports splitting route modules with `APIRouter` while preserving application flexibility: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- SQLAlchemy's metadata/declarative documentation supports keeping one mapped registry/metadata surface while models coordinate through a declarative base: https://docs.sqlalchemy.org/en/latest/tutorial/metadata.html

### Voice Degradation Matrix

| Phase | Codex voice | Subagent voice | Effective source | Impact |
|---|---|---|---|---|
| CEO | unavailable: WindowsApps `codex.exe` returned access denied; WSL has no `codex` | unavailable by current tool policy because user did not explicitly request subagents | single-reviewer mode | No cross-model consensus; all findings require local evidence |
| Design | skipped, no UI scope | skipped, no UI scope | skipped | Not applicable |
| Eng | unavailable: same Codex preflight failure | unavailable by current tool policy | single-reviewer mode | Eng review is local-only but evidence-backed |
| DX | unavailable: same Codex preflight failure | unavailable by current tool policy | single-reviewer mode | DX scores are local-only |

### CEO Phase

Premise gate: accepted. The user already approved the server modularization direction and gave standing approval for future gates. No user challenge was found because the plan keeps the approved vertical-slice strategy and explicitly defers independent domains.

Premise challenge:

| Premise | Verdict | Evidence |
|---|---|---|
| `ai_video_series` should move first | Accepted | It is the largest current series/video hotspot and has route, worker, read-model, ORM, and status surfaces that prove the playbook |
| Public `/api/series/*` behavior must not change | Accepted | Existing frontend and production flows depend on stable FastAPI routes and auth behavior |
| Compatibility facades are worth the temporary indirection | Accepted | Tests and `app.main` still use old paths; removing them in the same PR would create a migration cliff |
| ORM class-body extraction can wait | Accepted | `Series`, `Character`, `Scene`, association tables, and production models share a relationship/import graph |

Existing code leverage:

| Sub-problem | Existing code reused | Plan choice |
|---|---|---|
| Route behavior | `server/app/routers/series.py` | Copy first, then alias old module to domain router |
| Story planning | `server/app/services/series_planning_service.py` | Reuse service, move only route orchestration |
| Style lock/reference work | Current series router helpers plus existing provider services | Move helpers to `style_lock.py`, keep patchable dependency points |
| Production queue | `production_queue_service.claim_next_job`, job states | Reuse existing queue model, no new queue infra |
| Audit/events | `ProductionAuditEvent`, `record_production_event` | Reuse existing audit path |
| ORM registry | `app.db_models.Base` and SQLAlchemy metadata | Extract shared `Base`, preserve facade over existing class bodies |

Dream state delta:

```text
CURRENT
  flat routers/series.py owns route assembly, workers, helpers, schemas, read models
    |
    v
THIS PLAN
  ai_video_series domain owns route assembly, focused modules, status read model,
  and tested compatibility facades
    |
    v
12-MONTH IDEAL
  each server business domain has its own router, use cases, read models, model
  boundary, facade cleanup gate, and implementation plan
```

Implementation alternatives:

| Approach | Effort | Risk | Pros | Cons | Decision |
|---|---:|---:|---|---|---|
| Minimal facade only | S | Med | Very small diff; fast | Leaves router too large and status truth hidden | Rejected |
| Incremental vertical slice | M | Low | Proves domain pattern without public behavior changes | More plan/test work | Accepted |
| Big-bang server modularization | XL | High | Broad cleanup in one push | Massive conflict risk, hard rollback | Rejected |

CEO decisions:

- Accepted the incremental vertical slice because it is the complete lake inside the `ai_video_series` blast radius.
- Deferred device/content/account implementation to child plans because they are independent subsystems.
- Converted physical ORM extraction into a required child plan because the import graph is load-bearing.

### Eng Phase

Scope challenge: the plan touches more than eight files and introduces more than two modules, but the complexity is essential. The work is split into PR-sized phases with behavior-neutral gates, so the right reduction is not "do less"; it is "keep each PR reversible."

Architecture diagram:

```text
FastAPI app.main
  |
  v
app.routers.series -------------- compatibility alias
  |                                      |
  v                                      v
app.domains.ai_video_series.router -- public route assembly
  |        |          |           |            |
  |        |          |           |            +--> status_read_model.py
  |        |          |           +--------------> style_lock.py
  |        |          +--------------------------> story_planning.py
  |        +-------------------------------------> read_models.py
  +----------------------------------------------> artifacts.py / schemas.py
                                                   |
                                                   v
app.db.models.ai_video_series --------------- ORM facade
  |
  v
app.db_models ------------------------------- legacy model owner
  |
  v
app.db.base.Base ---------------------------- single metadata registry
```

Data flow with shadow paths:

```text
GET /api/series/{id}
  -> auth dependency snapshot
  -> load Series + Episodes
  -> build_episode_status_matrix(series_id)
       -> episodes query
       -> latest runs query
       -> active jobs query
       -> approved artifacts query
  -> attach production_status to each episode
  -> return legacy-compatible payload

nil/missing series_id -> existing route not-found behavior
empty episodes -> empty matrix, no per-episode queries
upstream DB error -> request fails loudly through existing FastAPI error handling
running run with no active job -> named blocked status, not "producing"
```

Architecture findings:

| # | Finding | Decision | Principle | Change |
|---|---|---|---|---|
| 1 | Task 6 moved private function globals but did not force tests to patch the owning modules | Auto-fix | Explicit over clever | Added patchable dependency test and migrated patch-target requirement |
| 2 | Task 6 commit command omitted existing tests modified by the migration | Auto-fix | Completeness | Added `test_series_style_lock_pipeline.py` and `test_style_lock_background_worker.py` to the commit |
| 3 | Task 12 child plans claimed file map/tests/PR sequence but only seeded first tasks | Auto-fix | Completeness | Added child-plan completeness gate requiring six headings |

Code quality review:

- Module boundaries fit existing FastAPI patterns: router assembly remains in `router.py`, pure builders move to non-FastAPI modules, and compatibility facades are documented.
- The plan avoids a new abstraction layer for ORM ownership until the graph is proven. That is the right explicit choice.
- No DRY issue remains in the plan after Task 6 patch targets and Task 12 child-plan gates were fixed.

Test diagram:

```text
CODE PATHS                                                     COVERAGE
[+] Domain skeleton import                                     Task 1/2 smoke tests
[+] /api/series route/auth snapshot                            Task 1 auth parity
[+] app.routers.series -> domain router module identity         Task 3/4 facade tests
[+] copied router globals before worker split                   Task 3/4 monkeypatch identity test
[+] moved style-lock worker globals                             Task 6 patchable dependency test
[+] moved story-plan worker globals                             Task 6 patchable dependency test
[+] schemas/read_models/artifacts split                         Task 5 boundary/read-model tests
[+] ORM facade names and one metadata object                    Task 7 ORM boundary tests
[+] shared Base extraction                                      Task 8 Base test
[+] clean subprocess import order                               Task 8 subprocess import test
[+] physical ORM class-body extraction deferred safely          Task 8 child plan gate
[+] episode production status matrix                            Task 9 status tests
[+] status batching                                             Task 10 query-count guard
[+] facade cleanup gates                                        Task 11 README/tests
[+] child domain plan completeness                              Task 12 heading gate
```

Coverage: 15/15 planned codepath groups have tests or explicit child-plan gates after autoplan corrections.

Failure modes registry:

| Codepath | Failure mode | Test/gate | User sees | Critical gap |
|---|---|---|---|---|
| Router alias | legacy import returns a different module object | Task 3/4 identity test | test failure before merge | no |
| Worker split | private monkeypatch patches router alias but function reads new module globals | Task 6 patchable dependency test | test failure before merge | no |
| ORM boundary | second `Base` creates split metadata | Task 7/8 one metadata tests | test failure before merge | no |
| ORM extraction | `Series` move creates `Character`/`Scene` circular import | Task 8 child plan gate | extraction blocked before code move | no |
| Status matrix | N+1 queries across episodes | Task 10 query-count guard | test failure before merge | no |
| Status truth | run marked running but no active job | Task 9 blocked status test | named `RUNNING_WITHOUT_ACTIVE_JOB` | no |
| Child plans | thin child plan starts coding without boundaries/tests | Task 12 completeness gate | plan fails before coding | no |

Performance review:

- Main performance risk is the new episode status payload. Task 10 limits it to batched episode/run/job/artifact queries.
- No cache is needed in the plan because the read model is request-scoped and evidence must be fresh.
- The plan does not add new infrastructure, background queues, migrations, or external calls.

Worktree parallelization:

| Lane | Work | Depends on | Conflict risk |
|---|---|---|---|
| A | Tasks 1-4 skeleton and router alias | none | touches series router, run sequentially |
| B | Tasks 5-6 module splits | Lane A | touches domain router/tests, sequential |
| C | Tasks 7-8 ORM boundary/base | Lane A | touches ORM modules/tests, can start after router alias stabilizes |
| D | Tasks 9-10 status read model | Lane C | touches domain read model/tests |
| E | Tasks 11-12 cleanup gates and child plans | Lanes B/C | docs/tests, can run after gates exist |

Execution order: A first, then B and C can proceed in separate worktrees with coordination, then D, then E. Final verification runs after all lanes merge.

### DX Phase

Product type: internal developer/agent implementation plan.

Developer persona:

| Field | Value |
|---|---|
| Who | A future coding agent or maintainer implementing the plan task-by-task |
| Context | They inherit a dirty branch and need exact commands, file ownership, and pass/fail gates |
| Tolerance | Low for ambiguity; they should not infer missing file lists, test targets, or migration order |
| Expects | Every task states files, commands, expected failures, expected passes, and cleanup gates |

Developer empathy narrative:

I open the implementation plan and expect to execute one checkbox at a time. I can follow the route migration because the old and new module identities are spelled out. I slow down at Task 6 because private monkeypatches are easy to misread: if I patch `app.routers.series` after moving functions, my test may stop controlling the code under test. Autoplan now points me at `style_lock.py` and `story_planning.py`. I slow down again at Task 12 because child plans need the same rigor as the parent. Autoplan now blocks thin child plans with a completeness gate.

Developer journey map:

| Stage | Developer does | Friction found | Status |
|---|---|---|---|
| Discover | Opens plan file | Needs restore point | fixed |
| Prepare | Reads scope/file map | UI/DX scope could be confused | documented |
| Execute PR1-PR2 | Creates skeleton and router alias | clear commands | ok |
| Execute PR3 | Splits workers | private patch targets were ambiguous | fixed |
| Execute PR4 | Adds ORM boundary | class-body extraction risk documented | fixed |
| Execute PR5 | Adds status read model | batching guard present | ok |
| Execute PR6 | Adds cleanup gates | legacy paths inventoried | ok |
| Continue domains | Creates child plans | child plan skeleton too thin | fixed |
| Debug | Runs listed tests | test plan artifact now exists | fixed |

DX scorecard:

| Dimension | Score | Notes |
|---|---:|---|
| Getting Started | 8/10 | Restore point, file map, commands, and expected failures are present |
| API/import design | 9/10 | Public and private import boundaries now separated |
| Error/debugging | 8/10 | Expected failure outputs are named; status blocking codes are explicit |
| Documentation | 8/10 | Parent plan is strong; child plans now have completeness gate |
| Upgrade/migration path | 9/10 | Facade cleanup gates and legacy inventories are explicit |
| Dev environment | 7/10 | Windows PowerShell commands are clear; Codex CLI unavailable is environment friction |
| Community/ecosystem | 6/10 | Internal project; not a public developer product |
| Measurement/feedback | 8/10 | Review logs, test artifact, and verification commands exist |

Overall DX: 8/10.
TTHW for implementer: about 10-15 minutes to begin PR1 safely.
Target TTHW: under 10 minutes for future domain plans after Task 12 templates are expanded.

DX implementation checklist:

```text
[x] Restore point captured
[x] One clear first command/test per phase
[x] Every route/API behavior change has a parity test
[x] Every compatibility facade has an exit gate
[x] Private monkeypatch paths point to owning modules after split
[x] ORM class-body extraction has a relationship graph gate
[x] Status read model has named blocked states
[x] Query batching has a regression guard
[x] Child plans have a completeness gate
[x] Eng review test plan artifact written
```

### NOT In Scope

| Item | Rationale |
|---|---|
| Frontend implementation | Backend read models must stabilize first |
| Device/content/account coding | Independent domains need their own complete implementation plans |
| Physical ORM class-body extraction | Requires graph/import/Alembic plan first |
| Full `video_production_service.py` rewrite | Too wide for the series vertical slice |
| Schema-changing migrations | No schema need proven in this plan |
| Broad platform rate limiting | Outside `ai_video_series` blast radius |

### Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | CEO | Keep incremental `ai_video_series` vertical slice | Mechanical | Completeness | Proves the domain playbook without broad rewrite risk | big-bang modularization |
| 2 | CEO | Skip UI design review | Mechanical | Pragmatic | No UI files or user-facing screens are in scope | forced design pass |
| 3 | CEO | Run DX review | Mechanical | Completeness | Agent-facing implementation plans need executable developer experience | skip DX |
| 4 | Eng | Keep shared `Base` plus facade before ORM class moves | Mechanical | Explicit over clever | Relationship graph is load-bearing | direct class-body move |
| 5 | Eng | Migrate private monkeypatches to owning modules | Mechanical | Explicit over clever | Router alias cannot patch moved globals reliably | patch-sync wrapper |
| 6 | Eng | Add patchable dependency boundary test | Mechanical | Completeness | Prevents Task 6 from regressing silently | rely on manual discipline |
| 7 | Eng | Include modified legacy tests in Task 6 commit | Mechanical | Completeness | Commit command must match the write set | leave tests unstaged |
| 8 | Eng | Add child-plan completeness gate | Mechanical | Completeness | Task 12 success criteria require real file map/tests/PR sequence | thin child plan skeletons |
| 9 | DX | Treat Codex/subagent voices as unavailable and continue | Mechanical | Bias toward action | Tooling unavailable should not block plan hardening | abort autoplan |

### Autoplan Completion Summary

| Phase | Result |
|---|---|
| CEO | Cleared with prior corrections preserved |
| Design | Skipped, no UI scope |
| Eng | Cleared after 3 plan corrections |
| DX | 8/10, cleared after child-plan and test-plan fixes |
| User challenges | 0 |
| Taste decisions | 0 |
| Auto-decisions | 9 |
| Critical gaps | 0 after corrections |
| Test plan artifact | `C:\Users\szm\.gstack\projects\dy_auto_new\szm-codex-bailian-high-quality-video-pipeline-eng-review-test-plan-20260618-112857.md` |

## Plan CEO Review Report

Status: DONE_WITH_CONCERNS.
Date: 2026-06-18.
Mode: HOLD_SCOPE.
Verdict: Approved after corrections.

Findings:

1. Task 4's `sys.modules[__name__] = domain_module` router alias is valid for PR2 because legacy and domain imports share one module object while the copied router still owns function globals.
2. Task 6 needed a correction: private monkeypatch paths against `app.routers.series` would stop affecting moved worker globals. The plan now requires migrating private patch targets to `style_lock.py` and `story_planning.py`.
3. Task 8 needed a correction: physical ORM class-body extraction is unsafe in the same PR as shared `Base` extraction because `Series`, `Character`, `Scene`, association tables, and the production model family share one import graph. The plan now limits PR4 to shared `Base` plus a complete facade, and creates a required ORM graph extraction child plan.

Decision: proceed with the implementation plan after these corrections. Fresh engineering review remains recommended before code implementation because the plan now changes ORM sequencing.

## Plan Eng Review Report

Status: DONE.
Date: 2026-06-18.
Mode: FULL_REVIEW.
Verdict: Clear. The standalone `/plan-eng-review` run found no new unresolved architecture, code quality, test, or performance gaps after the prior `/autoplan` corrections.

### Step 0 Scope Challenge

| Check | Result |
|---|---|
| What already exists | Reuses `app.routers.series`, `series_planning_service.py`, existing style-lock/reference helpers, `ProductionAuditEvent`, `record_production_event`, `VideoProductionRun`, `ProductionJob`, and `app.db_models` as a compatibility facade. |
| Minimum change | Keep the approved `ai_video_series` vertical slice; independent device/content/account domains stay as child plans. |
| Complexity | More than eight files and more than two modules are touched, but the complexity is split into reversible PR-sized phases with behavior-neutral gates. |
| Search check | [Layer 1] FastAPI official docs support splitting large apps with package modules and `APIRouter`; [Layer 1] SQLAlchemy official docs support one shared `MetaData`/declarative base and relationship graph caution. |
| TODOs | Existing `TODOS.md` deferred scope is aligned. No new TODO entry is required from this standalone review. |
| Distribution | No new binary/package/container artifact is introduced. |

Sources checked:

- FastAPI bigger applications / `APIRouter`: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- SQLAlchemy shared metadata and declarative base: https://docs.sqlalchemy.org/en/latest/tutorial/metadata.html
- SQLAlchemy relationship and many-to-many patterns: https://docs.sqlalchemy.org/en/latest/orm/basic_relationships.html

### Architecture Review

No new issues found.

The current plan keeps the safest architecture: route behavior moves through a compatibility alias, private patch points move to owning modules before worker extraction, and ORM class-body movement is blocked behind the child graph extraction plan.

```text
FastAPI app.main
  -> app.routers.series                         legacy compatibility entry
       -> app.domains.ai_video_series.router    route assembly
            -> schemas/read_models/artifacts
            -> style_lock/story_planning
            -> status_read_model
                 -> app.db.models.ai_video_series facade
                      -> app.db_models legacy owner
                           -> app.db.base.Base single metadata registry
```

### Code Quality Review

No new issues found.

The plan is explicit about temporary facades, keeps router code from becoming the long-term business logic home, and avoids adding a router-level patch synchronization layer. That matches the project preference for explicit, right-sized changes instead of clever compatibility magic.

### Test Review

Test framework detected: pytest for server tests from `CLAUDE.md`.

```text
CODE PATHS / USER FLOWS                                      COVERAGE
[+] Domain skeleton and import smoke                         Task 1/2
[+] /api/series route table and auth parity                   Task 1
[+] app.routers.series compatibility identity                 Task 3/4
[+] schema/read-model/artifact split                          Task 5
[+] story planning worker split and patch points              Task 6
[+] style-lock worker split and patch points                  Task 6
[+] ORM facade and shared Base                                Task 7/8
[+] ORM graph extraction deferral                             Task 8 child plan
[+] episode production status truth                           Task 9
[+] running run without active job is blocked                 Task 9
[+] status read-model query batching                          Task 10
[+] facade cleanup gates                                      Task 11
[+] independent child-plan completeness                       Task 12
[+] final series/production/model verification                Task 13
```

Coverage: 14/14 planned path groups have a direct test, focused verification command, or explicit child-plan gate. No additional test gap was found.

Standalone test plan artifact: `C:\Users\szm\.gstack\projects\dy_auto_new\szm-codex-bailian-high-quality-video-pipeline-plan-eng-review-test-plan-20260618-standalone.md`.

### Performance Review

No new issues found.

The main runtime risk is the new episode production status payload. Task 10 already adds a query-count regression test so the matrix loads episodes, runs, jobs, and artifacts in batches rather than per episode.

### Failure Modes

| Codepath | Realistic failure | Covered by |
|---|---|---|
| Router alias | Old import path points at a different module object | Task 3/4 facade identity tests |
| Worker split | Tests patch `app.routers.series` after globals move | Task 6 owning-module patch requirements and dependency test |
| ORM boundary | A second SQLAlchemy `Base` splits metadata | Task 7/8 single-Base tests |
| ORM extraction | `Series`/`Character`/`Scene` relationship graph creates import-order failure | Task 8 child plan gate |
| Status matrix | Running run displays as producing without active job evidence | Task 9 blocked status test |
| Status batching | New payload creates N+1 episode queries | Task 10 query-count guard |
| Child domains | Thin child plans start coding without file map/tests/PR sequence | Task 12 completeness gate |

Critical gaps: 0.

### Worktree Parallelization

| Lane | Work | Depends on |
|---|---|---|
| A | Tasks 1-4 domain skeleton and router alias | none |
| B | Tasks 5-6 schemas/read models/workers | A |
| C | Tasks 7-8 ORM facade/Base/graph gate | A |
| D | Tasks 9-10 status read model and batching | C |
| E | Tasks 11-12 cleanup gates and child plans | B + C |

Recommended order: run A first, then B and C can proceed in coordinated worktrees, then D, then E and Task 13 final verification.

### Outside Voice

Unavailable. WindowsApps `codex.exe` returned access denied, WSL had no `codex` binary, and subagent fallback is unavailable under the current tool policy because this turn did not explicitly request delegation. No cross-model tension exists.

### Completion Summary

| Section | Result |
|---|---|
| Step 0 Scope Challenge | Scope accepted as-is |
| Architecture Review | 0 new issues |
| Code Quality Review | 0 new issues |
| Test Review | Diagram produced, 0 new gaps |
| Performance Review | 0 new issues |
| NOT in scope | Already written in Autoplan report and preserved |
| What already exists | Written above |
| TODOS.md updates | 0 new items proposed |
| Failure modes | 0 critical gaps |
| Outside voice | Unavailable |
| Parallelization | 5 lanes, A first, B/C parallel after A |
| Lake Score | Complete option preserved for all reviewed recommendations |

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/autoplan` -> `/plan-ceo-review` | Scope & strategy | 2 | CLEAR via /autoplan | Premises accepted; vertical-slice strategy preserved; independent domains deferred to complete child plans |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | UNAVAILABLE | WindowsApps `codex.exe` access denied; WSL has no `codex` binary |
| Eng Review | `/autoplan` -> `/plan-eng-review`; `/plan-eng-review` | Architecture & tests (required) | 2 | CLEAR via /autoplan + /plan-eng-review | 3 autoplan issues fixed and preserved; standalone Eng review found 0 new issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | SKIPPED | No UI implementation scope |
| DX Review | `/autoplan` -> `/plan-devex-review` | Developer experience gaps | 1 | CLEAR via /autoplan | Internal implementer DX 8/10; test artifact written; TTHW target under 10 minutes |

- **CROSS-MODEL:** unavailable because Codex and subagent voices both degraded; local review used code and plan evidence.
- **UNRESOLVED:** 0 user decisions; 0 critical gaps after autoplan and standalone Eng review.
- **VERDICT:** CEO + ENG + DX CLEARED via /autoplan; standalone ENG CLEARED via `/plan-eng-review`; ready for implementation.

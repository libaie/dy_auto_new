# Server Business Modularization Design

Date: 2026-06-17

## Goal

Rebuild the server structure around business domains instead of continuing to grow flat technical folders. The current server has too much business logic concentrated in `app/routers`, `app/services`, and the single `app/db_models.py` module. This makes multi-step AI video workflows difficult to understand, test, and change safely.

The target outcome is a gradual migration path where business areas have clear homes, API behavior remains stable, and old import paths keep working while implementation moves behind better boundaries.

## Current Context

The current `server/app` layout has about 181 files under technical folders such as `routers`, `services`, `models`, `utils`, and `data`.

The largest maintenance hotspots are:

- `app/db_models.py`, which holds all ORM models across unrelated business areas.
- `app/routers/series.py`, which mixes CRUD, read-model building, style-lock workers, story planning, artifact recording, episode script generation, and asset scope payloads.
- `app/routers/device.py`, which mixes device pairing, websocket status, task polling, content generation, collection reports, DM claims, and asset upload endpoints.
- `app/services/video_production_service.py`, `app/services/image_creation_service.py`, `app/services/one_sentence_video_service.py`, and `app/services/production_run_service.py`, which are large orchestration files with many separate responsibilities.

The working tree also contains many unrelated in-progress changes. The refactor must therefore be incremental and compatible, not a broad rewrite.

## Approved Direction

Use a domain package structure and migrate incrementally.

The approved first target is the AI video series and multi-episode production chain, because it is currently where the user-facing production issues are most concentrated. This includes series story planning, style lock, episode asset scopes, episode scripts, storyboards, AI text artifacts, and production start glue.

## Target Structure

The long-term structure should look like this:

```text
server/app/
  core/
    config.py
    database.py
    deps.py
    auth.py
    time.py
    errors.py
  db/
    base.py
    session.py
    models/
  domains/
    ai_video_series/
      __init__.py
      router.py
      schemas.py
      read_models.py
      story_planning.py
      style_lock.py
      episode_assets.py
      episode_scripts.py
      jobs.py
      artifacts.py
    video_production/
    image_generation/
    device_automation/
    agency_review/
    content_ops/
  routers/
  services/
  models/
```

The first implementation should not attempt the full long-term tree. It should create `app/domains/ai_video_series` and make `app/routers/series.py` a compatibility entrypoint.

## First Migration Boundary

Phase 1 migrates route-level business logic out of `app/routers/series.py`.

Move these responsibilities into `app/domains/ai_video_series`:

- request and response schemas currently local to `series.py`;
- series and episode payload/read-model helpers;
- story planning endpoint state, completed-payload detection, enqueue logic, and worker step glue;
- style-lock state, enqueue logic, reference progress helpers, and worker step glue;
- episode asset scope payload helpers;
- episode script and storyboard generation endpoint glue;
- AI text artifact recording helpers used by series and episode update flows;
- router assembly for `/api/series/*`.

Keep these files in place during the first phase:

- `app/services/series_planning_service.py`;
- `app/services/production_run_service.py`;
- `app/services/video_production_service.py`;
- `app/services/script_pipeline.py`;
- `app/services/ai_text_artifact_service.py`;
- `app/db_models.py`.

Those service and model files can be split in later phases after the route boundary is stable.

## Compatibility Strategy

`app/routers/series.py` should remain importable.

After Phase 1 it should be a thin compatibility module, roughly:

```python
from app.domains.ai_video_series.router import router
```

If tests or background workers still import internal helper names from `app.routers.series`, the first migration may re-export those names from the new domain modules. This keeps the migration surgical and avoids rewriting the whole test suite at the same time as moving code.

External behavior must not change:

- `/api/series/*` paths remain the same.
- `app/main.py` can continue importing `series.router`.
- Existing database tables and migrations remain unchanged.
- Existing service call sites outside the series router keep working.

## Dependency Rules

Use simple dependency rules for the first phase:

```text
app.domains.ai_video_series.router
  -> handles FastAPI, Depends, HTTPException, and request/response translation

app.domains.ai_video_series.*
  -> may call existing app.services modules
  -> may use app.db_models ORM classes
  -> may use app.database Session dependencies

app.services.*
  -> must not import app.domains.ai_video_series during Phase 1
```

This makes the domain package the new business entrypoint without forcing all existing services to move at once. It also avoids circular imports while the codebase is in a mixed old/new structure.

## Anti-Regression Rules

The refactor should add boundary tests so the codebase does not slide back into the current shape.

Rules for the first domain:

- New `/api/series/*` business logic must go into `app/domains/ai_video_series`, not into `app/routers/series.py`.
- `app/routers/series.py` must stay a thin compatibility module after migration.
- A single domain module should not grow into another large file. If a file reaches roughly 500 lines, split it by business action.
- Endpoint functions should stay short. Long workflows belong in domain modules, not in router functions.
- `app/services` must not reverse-import `app.domains.ai_video_series`.

Add a structure test such as `server/tests/test_server_modular_boundaries.py` to enforce:

- `app/domains/ai_video_series` exists;
- `app/routers/series.py` is thin after Phase 1;
- `app/services` does not import `app.domains.ai_video_series`.

## Implementation Phases

### Phase 0: Domain Skeleton and Boundary Tests

Create:

```text
server/app/domains/__init__.py
server/app/domains/ai_video_series/__init__.py
server/tests/test_server_modular_boundaries.py
```

The boundary test should initially enforce only what is true at that phase. It can be tightened once `app/routers/series.py` has been migrated.

### Phase 1: Move Series Route-Level Business Logic

Create the first set of domain modules:

```text
app/domains/ai_video_series/router.py
app/domains/ai_video_series/schemas.py
app/domains/ai_video_series/read_models.py
app/domains/ai_video_series/story_planning.py
app/domains/ai_video_series/style_lock.py
app/domains/ai_video_series/episode_assets.py
app/domains/ai_video_series/episode_scripts.py
app/domains/ai_video_series/jobs.py
app/domains/ai_video_series/artifacts.py
```

Then make `app/routers/series.py` a compatibility layer.

Acceptance criteria:

- `/api/series/*` behavior is unchanged.
- `app/main.py` continues to include `series.router`.
- `app/routers/series.py` is clearly thin.
- Series-related tests pass.
- Boundary tests pass.

### Phase 2: Split Service-Layer Hotspots

After the route layer is stable, split the implementation-heavy services gradually.

Priority files:

- `series_planning_service.py`;
- `production_run_service.py`;
- `video_production_service.py`.

The old service modules should become facades during migration, exporting stable names while implementation moves into the domain package.

### Phase 3: Repeat for Other Domains

Apply the same pattern to other server areas.

Recommended order:

1. `ai_video_series`;
2. `image_generation`;
3. `device_automation`;
4. `agency_review`;
5. `content_ops`.

The order is based on current file size, change frequency, and user-visible workflow complexity.

## Testing Strategy

Phase 1 should verify behavior using existing tests first:

```text
server/tests/test_series_api.py
server/tests/test_series_planning_service.py
server/tests/test_series_style_lock_pipeline.py
server/tests/test_video_production_start_flow_contract.py
```

Add structure tests for the new modular boundary.

If the migration touches imports used by production startup, also run an app import smoke test:

```text
python -c "from app.main import app; print(app.title)"
```

## Non-Goals

The first phase will not:

- redesign database tables;
- split `app/db_models.py`;
- rename public API paths;
- migrate every server feature into domains;
- rewrite the whole test suite;
- introduce a full Clean Architecture framework;
- move frontend code.

## Risks and Mitigations

Large dirty worktree:

- Keep commits narrow.
- Stage only refactor files for this work.
- Avoid touching unrelated modules.

Circular imports:

- Keep the dependency direction simple.
- Domain modules may call legacy services.
- Legacy services must not import the new domain package during Phase 1.

Behavior regressions:

- Keep public API paths unchanged.
- Run existing series and production-start tests.
- Add boundary tests to protect the new structure.

Half-migrated confusion:

- Keep compatibility wrappers explicit.
- Document old files as temporary facades once they are thinned.
- Tighten boundary tests after each phase.

## Completion Definition

The full server modularization goal is complete only when the main business areas live under domain packages and the old flat technical folders no longer accumulate new business logic.

- Implementation plan: `docs/superpowers/plans/2026-06-18-server-business-modularization.md`.

The first implementation plan should target this narrower milestone:

- `app/domains/ai_video_series` exists and owns the series route-level business flow.
- `app/routers/series.py` is a thin compatibility module.
- Existing `/api/series/*` behavior is preserved.
- Boundary tests prevent the old series router from growing again.
- Relevant series and production-start tests pass.

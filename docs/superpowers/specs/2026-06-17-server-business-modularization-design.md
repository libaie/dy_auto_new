<!-- /autoplan restore point: C:\Users\szm\.gstack\projects\dy_auto_new\codex-bailian-high-quality-video-pipeline-autoplan-restore-20260617-233941.md -->
<!-- /autoplan restore point: C:\Users\szm\.gstack\projects\dy_auto_new\codex-bailian-high-quality-video-pipeline-autoplan-restore-20260618-102658.md -->
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

## Autoplan Review Report

Status: in progress, waiting on premise confirmation.

### Phase 0: Intake

Base branch: `main`.

Plan file: `docs/superpowers/specs/2026-06-17-server-business-modularization-design.md`.

Restore point: `C:\Users\szm\.gstack\projects\dy_auto_new\codex-bailian-high-quality-video-pipeline-autoplan-restore-20260617-233941.md`.

Scope detection:

- UI review: skipped. The plan has no direct UI screen/component changes.
- DX review: enabled. The plan changes developer-facing server structure, import paths, routing ownership, and onboarding for future contributors.
- Codex external voice: unavailable. `codex.exe --version` failed with `Access is denied`, so dual-voice sections will mark Codex as unavailable unless the CLI is fixed before those phases.

System audit evidence:

- `server/app/db_models.py` is a 1470-line ORM concentration point.
- `server/app/routers/series.py` is about 1590 lines and mixes HTTP, read models, workers, story planning, style lock, artifacts, and episode generation.
- `server/app/routers/device.py` is about 1410 lines and remains a later-domain hotspot.
- `server/app/services/video_production_service.py`, `image_creation_service.py`, `one_sentence_video_service.py`, and `production_run_service.py` are the largest service-layer hotspots.
- No git stashes are present.
- No root `TODOS.md` exists. Deferred review items should stay in this plan unless a project-level TODO file is introduced deliberately.

### Phase 1: CEO Premise Challenge

Specific premises to confirm:

1. The real problem is maintainability and change safety, not runtime behavior. The plan should therefore preserve API behavior while moving ownership boundaries.
2. The first business domain should be `ai_video_series`, because recent work and current user pain are concentrated in series planning, episode assets, scripts, storyboards, artifacts, and production start.
3. The migration should be incremental. A full clean-architecture rewrite would create too much risk in the current dirty worktree.
4. The first milestone should move route-level series business logic before splitting `db_models.py` or service-layer internals.
5. Compatibility matters. Existing `/api/series/*`, `app.main`, tests, and old import paths should keep working during Phase 1.

Premise assessment:

| Premise | Assessment | Risk if wrong |
|---|---|---|
| Maintainability is the core problem | Strong evidence from file size and mixed responsibilities | If runtime bugs are the real priority, this plan may improve structure without fixing the user's immediate production pain |
| Start with `ai_video_series` | Strong evidence from current bugs and large mixed `series.py` flow | If device automation is the higher business priority, the first module will not reduce the most active maintenance pain |
| Incremental migration | Strong evidence from dirty worktree and broad import surface | A big-bang rewrite would likely break imports, tests, or in-progress work |
| Route layer first | Good but not perfect | If service-layer coupling is the true blocker, Phase 1 may leave too much complexity behind facades |
| Compatibility first | Strong | If old imports are kept too long, compatibility wrappers can become permanent clutter |

Recommended decision: accept these premises and proceed with `HOLD SCOPE` for the CEO phase. This is a refactor plan, and the biggest risk is scope expansion turning a maintainability pass into a rewrite.

### Autonomous Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | Phase 0 | Skip UI design review | Mechanical | Explicit over clever | The plan does not add or change user-facing screens, components, forms, layout, dashboard, or dialogs | Running UI review on a backend structure plan |
| 2 | Phase 0 | Enable DX review | Mechanical | Choose completeness | The plan changes developer-facing server organization, import ownership, tests, and future onboarding | Treating this as backend-only and skipping developer experience |
| 3 | Phase 0 | Degrade Codex voice to unavailable for now | Mechanical | Bias toward action | `codex.exe` failed with Access denied, so waiting on CLI auth/permissions would stall review | Blocking the review on a local CLI issue |

## OpenClaw CEO Review Report

Status: DONE.

Mode: `SCOPE EXPANSION`.

Selected approach: `C`, ideal architecture migration.

User approval model: the user approved proposals 1-5 and then granted blanket approval for the remaining OpenClaw CEO review decisions on 2026-06-18.

### Accepted Scope Expansion

The original route-layer modularization plan is expanded into a full `ai_video_series` vertical slice.

Accepted additions:

1. `ai_video_series` becomes a vertical slice, not only a router relocation.
2. Series-related ORM models move behind a new `app.db.models.*` boundary while `app/db_models.py` remains a compatibility facade.
3. Series production orchestration logic moves behind domain use cases and `legacy_*` adapters.
4. Production truth and observability become first-class deliverables.
5. Architecture safety tests prevent regressions back into large flat files.

### Architecture Review

The expanded migration must ship as multiple independently reversible PRs:

```text
PR 1: domain skeleton + architecture tests
PR 2: series router vertical slice
PR 3: series ORM facade + db model extraction
PR 4: production orchestration use cases
PR 5: production truth/status read model
PR 6: cleanup docs + migration checklist
```

Each PR must preserve `/api/series/*` behavior, keep old import paths working, run relevant tests, and be independently revertible.

The domain dependency direction is:

```text
router
  -> application/use_cases
  -> domain rules
  -> repositories/adapters
  -> legacy services or app.db.models
```

Hard dependency rules:

- `app.services.*` must not import `app.domains.ai_video_series`.
- domain rule modules must not import `fastapi`.
- routers must not contain DB query soup or long workflows.
- legacy services can only be reached through explicit `adapters/legacy_*.py` modules.
- every legacy adapter must document its exit condition.

The production status read model is a formal domain component. It must derive state from database facts, not UI optimism:

```text
Episode row
latest approved AITextArtifact
ProductionJob
VideoProductionRun
EpisodeScript / storyboard payload
episode asset scope
```

Hard status rules:

- `production_running` requires an active `VideoProductionRun` or active production job.
- `production_ready` requires script, storyboard, asset scope, and style lock readiness.
- `production_blocked` must include a named blocking reason.
- `completed` requires terminal state evidence and output evidence.

DB model extraction must keep one SQLAlchemy `Base`, keep `app/db_models.py` as a re-export facade, and avoid schema changes in the first model extraction PR.

### Error And Rescue Map

Add a `Named Error Catalog` for the `ai_video_series` domain. Approved initial names:

```text
SERIES_NOT_FOUND
EPISODE_NOT_FOUND
MISSING_EPISODE_SCRIPT
MISSING_STORYBOARD
MISSING_ASSET_SCOPE
STYLE_LOCK_NOT_READY
UNAPPROVED_TEXT_ARTIFACT
NO_ACTIVE_PRODUCTION_RUN
PRODUCTION_JOB_STALE
PRODUCTION_RUN_TERMINAL_WITHOUT_OUTPUT
DUPLICATE_ACTIVE_JOB
DUPLICATE_ACTIVE_PRODUCTION_RUN
STALE_ARTIFACT_VERSION
ARTIFACT_APPROVAL_CONFLICT
EPISODE_MUTATION_CONFLICT
AI_PROVIDER_TIMEOUT
AI_PROVIDER_RATE_LIMITED
AI_PROVIDER_BAD_RESPONSE
AI_OUTPUT_SCHEMA_INVALID
AI_OUTPUT_EMPTY
REFERENCE_ASSET_GENERATION_FAILED
ASSET_SCOPE_REFERENCE_INVALID
```

Every named error must document:

```text
trigger condition
catching layer
API status / response shape
user-visible message
developer log fields
retryability
```

Legacy adapters must translate provider and old-service exceptions into named business errors. Use cases should not know provider-specific exception details.

`PRODUCTION_JOB_STALE` and `PRODUCTION_RUN_TERMINAL_WITHOUT_OUTPUT` must render as `production_blocked`, not `production_running` or `completed`.

All job/run/artifact mutation paths must enforce backend idempotency or explicit conflict handling. UI debouncing is not sufficient.

### Security And Threat Model

Route migration requires auth parity tests for every migrated `/api/series/*` endpoint.

Security rules:

- Every migrated endpoint must preserve `verify_admin_token` or `require_role("admin")` behavior.
- Actor propagation must remain intact from token to `actor_user_id` in artifact approvals and updates.
- worker-step endpoints must require admin or stronger internal-worker authentication.
- worker-step payloads must be bound to active database jobs and legal state transitions.
- worker-step responses must not expose full prompts, provider secrets, internal stack traces, or raw provider responses.
- worker-step actions must write audit events.

`AITextArtifact` content is untrusted until it passes schema validation, latest-version validation, approval-state validation, and series/episode ownership validation. Production start must use only latest approved artifacts of the expected kind and schema version.

Observability and logs may include only whitelisted metadata:

```text
series_id
episode_id
job_id
run_id
artifact_id
actor_user_id
provider name
model name
named_error_code
blocking_reason
elapsed_ms
retry_after
```

Logs must not include authorization headers, device secrets, provider keys, full prompts, full raw AI responses, secret-bearing filesystem paths, or signed private media URLs.

### Data Flow And Interaction Edge Cases

Add a `Four-Path Data Flow Matrix` for:

```text
series story plan
style lock
episode script
storyboard
episode asset scope
start production
production status read model
```

Each flow must document:

```text
happy path
nil path
empty path
upstream error path
```

`EpisodeAssetScope` is the formal source of per-episode character and scene selection. Production start must not silently fall back to the full series asset pool.

Rules:

- missing scope => `MISSING_ASSET_SCOPE`;
- empty scope requires an explicit `scope_intentionally_empty=true`;
- unknown character or scene IDs => `ASSET_SCOPE_REFERENCE_INVALID`;
- two episodes must be able to carry different character and scene scopes.

Add an `EpisodeTextReadModel` so script and storyboard visibility is stable and does not depend on UI artifact-table guessing. It must expose script/storyboard visibility, current artifact IDs, approved artifact IDs, and stale/pending/missing state.

Repeated clicks, refreshes, back navigation, slow providers, and retry after network timeout must be absorbed by backend status derivation, idempotency, or explicit conflicts.

### Code Quality Review

New domain files must be use-case oriented. Avoid `helpers.py`, `utils.py`, `common.py`, or `misc.py` as business-logic buckets.

Target size limits:

```text
router.py <= 250 lines target
application/use_cases/* <= 300 lines target
domain/rules/* <= 300 lines target
repositories/* <= 350 lines target
single file > 500 lines requires failure, warning, or explicit waiver
endpoint function <= 40 lines target
```

Critical payloads must have typed boundaries:

```text
EpisodeAssetScope
EpisodeScriptView
EpisodeStoryboardView
ProductionReadiness
ProductionStatus
NamedBusinessError
```

Production readiness/status, episode text, and asset scope must not remain naked dictionaries across the domain boundary.

Add a `Compatibility Facade Register` for every old path retained during migration:

```text
old path
new path
why compatibility is needed
known importers/tests
allowed exported names
deprecation/removal condition
owner phase
```

Facade modules must use explicit exports, not wildcard imports, and must not accumulate new business logic.

Centralize public status, error, artifact kind, visibility, job kind, and run state names in enums or constants. API response strings are contracts and must be tested.

### Test Review

Architecture characterization tests must come before moving code.

Required architecture tests:

```text
test_series_route_auth_parity_before_after
test_series_router_is_thin_facade_after_migration
test_services_do_not_import_ai_video_series_domain
test_domain_rules_do_not_import_fastapi
test_domain_files_stay_under_size_limit
test_db_models_facade_reexports_series_models
test_single_sqlalchemy_base_metadata_survives_model_split
```

Production status/readiness matrix tests must cover:

```text
missing script
missing storyboard
missing asset scope
style lock not ready
active run
active job
stale job
terminal run without output
completed with output evidence
```

Episode text and asset scope contract tests must cover:

```text
missing/draft/approved/stale script visibility
script and storyboard artifact IDs
missing scope blocks production
empty scope requires explicit intent
unknown character/scene IDs are rejected
full series pool is not a silent fallback
two episodes can have different scopes
```

Backend concurrency/idempotency tests must cover duplicate story planning, style locking, script generation, production start, stale artifact approval, and stale episode artifact writes.

Every migration PR must run the relevant existing series and production tests plus an app import smoke test:

```text
python -c "from app.main import app; print(app.title)"
```

### Observability And Monitoring

Standardize business events for the multi-episode production chain:

```text
series.story_plan.requested
series.story_plan.completed
series.style_lock.requested
series.style_lock.completed
episode.script.requested
episode.script.completed
episode.storyboard.completed
episode.asset_scope.validated
episode.production.readiness_checked
episode.production.started
episode.production.blocked
episode.production.completed
episode.production.failed
```

Prefer the existing `ProductionAuditEvent` and `production_observability.record_production_event` path before adding new audit tables.

Add a production truth read path, either as a dedicated endpoint or as part of episode detail:

```text
GET /api/series/{series_id}/episodes/{episode_id}/production-status
```

It must return status, blocking reason, IDs/evidence, and next-action hints without sensitive content.

Track at least:

```text
blocked count by reason
stale job count
terminal run without output count
provider error count by provider/model/error
schema invalid count by artifact kind
generation duration
readiness check duration
duplicate conflict count
```

Create a developer runbook for "series/episode says production running but has no output."

### Database And State Management

No schema changes are required for the first extraction PR. Moving ORM code must not create a second `Base`, change table names, or change relationship behavior.

Use current indexes first, then measure before adding migrations. The status read model should batch-load episodes, latest artifacts, active jobs, active runs, and asset scopes to avoid N+1 query behavior.

Any new DB migrations must be separate PRs with explicit rollback notes. If a new index is needed, justify it with the status/readiness query pattern it supports.

State integrity rules:

- `ProductionJob` and `VideoProductionRun` evidence must be scoped to the same series/episode/plan.
- latest approved artifacts must match expected artifact kind, schema version, and series/episode ownership.
- `EpisodeAssetScope` references must resolve to known characters/scenes within the series.
- no production status may be derived from stale or cross-episode evidence.

### API Design And Contract

Existing `/api/series/*` paths must remain compatible. New endpoints are additive unless separately approved.

Named error responses should use a stable shape:

```json
{
  "code": "MISSING_STORYBOARD",
  "message": "Storyboard is missing.",
  "details": {}
}
```

The production status response is also a contract:

```json
{
  "status": "production_blocked",
  "blocking_reason": "MISSING_STORYBOARD",
  "evidence": {
    "script": "approved",
    "storyboard": "missing",
    "asset_scope": "valid",
    "style_lock": "ready",
    "active_job_id": null,
    "active_run_id": null
  }
}
```

Old test monkeypatch/import paths under `app.routers.series.*` must either continue to work or be migrated in a dedicated compatibility cleanup PR.

Broad rate limiting is not part of this design unless the project already has a standard mechanism. Duplicate mutation protection belongs in the backend use cases regardless of rate limiting.

### Performance And Scalability

At 10x episodes per series, the status/readiness API must avoid per-episode artifact/job/run queries. Batch queries and indexed filters are required for list views.

At 100x production jobs, stale-job detection and active-run lookup must be bounded by indexed status/target/run fields, not table scans.

Do not return full script, storyboard, prompt, or raw provider response blobs in list/status endpoints. Large content belongs in dedicated detail endpoints or artifact views.

Production status should be derived live enough to be trustworthy, but list endpoints can return compact evidence and IDs rather than hydrating every nested object.

### Design And UX

No direct UI implementation is in this backend architecture plan. The UX contract still matters:

- the UI must not infer `production_running` from a button click;
- the UI should read the production status/readiness model;
- blocked states must expose a next action;
- missing script/storyboard/scope should be visible instead of silently absent.

Any frontend changes should be a later PR consuming the stable read models rather than adding UI-specific inference.

### CEO Review Summary

Strongest challenges:

1. Scope expansion is justified, but only if delivered through small reversible PRs.
2. "Production running" must become a derived fact with evidence, not a loose status label.
3. Compatibility facades are necessary, but they need explicit exit conditions or they will become permanent debt.

Recommended path:

1. Update the implementation plan to include this expanded scope.
2. Start with skeleton, dependency tests, auth parity characterization, and facade register.
3. Move series route use cases next, then model facade, then production truth/status, then cleanup.

Accepted scope:

- `ai_video_series` vertical slice;
- series ORM extraction behind `app.db.models.*`;
- production orchestration use cases and legacy adapters;
- production truth/status read model;
- architecture, auth, status, asset scope, idempotency, and compatibility tests;
- observability events and runbook.

Deferred:

- full device/content/account modularization;
- full `video_production_service.py` rewrite;
- schema-changing DB migrations unless justified separately;
- frontend UI implementation;
- broad platform-wide rate limiting.

Not in scope:

- public API path renames;
- table renames;
- Clean Architecture rewrite of the whole server in one PR;
- removal of old import paths before compatibility cleanup PRs.

## Plan CEO Review Report

Status: DONE_WITH_CONCERNS.

Mode: `SCOPE EXPANSION`.

Selected approach: `C`, ideal architecture migration.

Decision basis: the user selected `C` during the CEO review flow and then granted approval for remaining review decisions. The current invocation of `/plan-ceo-review` uses that approval to avoid repeated gates in this non-plan-mode environment.

CEO plan snapshot: `C:\Users\szm\.gstack\projects\dy_auto_new\ceo-plans\2026-06-18-server-business-modularization.md`.

Outside voice: unavailable. `codex.exe` exists but failed with `Access is denied`; subagent review was not run because the current tool policy only permits spawning agents after an explicit user request for delegation/subagents.

### System Audit

Base branch: `main`.

Current branch: `codex/bailian-high-quality-video-pipeline`.

Recent history shows this branch is already deep into AI video production work:

- `feat: generate episode asset scopes during story planning`;
- `feat: normalize episode asset scope`;
- `feat: persist dramatic script outputs`;
- `feat: add dramatic script pipeline`;
- `refactor: migrate app models to package`;
- multiple design specs for story generation, storyboard frames, continuity artifacts, and episode asset scope.

Current diff against `main` is very large: about 209 files and more than 30k insertions. This makes "big-bang ideal architecture" dangerous unless split into independently reversible PRs.

No git stashes were found.

No root `TODOS.md` exists. Deferred work must therefore be written into this spec or a deliberately created follow-up plan, not assumed to exist elsewhere.

Recent hot files relevant to this plan:

- `server/app/routers/series.py`;
- `server/app/db_models.py`;
- `server/app/services/video_production_service.py`;
- `server/app/services/production_run_service.py`;
- `server/app/routers/video_production.py`;
- `web/src/views/SeriesDetailPage.vue`.

The audit reinforces the central thesis: the AI video series workflow is now spread across routers, services, ORM, tests, and UI read models. A domain slice is justified, but only with tight compatibility gates.

### Landscape Synthesis

Layer 1, tried and true:

- FastAPI's official "bigger applications" guidance supports splitting applications with `APIRouter` and submodules instead of one giant route file.
- SQLAlchemy supports organizing mapped classes across modules, but metadata and declarative base identity must remain coherent.
- Bounded-context/domain modularization works best when it owns business language, not just physical folders.

Layer 2, current ecosystem signal:

- The common pattern for Python web monoliths is a modular monolith: keep one deployable service, but create domain-oriented packages with clear import direction.
- The risky pattern is an overzealous clean architecture rewrite where every old service is split at once and compatibility breaks.

Layer 3, first principles:

- This project does not need a purity rewrite. It needs production truth: every episode should be able to prove whether script, storyboard, asset scope, style lock, job, and run evidence exist.
- The best architecture is therefore a vertical slice around `ai_video_series`, not a global restructure of the whole server.

### Step 0: Nuclear Scope Challenge

Premise check:

1. The right problem is maintainability plus production diagnosability, not only folder organization.
2. The real user outcome is trust in multi-episode production: users should know whether a series is actually producing, blocked, completed, or missing artifacts.
3. Doing nothing means continued ambiguity: "production running" can remain disconnected from active jobs/runs, scripts/storyboards can be generated but invisible, and each episode can accidentally share broad series-level asset defaults.

Existing code leverage:

- keep existing `/api/series/*` paths;
- keep existing `ProductionAuditEvent` and `production_observability.record_production_event`;
- keep existing services behind `legacy_*` adapters;
- keep `app/db_models.py` as a facade;
- keep existing tests as compatibility characterization tests.

Dream state:

```text
CURRENT STATE
  large route/service/model files, mixed responsibilities, unclear production truth
    ->
THIS PLAN
  ai_video_series vertical slice with compatibility facades and status evidence
    ->
12-MONTH IDEAL
  main business domains own their routes, use cases, data access, status read models, errors, and observability
```

Implementation alternatives:

```text
APPROACH A: Minimal Boundary Guard
Effort: S
Risk: Low
Completeness: 4/10
Pros: fastest; protects direction with tests.
Cons: leaves series production truth and service complexity mostly untouched.
Reuses: all existing router/service/model code.

APPROACH B: Route-Layer Domain Migration
Effort: M
Risk: Medium
Completeness: 7/10
Pros: directly thins series.py; preserves public behavior.
Cons: can become a directory-only move if status/readiness/model boundaries stay vague.
Reuses: existing services, ORM, tests, paths.

APPROACH C: AI Video Series Vertical Slice
Effort: L/XL
Risk: Medium-High
Completeness: 9/10
Pros: addresses router, model ownership, production truth, errors, tests, and observability together.
Cons: must be split into small PRs or it becomes a rewrite.
Reuses: existing services as adapters, db_models facade, audit event path, test suite.
```

Recommendation: Approach C is the right target because the user pain is not merely "files are crowded"; it is "the system cannot convincingly explain each episode's production state."

### Expanded Scope

Accepted additions:

- `ai_video_series` vertical slice;
- series ORM boundary through `app.db.models.*` with `app/db_models.py` re-export facade;
- production orchestration use cases and `legacy_*` adapters;
- production truth/status read model;
- episode text read model;
- episode asset scope as the per-episode character/scene source;
- named error catalog;
- auth parity and actor propagation tests;
- architecture safety harness;
- production audit events, metrics, and runbook.

### Architecture Review

Required architecture:

```text
app.domains.ai_video_series.router
  -> application/use_cases
  -> domain/rules
  -> repositories
  -> app.db.models.*

application/use_cases
  -> adapters/legacy_*.py
  -> existing app.services.*
```

Before/after dependency graph:

```text
BEFORE
main.py -> routers/series.py -> db_models.py
                          |-> series_planning_service.py
                          |-> production_run_service.py
                          |-> ai_text_artifact_service.py
                          |-> agency/video services

AFTER
main.py -> routers/series.py facade -> domains/ai_video_series/router.py
                                      -> application/use_cases/*
                                      -> domain/*
                                      -> repositories/*
                                      -> adapters/legacy_*.py -> old services
                                      -> app.db.models.* -> db_models facade for old importers
```

Rollback posture:

- PR 1 skeleton/tests can be reverted without behavior change.
- PR 2 route slice can be reverted by restoring the old router import surface.
- PR 3 model extraction must be schema-neutral and preserve one `Base`.
- PR 4 production use cases must keep old service public entrypoints.
- PR 5 status read model is additive unless a current endpoint shape is explicitly approved to change.

Critical architecture gate: no PR may combine route migration, ORM extraction, and production orchestration split in one diff.

### Error And Rescue Map

The named error catalog from the OpenClaw review is accepted. `/plan-ceo-review` adds two implementation constraints:

1. every named error needs a concrete Python exception/type or domain error object, not just a string;
2. legacy adapters are the only layer allowed to translate provider-specific exceptions.

Rescue table template:

```text
CODEPATH                     | WHAT CAN GO WRONG                    | DOMAIN ERROR
-----------------------------|--------------------------------------|------------------------------
start_episode_production     | no approved script                   | MISSING_EPISODE_SCRIPT
start_episode_production     | no approved storyboard               | MISSING_STORYBOARD
start_episode_production     | no valid episode scope               | MISSING_ASSET_SCOPE
status_read_model            | active job stopped updating          | PRODUCTION_JOB_STALE
status_read_model            | terminal run lacks output            | PRODUCTION_RUN_TERMINAL_WITHOUT_OUTPUT
generate_episode_script      | provider timeout                     | AI_PROVIDER_TIMEOUT
generate_episode_script      | provider malformed output            | AI_OUTPUT_SCHEMA_INVALID
approve_artifact             | not latest version                   | STALE_ARTIFACT_VERSION
```

User-visible rule: status endpoints should return `production_blocked` with `blocking_reason`; mutation endpoints should return a stable error response with `code`, `message`, and `details`.

### Security And Threat Model

Threats:

```text
THREAT                                  | LIKELIHOOD | IMPACT | MITIGATION
----------------------------------------|------------|--------|-------------------------------
Migrated route loses auth dependency    | Medium     | High   | auth parity route tests
Worker-step endpoint advances fake job  | Medium     | High   | job_id/series_id active binding
Artifact prompt injection leaks forward | Medium     | High   | schema/latest/approval checks
Cross-episode artifact reuse            | Medium     | High   | ownership validation
Sensitive prompt/provider data in logs  | Medium     | Medium | log field whitelist
```

No new secrets should be introduced by the architecture migration. If a worker secret is later added, it must be env-based and rotatable.

### Data Flow And Interaction Edge Cases

Production readiness flow:

```text
episode_id
  -> load episode and series
  -> load latest approved script/storyboard artifacts
  -> load episode asset scope
  -> load style lock evidence
  -> load active job/run evidence
  -> derive status + blocking_reason + evidence
```

Shadow paths:

```text
nil episode_id          -> EPISODE_NOT_FOUND
empty script            -> MISSING_EPISODE_SCRIPT
empty storyboard        -> MISSING_STORYBOARD
empty scope             -> MISSING_ASSET_SCOPE unless intentionally empty
provider failure        -> AI_PROVIDER_* or AI_OUTPUT_* domain error
stale artifact          -> STALE_ARTIFACT_VERSION
duplicate active job    -> DUPLICATE_ACTIVE_JOB
```

Interaction rule: frontend clicks, refreshes, or retries must not be the source of truth. Backend status read model is the source of truth.

### Code Quality Review

The new domain must avoid "new big file" failure.

Required module shape:

```text
domains/ai_video_series/
  router.py
  application/
  domain/
  repositories/
  adapters/
  schemas.py
```

Quality gates:

- no `helpers.py`, `utils.py`, `misc.py`, or wildcard re-export buckets for business logic;
- endpoint functions target 40 lines or less;
- single files over 500 lines require a failed/warning boundary test or explicit waiver;
- typed boundaries for production status, readiness, episode text, asset scope, and domain errors;
- compatibility facade register must stay current.

### Test Review

The test plan is mandatory, not polish.

Required groups:

```text
Architecture:
  import direction
  FastAPI-free domain rules
  thin series router facade
  single SQLAlchemy Base
  db_models re-export compatibility

Behavior:
  /api/series/* response compatibility
  old monkeypatch/import paths
  script/storyboard read visibility
  episode-specific asset scope

Truth/status:
  running requires active job/run evidence
  blocked always includes reason
  completed requires output evidence
  stale job is blocked
  terminal run without output is blocked

Concurrency:
  duplicate active job/run
  stale artifact version
  artifact approval conflict
```

Do not add external-provider-dependent tests for provider behavior. Use deterministic adapters/fakes.

### Performance Review

Performance risks:

- status list views can become N+1 query farms if every episode separately loads artifacts, jobs, runs, scopes, and style lock evidence;
- large storyboard/script blobs can bloat list responses;
- stale-job detection can become a table scan without indexed status/target filters;
- production status polling can increase database pressure.

Mitigations:

- batch-load status evidence for series detail/list views;
- return compact status evidence and artifact IDs in list/status endpoints;
- keep full script/storyboard payload behind detail/artifact reads;
- prefer existing indexes first, then add separate migration PRs only if query review proves need;
- cache only derived read models that can tolerate short staleness, not production mutation decisions.

### Observability And Debuggability Review

Use existing `ProductionAuditEvent` and `record_production_event` unless a later PR proves they cannot support required metadata.

Day-1 observability:

- `episode.production.readiness_checked`;
- `episode.production.blocked`;
- `episode.production.started`;
- `episode.production.completed`;
- `episode.production.failed`;
- counts by `blocking_reason`;
- counts by provider error code/model;
- stale-job and terminal-run-without-output counts;
- runbook for "production running but no output."

Debugging expectation: with `series_id` and `episode_id`, a developer should reconstruct script/storyboard/scope/status/job/run evidence without reading raw prompts or provider responses.

### Deployment And Rollout Review

Rollout order:

```text
1. skeleton and non-invasive tests
2. compatibility facade register
3. route slice behind old router import
4. schema-neutral ORM extraction
5. use case/adapters migration
6. additive status endpoint/read model
7. frontend consumption in a later PR
8. cleanup and facade retirement
```

Deployment rules:

- no schema-changing migration in the first ORM extraction PR;
- no table rename;
- no public API path rename;
- no facade deletion in the same PR that introduces the new path;
- app import smoke test after every migration PR;
- if a PR changes endpoint response shape, it needs a separate API contract approval.

Rollback:

- route migration can roll back by restoring the old `app.routers.series` implementation;
- model extraction rolls back through re-export facade if no schema changed;
- status endpoint is additive and can be disabled/ignored without breaking old flows.

### Long-Term Trajectory Review

Reversibility rating:

- PR 1 skeleton/tests: 5/5;
- PR 2 route slice: 4/5 if facade remains;
- PR 3 model extraction: 3/5 because metadata/import behavior is sensitive;
- PR 4 production use cases: 3/5 because it touches orchestration;
- PR 5 status truth layer: 4/5 if additive.

The plan creates platform value if done correctly:

- `ProductionStatusReadModel` can later serve frontend, QA, admin diagnostics, and monitoring.
- `Named Error Catalog` can unify API behavior across production flows.
- `Compatibility Facade Register` gives the repo a reusable migration pattern for future domains.

Path dependency risk: if the first domain is sloppy, it becomes the template for every future domain. The first implementation must be boringly strict.

### Design And UX Review

No direct UI implementation is in this backend plan, but the API contract determines the eventual UX.

User-visible state model:

```text
Series detail
  -> episode row
    -> text visibility: missing | draft | pending_approval | approved | stale
    -> asset scope: missing | invalid | valid | intentionally_empty
    -> production status: ready | running | blocked | completed | failed
    -> next action: generate script | approve storyboard | fix scope | restart run | inspect failure
```

The frontend must not infer production state from a button click. It should render the backend status/readiness model and show missing/blocked reasons explicitly.

Recommended later skill: run `/plan-design-review` only when a frontend implementation plan exists. This backend spec does not yet define UI layout, responsive behavior, or accessibility details.

### Final CEO Verdict

Verdict: proceed with expanded scope, but only as a sequence of guarded PRs.

Strongest risks:

1. The expanded plan is too large for one implementation branch.
2. `production_running` can remain untrustworthy unless derived from active job/run evidence.
3. Compatibility facades can become permanent unless tracked and retired.
4. Status/readiness endpoints can become slow without batched evidence loading.
5. ORM extraction can break metadata if a second `Base` appears.

Recommended next action:

Convert this review into an implementation plan with PR-sized tasks. The first task should not move business logic. It should create the domain skeleton, facade register, boundary tests, auth parity characterization, and app import smoke test.

## Autoplan Full Review Pipeline Report

Status: DONE_WITH_CONCERNS.

Mode: automatic review pipeline with auto-decisions.

Plan file: `docs/superpowers/specs/2026-06-17-server-business-modularization-design.md`.

Restore point: `C:\Users\szm\.gstack\projects\dy_auto_new\codex-bailian-high-quality-video-pipeline-autoplan-restore-20260618-102658.md`.

Eng test plan artifact: `C:\Users\szm\.gstack\projects\dy_auto_new\szm-codex-bailian-high-quality-video-pipeline-eng-review-test-plan-20260618-102839.md`.

Codex voice: unavailable. `codex.exe` exists but returns `Access is denied`.

Subagent voice: unavailable in this run because the current tool policy only permits spawned agents after an explicit user request for delegation/subagents.

### Phase 0: Intake

Base branch: `main`.

Current branch: `codex/bailian-high-quality-video-pipeline`.

UI scope: skipped. The plan contains UI/UX words only in negative scope and API-contract context. It does not specify a frontend component, layout, view, modal, dialog, or responsive implementation.

DX scope: enabled. The plan changes developer-facing server organization, imports, route ownership, compatibility facades, error contracts, test commands, and debugging/onboarding paths.

Loaded review skills:

- `plan-ceo-review`;
- `plan-eng-review`;
- `plan-devex-review`.

`plan-design-review` was not run because the direct UI scope detector was treated as false-positive after inspecting the plan content.

System audit:

- `server/app/routers/series.py` contains the main series API surface and worker-step endpoints.
- `server/app/db_models.py` contains `ProductionJob`, `AITextArtifact`, `ProductionAuditEvent`, `EpisodeScript`, and `VideoProductionRun`.
- `server/app/services/production_run_service.py` owns `generate_episode_script_storyboard` and `start_episode_production`.
- `server/app/services/production_observability.py` already exposes `record_production_event`.
- Existing tests cover many series, style lock, artifact, scope, and production-start contracts, but not the new architecture boundary and derived status/readiness matrix.

### Phase 1: CEO Review

Premise gate: passed from prior explicit approvals. The user selected approach `C` and later approved remaining review decisions.

Premises:

| Premise | Assessment | Decision |
|---|---|---|
| The real problem is maintainability plus production diagnosability | Supported by large route/service/model hotspots and user reports about invisible scripts/storyboards and unclear production state | Accept |
| `ai_video_series` is the first domain | Supported by `series.py`, production start, artifact, story planning, style lock, and episode asset scope evidence | Accept |
| The ideal architecture target is justified | Supported, but only with multi-PR rollout | Accept with guard |
| Public `/api/series/*` paths and old imports must stay compatible | Required by existing tests and `app.main` imports | Accept |
| Production status must be derived from evidence | Required to answer whether "production running" is true | Accept |

What already exists:

| Sub-problem | Existing code to reuse |
|---|---|
| Series routes and auth dependencies | `server/app/routers/series.py` |
| Story planning | `server/app/services/series_planning_service.py` |
| Episode asset scope normalization | `server/app/services/episode_asset_scope_service.py` |
| Production start | `server/app/services/production_run_service.py` |
| Production error codes | `server/app/services/production_errors.py` |
| Production audit events | `server/app/services/production_observability.py`, `ProductionAuditEvent` |
| Artifact approval/versioning | `server/app/services/ai_text_artifact_service.py`, `server/app/routers/ai_text_artifacts.py` |
| Existing compatibility tests | `test_series_api.py`, `test_series_style_lock_pipeline.py`, `test_video_production_start_flow_contract.py` |

Dream state delta:

```text
CURRENT
  series router, db_models, and production services mix business concerns
    ->
THIS PLAN
  ai_video_series owns router/use cases/rules/read models with compatibility facades
    ->
12-MONTH IDEAL
  each high-change business area has a domain home, stable read models, named errors, and migration-safe facades
```

Implementation alternatives:

| Approach | Effort | Risk | Completeness | Decision |
|---|---:|---:|---:|---|
| A. Minimal boundary guard | S | Low | 4/10 | Rejected. Too little improvement for current production ambiguity. |
| B. Route-layer domain migration | M | Medium | 7/10 | Rejected as final target. Good intermediate PR, but incomplete as end state. |
| C. AI video series vertical slice | L/XL | Medium-High | 9/10 | Accepted. Best match for user goal when split into small reversible PRs. |

CEO dual voices consensus:

```text
Dimension                            Claude  Codex  Consensus
1. Premises valid?                   N/A     N/A    single-reviewer
2. Right problem to solve?           N/A     N/A    single-reviewer
3. Scope calibration correct?        N/A     N/A    single-reviewer
4. Alternatives sufficiently explored?N/A    N/A    single-reviewer
5. Competitive/market risks covered? N/A     N/A    single-reviewer
6. 6-month trajectory sound?         N/A     N/A    single-reviewer
```

CEO completion summary:

- strongest challenge: scope is now large enough to fail if implemented as one PR;
- recommendation: keep expanded scope but enforce PR gates;
- accepted scope: vertical slice, ORM facade, orchestration adapters, production truth, automated safety harness;
- not in scope: public API renames, table renames, full server rewrite, immediate frontend implementation.

Phase 1 complete. Codex: unavailable. Claude subagent: unavailable. Consensus: single-reviewer mode.

### Phase 2: Design Review

Skipped. No direct UI implementation is in this plan.

The backend API contract still affects UX, so the plan keeps these constraints:

- UI must not infer `production_running` from a click;
- UI should consume status/readiness read models;
- blocked states must expose next action and evidence;
- frontend implementation should be a later PR after backend contracts stabilize.

Phase 2 complete. Design skipped due backend-only implementation scope.

### Phase 3: Engineering Review

Scope challenge:

- Complexity is high by design, but the PR sequence makes the risk manageable.
- The first PR must not move behavior. It should create skeleton, facade register, boundary tests, auth parity characterization, and app import smoke.
- Route migration, ORM extraction, and production orchestration split must not be combined in one PR.

Architecture diagram:

```text
app.main
  -> app.routers.series                  (thin facade after PR 2)
       -> app.domains.ai_video_series.router
            -> application/use_cases
                 -> domain/rules
                 -> repositories
                      -> app.db.models.*
                 -> adapters/legacy_*.py
                      -> existing app.services.*

old importers
  -> app.routers.series.*                (compat re-exports during migration)
  -> app.db_models.*                     (compat re-exports during model extraction)
```

Test diagram:

```text
NEW CODEPATHS / FLOWS                                     COVERAGE DECISION
domain skeleton imports                                   architecture unit tests
series router facade                                      existing series API tests + facade thinness test
domain rules without FastAPI                              import boundary tests
services no reverse-import                                import boundary tests
db model extraction                                       single Base + db_models facade tests
production status read model                              new readiness/status matrix tests
episode text read model                                   new API/read-model contract tests
episode asset scope as per-episode truth                  existing scope tests + no-fallback tests
legacy adapters                                           unit tests with deterministic fake services
provider error translation                                adapter tests for timeout/rate/schema/empty
duplicate job/run handling                                backend idempotency/conflict tests
auth parity                                               route dependency snapshot tests
```

Current coverage leverage:

- `test_series_api.py` already covers create/get/list/update/delete, auth, story plan jobs, active video runs, linked assets, and episode asset scope.
- `test_series_style_lock_pipeline.py` covers style-lock worker behavior, progress, stale/recovery, duplicate active jobs, and saved storyboard flows.
- `test_video_production_start_flow_contract.py` covers missing storyboard/script generation, missing scope blocking, unlinked asset IDs, text artifact approval gates, and approved storyboard input.
- `test_ai_text_artifacts_api.py` covers artifact auth and stale version approval conflict.
- `test_episode_asset_scope_service.py` covers normalization and invalid linked asset IDs.

Critical test gaps to add:

| Gap | Test requirement |
|---|---|
| Derived production status | Matrix tests for missing script/storyboard/scope/style lock, active job/run, stale job, terminal run without output, completed with output |
| Architecture boundary | Tests for no reverse service imports, no FastAPI in domain rules, thin series router, file size thresholds |
| Auth parity | Snapshot migrated `/api/series/*` endpoints and dependencies before/after migration |
| Compatibility facades | Tests for explicit re-export names and old monkeypatch paths |
| ORM extraction | Tests for single `Base`, metadata survival, `app/db_models.py` re-exports |
| Legacy adapters | Tests translating old service/provider exceptions into named domain errors |
| Episode text visibility | Tests for missing/draft/pending/approved/stale states and artifact IDs |

Performance review:

- The status read model can become an N+1 query source if list endpoints load evidence per episode. Auto-decision: require batched evidence loading.
- Full script/storyboard blobs can bloat list responses. Auto-decision: list/status endpoints return compact status and artifact IDs only.
- Stale job detection can table-scan. Auto-decision: use existing indexes first; add index migrations only in separate PRs after query review.
- Production status polling can pressure DB. Auto-decision: keep read model compact and avoid hydrating nested objects in list views.

Eng dual voices consensus:

```text
Dimension                            Claude  Codex  Consensus
1. Architecture sound?               N/A     N/A    single-reviewer
2. Test coverage sufficient?         N/A     N/A    single-reviewer
3. Performance risks addressed?      N/A     N/A    single-reviewer
4. Security threats covered?         N/A     N/A    single-reviewer
5. Error paths handled?              N/A     N/A    single-reviewer
6. Deployment risk manageable?       N/A     N/A    single-reviewer
```

Failure modes registry:

| Failure mode | Severity | Mitigation |
|---|---:|---|
| New domain becomes a second large file | High | file-size boundary tests and use-case modules |
| Router migration drops auth | High | auth parity tests |
| ORM extraction creates second SQLAlchemy Base | High | single Base tests and no schema migration in first model PR |
| Status says running without active job/run | High | production status matrix tests |
| Episode scope falls back to full series pool | High | explicit missing-scope blocking tests |
| Old monkeypatch/import paths break silently | Medium | compatibility facade register and tests |
| Status endpoint becomes slow | Medium | batched evidence loading |
| Provider raw errors leak to users/logs | Medium | legacy adapter named error translation and log whitelist |

Phase 3 complete. Codex: unavailable. Claude subagent: unavailable. Consensus: single-reviewer mode.

### Phase 3.5: DX Review

Product type: internal API/service architecture and developer-facing modularization plan.

Persona: backend engineer or AI coding agent implementing the next server feature.

Developer empathy narrative:

```text
I open the plan because I need to add or debug a multi-episode AI video feature.
Today I have to inspect `routers/series.py`, `db_models.py`, production services, artifact services, and tests to understand one episode's script/storyboard/status path.
With the reviewed plan, I should start in `app/domains/ai_video_series`, find the use case, follow named errors and read models, then run a small set of documented tests.
If the facade register and runbook are missing, I still have to guess which old path is real.
```

TTHW assessment:

- Current: 20-30 minutes for a new contributor to identify where to add series production logic safely.
- Target: 5-8 minutes after skeleton, README/domain doc, facade register, and test command checklist.

DX scorecard:

| Dimension | Score | Finding | Auto-decision |
|---|---:|---|---|
| Getting started | 6/10 | README explains repo but not domain migration entrypoint | Add `ai_video_series/README.md` in PR 1 |
| API/interface design | 8/10 | Named errors/read models are strong; response examples need exact schemas | Add schema examples beside DTOs |
| Error/debugging | 9/10 | Named error catalog and status evidence are strong | Keep problem/cause/fix shape |
| Documentation/learning | 7/10 | Spec is rich but too long for implementers | Add migration checklist and facade register |
| Upgrade/migration | 8/10 | Compatibility facades and PR gates reduce fear | Require deprecation/removal conditions |
| Developer tooling | 7/10 | Test commands exist but need one canonical command block | Add per-PR verification checklist |
| Ecosystem/community | N/A | Internal project, not external SDK | No action |
| Measurement/feedback | 7/10 | Status/debuggability metrics planned | Add review-ready runbook and post-implementation `/devex-review` target |

DX implementation checklist:

- Add `server/app/domains/ai_video_series/README.md` in PR 1.
- Add a facade register table in the spec or `docs/architecture/`.
- Add exact response examples for production status and episode text read models.
- Add "where do I add new series logic?" guidance.
- Add "how do I debug production running with no output?" runbook.
- Add one canonical verification command block per PR.
- Add compatibility cleanup checklist before removing facades.

DX dual voices consensus:

```text
Dimension                            Claude  Codex  Consensus
1. Persona correct?                  N/A     N/A    single-reviewer
2. Getting started sufficient?       N/A     N/A    single-reviewer
3. API/interface ergonomic?          N/A     N/A    single-reviewer
4. Error messages actionable?        N/A     N/A    single-reviewer
5. Documentation complete?           N/A     N/A    single-reviewer
6. TTHW target credible?             N/A     N/A    single-reviewer
```

Phase 3.5 complete. DX overall: 7.4/10. TTHW: 20-30 min -> 5-8 min.

### Cross-Phase Themes

Theme: production truth. CEO, Eng, and DX all converge on the same core: the system must prove whether an episode is ready, running, blocked, or complete.

Theme: compatibility with exit conditions. CEO and Eng both flag that facades are necessary but dangerous if they become permanent.

Theme: first PR must be non-behavioral. CEO, Eng, and DX all point to skeleton/tests/docs first.

Theme: existing assets should be reused. Eng and DX both favor existing tests, `ProductionAuditEvent`, `record_production_event`, and old services as adapters.

### Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | Phase 0 | Treat UI scope as skipped | Mechanical | Explicit over clever | Plan has UI words only in negative/API-contract context, not UI implementation | Running design review on backend-only work |
| 2 | Phase 0 | Enable DX review | Mechanical | Choose completeness | Imports, APIs, docs, tests, and debugging paths are developer-facing | Skipping developer experience review |
| 3 | Phase 0 | Degrade Codex voice to unavailable | Mechanical | Bias toward action | `codex.exe` returns Access denied | Blocking on Codex CLI |
| 4 | Phase 0 | Degrade subagent voice to unavailable | Mechanical | Explicit over clever | Current tool policy requires explicit user delegation/subagent request | Violating tool policy |
| 5 | Phase 1 | Accept prior premise approvals | Mechanical | Bias toward action | User already selected C and approved remaining review decisions | Re-asking the same premise gate |
| 6 | Phase 1 | Keep Approach C as target | Taste | Choose completeness | It solves maintainability and production diagnosability together | Reducing to route-only move |
| 7 | Phase 1 | Enforce multi-PR rollout | Mechanical | Explicit over clever | Huge branch diff makes one-shot migration unsafe | One large ideal-architecture PR |
| 8 | Phase 3 | Require skeleton/tests first | Mechanical | Pragmatic | Keeps first PR behavior-neutral and reversible | Moving business logic first |
| 9 | Phase 3 | Require batched status evidence loading | Mechanical | Boil lakes | Prevents N+1 status/readiness reads | Per-episode lazy evidence queries |
| 10 | Phase 3 | Write root `TODOS.md` for deferred scope | Mechanical | Explicit over clever | Autoplan requires deferred work to be written down and no root TODO existed | Leaving deferrals only implicit |
| 11 | Phase 3.5 | Add domain README/checklist to PR 1 | Mechanical | Choose completeness | Reduces implementer TTHW from 20-30 minutes toward 5-8 minutes | Relying on long spec only |

### Final Gate

No user challenges were detected. The plan's direction remains the user's approved direction.

Taste choices:

- Approach C remains accepted. Approach B is still viable as an intermediate PR, but not as the final target.
- Root `TODOS.md` was introduced deliberately to satisfy autoplan's deferred-work requirement.

Auto-decided decisions: 11. See Decision Audit Trail above.

Review scores:

- CEO: passed with concerns about scope size and rollout discipline.
- Design: skipped, no direct UI scope.
- Eng: passed with required test and performance gates.
- DX: 7.4/10, target TTHW 5-8 minutes.

Verdict: APPROVED AS-IS under the user's prior blanket approval, with the hard requirement that implementation begins with a behavior-neutral skeleton/test/docs PR.

## Plan CEO Review Recheck After Autoplan

Status: DONE.

Date: 2026-06-18.

Purpose: post-`/autoplan` CEO recheck of the finalized review artifact. This review does not reopen previously approved scope decisions unless the autoplan output created a new strategic contradiction.

### CEO Verdict

No new scope change is recommended.

The plan is now strategically coherent:

- the user-approved direction remains `Approach C`, an `ai_video_series` vertical slice;
- `/autoplan` added the missing execution discipline: restore point, phase sequencing, engineering test plan, DX checklist, root `TODOS.md`, and review status table;
- deferred work is now explicit instead of implicit;
- first implementation is clearly behavior-neutral: skeleton, tests, facade register, docs, and smoke checks before moving business logic.

### New CEO Finding

The biggest risk is no longer under-reviewing the plan. The biggest risk is review drag.

The spec now contains:

- original design;
- OpenClaw CEO review;
- Plan CEO review;
- Autoplan CEO/Eng/DX pipeline;
- test plan artifact;
- root deferred-scope TODOs.

Another planning pass is unlikely to improve the implementation. It is more likely to add duplicate prose and make the plan harder for an implementer to scan.

Auto-decision: stop expanding review scope and move to PR-sized implementation planning.

Principle: bias toward action after sufficient review.

### CEO Recheck Gates

Proceed only if PR1 stays narrow:

```text
PR1 allowed:
  - server/app/domains/__init__.py
  - server/app/domains/ai_video_series/__init__.py
  - server/app/domains/ai_video_series/README.md
  - architecture/boundary tests
  - auth parity characterization
  - facade register docs
  - app import smoke command documentation

PR1 not allowed:
  - moving route behavior
  - splitting db_models.py
  - changing /api/series/* response shape
  - changing production run behavior
  - changing frontend UI
```

### Decision

CEO recheck approves the plan as ready for implementation planning.

Recommended next step: create the PR1 implementation plan, then start with tests and skeleton only.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 3 | DONE | Approach C accepted; recheck found no new scope, PR1 must stay narrow |
| Codex Review | `codex exec/review` | Independent second opinion | 0 | UNAVAILABLE | `codex.exe` returned Access denied |
| Eng Review | `/plan-eng-review` via `/autoplan` | Architecture & tests | 1 | DONE_WITH_CONCERNS | Boundary tests, status matrix, batching, facade register required |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | SKIPPED | No direct frontend implementation scope |
| DX Review | `/plan-devex-review` via `/autoplan` | Developer experience gaps | 1 | DONE_WITH_CONCERNS | DX 7.4/10, TTHW 20-30 min -> 5-8 min target |

- UNRESOLVED: no blocking user challenges; known concerns are encoded as hard implementation gates.
- VERDICT: CEO + ENG + DX CLEARED FOR PLANNING. Implementation should start with the skeleton/tests/docs PR.

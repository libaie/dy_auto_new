# Director Planning Domain Design

## Goal

Move the legacy `/api/director/*` director workshop router into a business-domain
package without changing route behavior, storyboard generation helpers,
production-plan compatibility routes, or existing monkeypatch imports.

## Approved Approach

Use the established facade-first migration pattern:

1. Create `app.domains.director_planning`.
2. Move the current `app.routers.director` implementation to
   `app.domains.director_planning.director_router` in `director_router.py`.
3. Replace `app.routers.director` with a thin `sys.modules` compatibility
   facade pointing at the domain router module.
4. Wire `app.main` directly to `director_router.router`.

## Ownership Boundary

`app.domains.director_planning` owns:

- `POST /api/director/auto-plan`
- `POST /api/director/episode-production-plan`
- `POST /api/director/episode-plan`
- `POST /api/director/shot-segments`
- `POST /api/director/plan`
- Request models `DirectorScene`, `DirectorPlanRequest`,
  `DirectorAutoPlanRequest`, `EpisodeProductionPlanRequest`,
  `EpisodePlanRequest`, and `ShotSegmentsRequest`
- Storyboard generation helpers such as `generate_auto_storyboard`,
  `_normalize_auto_frames`, `_parse_frames_json`, `_duration_chunks`,
  `_fallback_auto_plan_frames`, and `_record_director_storyboard_artifacts`
- Route-local timeout constants and agency-review wrappers

`app.domains.director_planning` does not own:

- `Episode`, `Series`, or production ORM models in `app.db_models`.
- DB session construction in `app.database`.
- Auth dependencies in `app.deps`.
- AI generation implementation in `app.services.ai_generator`.
- Expert-review orchestration in `app.services.agency_orchestrator`.
- AI text artifact persistence internals in
  `app.services.ai_text_artifact_service`.
- Production plan row construction in `app.services.production_plan_service`.
- Pipeline execution, video rendering, or style-lock ownership.

## Compatibility Contract

The migration must preserve:

- Route paths, methods, names, dependency names, and response shapes.
- Current `POST /api/director/auto-plan` persistence behavior, including
  `Episode.storyboard_json`, agency trace, and AI text artifacts.
- Existing `POST /api/director/episode-production-plan` compatibility route.
- Existing tests that import `app.routers.director._normalize_auto_frames`.
- Existing tests that monkeypatch `app.routers.director.ai_generator`,
  `AgencyOrchestrator`, and director timeout constants.
- Current route-local helper names.

## Testing Strategy

Add boundary tests that fail before the move and pass after domain wiring:

- Spec and plan mention the domain, facade, route prefix, request models,
  `generate_auto_storyboard`, `_normalize_auto_frames`, and
  `AITextArtifactService`.
- Domain package exports `DOMAIN_NAME` and `PUBLIC_ROUTE_PREFIX`.
- Domain README documents facade and cleanup gates.
- Legacy `app.routers.director` is a thin `sys.modules` facade.
- Legacy and domain imports resolve to the same module object.
- Router snapshot matches the five existing `/api/director/*` routes.
- FastAPI route table uses `app.domains.director_planning.director_router`
  endpoint modules.

Run existing director episode-plan, shot-segment, production-plan, and
style-lock auto-plan tests after migration.

## Cleanup Gates

Do not remove `app.routers.director` until all of these are true:

- `app.main` imports `director_router` from `app.domains.director_planning`.
- Route/auth snapshots pass against the domain endpoint module.
- Existing director and style-lock auto-plan tests pass.
- Import inventory shows no unapproved production imports of
  `app.routers.director`.
- Tests that monkeypatch the legacy module path are either updated or
  intentionally kept compatible through the alias phase.

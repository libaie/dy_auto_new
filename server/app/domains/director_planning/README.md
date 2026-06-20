# Director Planning Domain

This domain owns director workshop and episode production planning routes.

## Owned Routes

- `/api/director/*`

## Not Owned

- `Episode`, `Series`, and production ORM model definitions stay in
  `app.db_models`.
- Database session helpers stay in `app.database`.
- Auth dependencies stay in `app.deps`.
- AI generation stays in `app.services.ai_generator`.
- Agency review orchestration stays in `app.services.agency_orchestrator`.
- AI text artifact persistence internals stay in
  `app.services.ai_text_artifact_service`.
- Production plan row construction stays in
  `app.domains.video_production.production_plan_service`.
- Pipeline execution and video rendering stay in their own domains and services.

## Current Modules

- `director_router.py` owns `DirectorAutoPlanRequest`, `EpisodePlanRequest`,
  `ShotSegmentsRequest`, `generate_auto_storyboard`, `_normalize_auto_frames`,
  storyboard artifact recording through `AITextArtifactService`, director
  timeout constants, and all `/api/director/*` route handlers.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.director` | `app.domains.director_planning.director_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |

## Boundaries

- Preserve route paths, route names, auth dependencies, and response shapes.
- Preserve auto-plan storyboard persistence and AI text artifact side effects.
- Preserve monkeypatch compatibility for `app.routers.director.ai_generator`,
  `app.routers.director.AgencyOrchestrator`, and director timeout constants.
- Keep script pipeline's `/api/director/auto-plan` message as an external route
  hint rather than importing this domain.

## Compatibility Cleanup Gates

Do not remove the legacy router facade until all of these are true:

- `app.main` imports `director_router` from `app.domains.director_planning`.
- Route/auth snapshots pass against the domain endpoint module.
- Legacy and domain imports resolve to the same module object during the alias
  phase.
- Existing director and style-lock auto-plan tests pass.
- Import inventory shows no unapproved production imports of
  `app.routers.director`.

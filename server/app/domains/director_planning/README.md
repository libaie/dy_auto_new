# Director Planning Domain

This domain owns director workshop and episode production planning routes.

## Owned Routes

- `/api/director/*`

## Not Owned

- `Episode`, `Series`, and production ORM model definitions stay in
  `app.db.models`.
- Database session helpers stay in `app.database`.
- Auth dependencies stay in `app.deps`.
- Agency review orchestration lives in
  `app.domains.agency_operations.agency_orchestrator`.
- AI text artifact persistence internals stay in
  `app.domains.ai_text_artifacts.ai_text_artifact_service`.
- Production plan row construction stays in
  `app.domains.video_production.production_plan_service`.
- Pipeline execution and video rendering stay in their own domains and services.

## Current Modules

- `director_router.py` owns `DirectorAutoPlanRequest`, `EpisodePlanRequest`,
  `ShotSegmentsRequest`, `generate_auto_storyboard`, `_normalize_auto_frames`,
  storyboard artifact recording through `AITextArtifactService`, director
  timeout constants, and all `/api/director/*` route handlers.

## Canonical Imports

The retired router, service, and ORM import packages have been removed. Runtime code, tests, scripts, and new docs must import domain modules directly and use `app.db.models` / `app.db.models.<domain>` for ORM models.

## Boundaries

- Preserve route paths, route names, auth dependencies, and response shapes.
- Preserve auto-plan storyboard persistence and AI text artifact side effects.
- Keep script pipeline's `/api/director/auto-plan` message as an external route
  hint rather than importing this domain.

## Legacy Import Guard

The cleanup gate is complete. Keep the retired import-path and AST inventory tests passing so removed paths stay unavailable.

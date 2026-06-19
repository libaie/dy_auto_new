# Video Production Domain

This domain owns the video production control-plane HTTP routes.

## Owned Routes

- `/api/video-production/*`

## Not Owned

- Production ORM models stay in `app.db_models`.
- Database session helpers stay in `app.database`.
- Auth dependencies stay in `app.deps`.
- Production orchestration, worker execution, queues, retries, reviews, costs,
  readiness, text artifacts, and stage transitions stay in `app.services.*`.
- Video library routes stay in `app.domains.video_library`.

## Current Modules

- `video_production_router.py` owns route request models such as
  `StartRunRequest` and `OneSentenceVideoRequest`, payload helpers such as
  `_run_payload`, `_asset_payload`, and `_provider_stage_task_payload`,
  HTTP error mapping helpers, and all `/api/video-production/*` route handlers.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.video_production` | `app.domains.video_production.video_production_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |

## Boundaries

- Preserve route paths, route names, auth dependencies, and response shapes.
- Preserve admin-role protection on every route.
- Preserve monkeypatch compatibility for `app.routers.video_production`, notably
  helpers like `edit_image_asset`.
- Preserve service-layer ownership of production state transitions.
- Preserve background helpers for one-sentence references and real worker steps.

## Compatibility Cleanup Gates

Do not remove the legacy router facade until all of these are true:

- `app.main` imports `video_production_router` from
  `app.domains.video_production`.
- Route/auth snapshots pass against the domain endpoint module.
- Legacy and domain imports resolve to the same module object during the alias
  phase.
- Focused video production API, start-flow, worker, readiness, and mocked E2E
  tests pass.
- Import inventory shows no unapproved production imports of
  `app.routers.video_production`.

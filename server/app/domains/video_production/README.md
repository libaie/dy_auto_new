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

- `production_action_result.py` owns `ProductionActionResult` and action result
  HTTP detail serialization.
- `production_errors.py` owns `ProductionErrorCode`,
  `ProductionRepairableError`, and `to_http_detail`.
- `video_production_router.py` owns route request models such as
  `StartRunRequest` and `OneSentenceVideoRequest`, payload helpers such as
  `_run_payload`, `_asset_payload`, and `_provider_stage_task_payload`,
  HTTP error mapping helpers, and all `/api/video-production/*` route handlers.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.video_production` | `app.domains.video_production.video_production_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |
| `app.services.production_action_result` | `app.domains.video_production.production_action_result` | Domain modules import the domain helper path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.services.production_errors` | `app.domains.video_production.production_errors` | Domain modules import the domain helper path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |

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

Do not remove the legacy production action result facade until all of these are true:

- `rg "app\.services\.production_action_result" server/app server/tests` returns only compatibility tests, migration docs, or service modules whose domains have not moved yet.
- `test_video_production_action_result_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.video_production.production_action_result` directly.

Do not remove the legacy production errors facade until all of these are true:

- `rg "app\.services\.production_errors" server/app server/tests` returns only compatibility tests, migration docs, or service modules whose domains have not moved yet.
- `test_video_production_error_helper_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.video_production.production_errors` directly.

# Image Generation Domain

This domain owns the admin image creation and image production route boundary,
plus image production strategy business logic.

## Owned Routes

- `/api/image-creation/*`
- `/api/image-production/*`

## Current Modules

- `image_creation_router.py` owns upload, Pixelle file proxy, task create/read,
  task sync/dispatch, asset list/review, and asset edit endpoints.
- `image_production_router.py` owns image strategies, metrics refresh, selection
  preview, A/B tests, winner decisions, image-to-video promotion, and strategy
  recommendations.
- `image_production_strategy_service.py` owns `seed_default_image_strategies`,
  strategy validation, CRUD/version writes, status transitions, and
  `strategy_payload`.
- `image_selection_preview_service.py` owns `create_selection_preview`,
  provider-option validation, model/cost/capacity/review preview assembly,
  request hashing, and `ImageSelectionPreview` persistence.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.image_creation` | `app.domains.image_generation.image_creation_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |
| `app.routers.image_production` | `app.domains.image_generation.image_production_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |
| `app.services.image_production_strategy_service` | `app.domains.image_generation.image_production_strategy_service` | Domain modules import the domain service path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.services.image_selection_preview_service` | `app.domains.image_generation.image_selection_preview_service` | Domain modules import the domain service path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |

## Boundaries

- Keep image route paths, methods, auth dependencies, response shapes, and route
  function names stable.
- Keep remaining service implementations in `app.services.*` until their
  service-split plans are approved.
- Keep ORM models in `app.db_models` during this route-boundary migration.
- Do not move video production, agency review, AI config, or Pixelle proxy
  ownership into this domain unless a later plan explicitly expands scope.

## Compatibility Cleanup Gates

Do not remove legacy router facades until all of these are true:

- `app.main` imports image routers from `app.domains.image_generation`.
- Route/auth snapshots pass against domain endpoint modules.
- Legacy and domain imports resolve to the same module objects during the alias
  phase.
- Existing image creation and image production API tests pass.
- Import inventory shows no unapproved production imports of
  `app.routers.image_creation` or `app.routers.image_production`.

Do not remove the legacy image strategy service facade until all of these are true:

- `rg "app\.services\.image_production_strategy_service" server/app server/tests` returns only compatibility tests and migration docs.
- `test_image_generation_strategy_service_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.image_generation.image_production_strategy_service` directly.

Do not remove the legacy selection preview service facade until all of these are true:

- `rg "app\.services\.image_selection_preview_service" server/app server/tests` returns only compatibility tests and migration docs.
- `test_image_generation_selection_preview_service_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.image_generation.image_selection_preview_service` directly.

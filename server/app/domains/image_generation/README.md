# Image Generation Domain

This domain owns the admin image creation and image production route boundary.

## Owned Routes

- `/api/image-creation/*`
- `/api/image-production/*`

## Current Modules

- `image_creation_router.py` owns upload, Pixelle file proxy, task create/read,
  task sync/dispatch, asset list/review, and asset edit endpoints.
- `image_production_router.py` owns image strategies, metrics refresh, selection
  preview, A/B tests, winner decisions, image-to-video promotion, and strategy
  recommendations.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.image_creation` | `app.domains.image_generation.image_creation_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |
| `app.routers.image_production` | `app.domains.image_generation.image_production_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |

## Boundaries

- Keep image route paths, methods, auth dependencies, response shapes, and route
  function names stable.
- Keep service implementations in `app.services.*` until a service-split plan is
  approved.
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

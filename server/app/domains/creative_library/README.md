# Creative Library Domain

This domain owns reusable creative asset routes for characters, scenes, and
reference dictionaries.

## Owned Routes

- `/api/characters/*`
- `/api/scenes/*`
- `/api/reference-categories/*`
- `/api/reference-data/*`

## Current Modules

- `characters_router.py` owns character CRUD, character auto-generation,
  character reference image generation, and character AI rewrite endpoints.
- `scenes_router.py` owns scene CRUD, scene auto-generation, scene reference
  image generation, and scene AI rewrite endpoints.
- `reference_data_router.py` owns reference category/item CRUD and default seed
  data.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.characters` | `app.domains.creative_library.characters_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |
| `app.routers.scenes` | `app.domains.creative_library.scenes_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |
| `app.routers.reference_data` | `app.domains.creative_library.reference_data_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |

## Boundaries

- Keep series character/scene linking in `ai_video_series`.
- Keep asset reference generation and AI rewrite service bodies in
  `app.services.*` until a service-split plan is approved.
- Keep ORM models in `app.db_models` during this route-boundary migration.
- Keep startup reference data seeding behavior unchanged.

## Compatibility Cleanup Gates

Do not remove legacy router facades until all of these are true:

- `app.main` imports creative library routers from
  `app.domains.creative_library`.
- Route/auth snapshots pass against domain endpoint modules.
- Legacy and domain imports resolve to the same module objects during the alias
  phase.
- Existing series, asset archive, asset rewrite, and reference asset tests pass.
- Import inventory shows no unapproved production imports of
  `app.routers.characters`, `app.routers.scenes`, or
  `app.routers.reference_data`.

# Video Library Domain

This domain owns admin generated-video library routes.

## Owned Routes

- `/api/videos/*`

## Not Owned

- `app.routers.video_production` stays outside this domain.
- Pixelle provider and proxy routes stay outside this domain.
- Seedance provider routes stay outside this domain.

## Current Modules

- `videos_router.py` owns generated-video list, detail, download, and delete
  routes.
- `app.db.models.video_library` owns the `GeneratedVideo` ORM class body.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.videos` | `app.domains.video_library.videos_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |
| `app.db_models.GeneratedVideo` | `app.db.models.video_library.GeneratedVideo` | Keep as a compatibility re-export until production imports use the domain model path. |

## Boundaries

- Keep generated-video persistence on `app.db.models.video_library.GeneratedVideo`.
- Keep video production, Pixelle, and Seedance execution flows outside this
  domain.
- Preserve route paths, route names, auth dependencies, response shapes,
  download token fallback behavior, and delete behavior.
- Do not add a service layer in this route-boundary migration.

## Compatibility Cleanup Gates

Do not remove the legacy router facade until all of these are true:

- `app.main` imports the videos router from `app.domains.video_library`.
- Route/auth snapshots pass against the domain endpoint module.
- Legacy and domain imports resolve to the same module object during the alias
  phase.
- Video library API behavior tests pass.
- Import inventory shows no unapproved production imports of
  `app.routers.videos`.

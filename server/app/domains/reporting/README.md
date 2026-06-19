# Reporting Domain

This domain owns admin statistics read routes for dashboard and account quota
views.

## Owned Routes

- `/api/stats/*`

## Not Owned

- `/api/device/stats/increment` stays in `device_operations`.

## Current Modules

- `stats_router.py` owns dashboard summary, daily stats, account stats, and
  realtime stats routes.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.stats` | `app.domains.reporting.stats_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |

## Boundaries

- Keep daily stats counting and quota logic in `app.services.stats_service`.
- Keep device-side stats increment reporting in `device_operations`.
- Preserve route paths, route names, auth dependencies, response shapes, default
  date behavior, and dashboard query behavior.
- Do not add analytics features in this route-boundary migration.

## Compatibility Cleanup Gates

Do not remove the legacy router facade until all of these are true:

- `app.main` imports the stats router from `app.domains.reporting`.
- Route/auth snapshots pass against the domain endpoint module.
- Legacy and domain imports resolve to the same module object during the alias
  phase.
- Existing stats API, stats service, and device stats reporting tests pass.
- Import inventory shows no unapproved production imports of
  `app.routers.stats`.

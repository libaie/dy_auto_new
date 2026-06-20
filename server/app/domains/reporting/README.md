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
- `stats_service.py` owns `StatsService`, `stats_service`, daily stats row
  creation, quota checks, remaining quota payloads, and task quota parameter
  injection.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.stats` | `app.domains.reporting.stats_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |
| `app.services.stats_service` | `app.domains.reporting.stats_service` | All stats service callers import the reporting domain service directly or belong to domains that have not moved yet. |

## Boundaries

- Keep daily stats counting and quota logic in
  `app.domains.reporting.stats_service`.
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

Do not remove the legacy stats service facade until all of these are true:

- `rg "app\.services\.stats_service" server/app server/tests` returns only
  compatibility tests, migration docs, or service modules whose domains have
  not moved yet.
- `test_reporting_stats_service_facade.py` has been replaced with tests for
  direct domain imports.
- Domain-owned reporting modules import `app.domains.reporting.stats_service`
  directly.
- Direct domain stats service coverage proves `StatsService` and
  `stats_service` behavior without legacy imports.

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
- `app.db.models.reporting` owns the `DailyStats` and `StatsEvent` ORM class
  bodies.

## Canonical Imports

The retired router, service, and ORM import packages have been removed. Runtime code, tests, scripts, and new docs must import domain modules directly and use `app.db.models` / `app.db.models.<domain>` for ORM models.

## Boundaries

- Keep daily stats counting and quota logic in
  `app.domains.reporting.stats_service`.
- Keep device-side stats increment reporting in `device_operations`.
- Keep reporting stats ORM class bodies in `app.db.models.reporting`.
- Preserve route paths, route names, auth dependencies, response shapes, default
  date behavior, and dashboard query behavior.
- Do not add analytics features in this route-boundary migration.

## Legacy Import Guard

The cleanup gate is complete. Keep the retired import-path and AST inventory tests passing so removed paths stay unavailable.

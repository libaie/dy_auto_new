# Reporting Domain Design

Date: 2026-06-20

## Goal

Move admin statistics route ownership out of the flat `app.routers` folder and
into `app.domains.reporting` without changing public API behavior.

This domain owns the dashboard-facing statistics reads for accounts, devices,
tasks, daily account operation counts, account quota summaries, and realtime
dashboard counters.

## Scope

The new domain owns:

- `/api/stats/dashboard`;
- `/api/stats/daily`;
- `/api/stats/accounts/{account_id}`;
- `/api/stats/realtime`;
- route assembly and admin auth dependencies for those endpoints.

The migration keeps `app.routers.stats` as a compatibility facade.

## Non-Goals

- Do not move device-facing `/api/device/stats/increment`; that stays in
  `device_operations`.
- Daily stats counting and quota checks now live in
  `app.domains.reporting.stats_service`; `app.services.stats_service` remains
  as a temporary compatibility facade.
- Do not change route paths, route names, auth dependencies, response shapes,
  default dates, quota behavior, or dashboard query behavior.
- Do not add new analytics features.

## Target Structure

```text
server/app/domains/reporting/
  __init__.py
  README.md
  stats_service.py
  stats_router.py
```

This began as a route-boundary migration. Daily stats queries and account quota
helpers now live in the reporting domain through `StatsService`, while later
work can still split dashboard read models after the domain import boundary is
stable.

## Compatibility Strategy

Legacy imports stay valid through a module alias:

```python
from app.domains.reporting import stats_router as _stats_router
sys.modules[__name__] = _stats_router
globals().update(_stats_router.__dict__)
```

This keeps old imports of `app.routers.stats` resolving to the same module
object as `app.domains.reporting.stats_router` during the compatibility phase.

## Tests

The migration adds:

- route/auth snapshot tests for `/api/stats/*`;
- boundary tests for metadata, README, facade thickness, route registration,
  main wiring, and device stats non-ownership;
- facade identity tests proving old and new imports resolve to the same module
  object while compatibility is active.

# Reporting Stats Service Domain Design

## Context

`app.services.stats_service` owns daily account operation counters and quota
checks for the reporting dashboard, account quota views, task execution, channel
claims, and device stats increment reporting. The reporting route already lives
in `app.domains.reporting`, but its service logic still lives in the generic
services folder.

## Approved Approach

Move the implementation to `app.domains.reporting.stats_service` and keep
`app.services.stats_service` as a temporary compatibility facade. Update the
clean reporting router to import the domain service directly.

Do not touch device operations, task, or channel service callers in this slice;
their legacy imports remain supported by the facade.

## Boundaries

- Preserve `StatsService`, `stats_service`, `_TASK_TYPE_TO_COLUMN`, and
  `_NURTURE_TYPE_TO_COLUMN`.
- Preserve daily stats row creation, flush-only increment behavior, quota
  checks, remaining quota payloads, and nurture quota parameter injection.
- Preserve existing callers that import `app.services.stats_service`.
- Preserve `/api/device/stats/increment` ownership in `device_operations`.
- Document the legacy facade in the reporting domain README with an explicit
  cleanup gate.

## Verification

- Add a boundary test proving spec and plan coverage for
  `app.domains.reporting.stats_service`, `app.services.stats_service`,
  `StatsService`, and `stats_service`.
- Prove the legacy import and domain import resolve to the same module object.
- Prove the legacy file is a thin facade and contains no local
  `class StatsService`.
- Prove the reporting router imports the domain stats service.
- Prove device operations stats increment still owns its route and can remain
  on the legacy facade during this slice.
- Run stats service, stats API, reporting route facade, and device stats
  reporting tests after migration.

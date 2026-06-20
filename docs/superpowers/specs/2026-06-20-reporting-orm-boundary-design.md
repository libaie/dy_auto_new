# Reporting ORM Boundary Design

## Context

`DailyStats` and `StatsEvent` are reporting statistics tables still defined in
the monolithic `app.db_models` module.

## Decision

Move both class bodies to `app.db.models.reporting`. Keep
`app.db_models.DailyStats` and `app.db_models.StatsEvent` as compatibility
re-exports.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_reporting_orm_boundary.py server/tests/test_reporting_domain_boundary.py server/tests/test_reporting_router_facade.py server/tests/test_reporting_stats_service_facade.py server/tests/test_stats_service.py server/tests/test_stats_api.py server/tests/test_device_operations_polling_reporting.py -q
```

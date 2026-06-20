# System Setting ORM Boundary Design

## Context

`SystemSetting` is still defined in the monolithic `app.db_models` file even
though system settings already have a `system_configuration` domain.

## Decision

Move the `SystemSetting` class body to
`app.db.models.system_configuration`. Keep `app.db_models.SystemSetting` as a
compatibility re-export.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_system_configuration_orm_boundary.py server/tests/test_settings_endpoints.py server/tests/test_ai_config_resolve.py -q
```

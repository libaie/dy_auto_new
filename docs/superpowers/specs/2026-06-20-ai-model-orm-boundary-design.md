# AI Model ORM Boundary Design

## Context

`AIModel` is a standalone model-configuration table still defined in the
monolithic `app.db_models` module.

## Decision

Move the `AIModel` class body to `app.db.models.model_configuration`. Keep
`app.db_models.AIModel` as a compatibility re-export.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_model_configuration_orm_boundary.py server/tests/test_model_registry.py server/tests/test_runtime_model_config.py server/tests/test_ai_config.py server/tests/test_ai_config_resolve.py server/tests/test_ai_config_scene_schema.py server/tests/test_ai_model_migration.py -q
```

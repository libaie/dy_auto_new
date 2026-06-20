# Content Template And Sensitive Word ORM Boundary Design

## Context

`ContentTemplate` and `SensitiveWord` are standalone content-collection tables
still defined in `app.db_models`.

## Decision

Move both class bodies to `app.db.models.content_collection`. Keep
`app.db_models.ContentTemplate` and `app.db_models.SensitiveWord` as
compatibility re-exports.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_collection_orm_boundary.py server/tests/test_content_service.py server/tests/test_content_api.py -q
```

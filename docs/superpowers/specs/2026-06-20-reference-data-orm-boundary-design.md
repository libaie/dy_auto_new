# Reference Data ORM Boundary Design

## Context

`ReferenceData` and `ReferenceCategory` are standalone creative-library
dictionary tables still defined in the monolithic `app.db_models` module.

## Decision

Move both class bodies to `app.db.models.creative_library`. Keep
`app.db_models.ReferenceData` and `app.db_models.ReferenceCategory` as
compatibility re-exports.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_creative_library_orm_boundary.py server/tests/test_creative_library_domain_boundary.py server/tests/test_creative_library_router_facade.py -q
```

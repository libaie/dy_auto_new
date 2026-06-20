# UI Selector ORM Boundary Design

## Context

`UISelector` is a standalone selector-management table still defined in the
monolithic `app.db_models` module.

## Decision

Move the `UISelector` class body to `app.db.models.selector_management`. Keep
`app.db_models.UISelector` as a compatibility re-export.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_selector_management_orm_boundary.py server/tests/test_selector_service.py server/tests/test_selectors_template.py -q
```

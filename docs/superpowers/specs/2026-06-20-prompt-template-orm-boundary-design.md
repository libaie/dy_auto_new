# Prompt Template ORM Boundary Design

## Context

`PromptTemplate` is a standalone prompt-management table still defined in the
monolithic `app.db_models` module.

## Decision

Move the `PromptTemplate` class body to `app.db.models.prompt_management`.
Keep `app.db_models.PromptTemplate` as a compatibility re-export.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_prompt_management_orm_boundary.py server/tests/test_prompt_templates_rewrite.py server/tests/test_prompt_template_service_domain_facade.py -q
```

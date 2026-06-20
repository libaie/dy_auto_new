# Prompt Template ORM Boundary Plan

> Auto-approved spec: proceed without approval pause.

**Goal:** Move the standalone `PromptTemplate` ORM class body out of
`app.db_models`.

## Tasks

- [ ] Add a boundary test for `app.db.models.prompt_management.PromptTemplate`.
- [ ] Move `PromptTemplate` into `server/app/db/models/prompt_management.py`.
- [ ] Re-export `PromptTemplate` from `server/app/db_models.py`.
- [ ] Update prompt management domain imports and README.
- [ ] Run focused prompt-template tests.

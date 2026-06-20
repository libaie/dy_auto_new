# Content Template And Sensitive Word ORM Boundary Plan

> Auto-approved spec: proceed without approval pause.

**Goal:** Move the standalone content template and sensitive-word ORM class
bodies out of `app.db_models`.

## Tasks

- [ ] Add a boundary test for `app.db.models.content_collection`.
- [ ] Move `ContentTemplate` and `SensitiveWord` into `server/app/db/models/content_collection.py`.
- [ ] Re-export both names from `server/app/db_models.py`.
- [ ] Update content collection domain imports and README.
- [ ] Run focused content service/API tests.

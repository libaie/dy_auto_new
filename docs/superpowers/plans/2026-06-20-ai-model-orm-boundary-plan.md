# AI Model ORM Boundary Plan

> Auto-approved spec: proceed without approval pause.

**Goal:** Move the standalone `AIModel` ORM class body out of `app.db_models`.

## Tasks

- [ ] Add a boundary test for `app.db.models.model_configuration.AIModel`.
- [ ] Move `AIModel` into `server/app/db/models/model_configuration.py`.
- [ ] Re-export `AIModel` from `server/app/db_models.py`.
- [ ] Update model configuration domain imports and README.
- [ ] Run focused model configuration tests.

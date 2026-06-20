# Reference Data ORM Boundary Plan

> Auto-approved spec: proceed without approval pause.

**Goal:** Move standalone creative-library dictionary ORM class bodies out of
`app.db_models`.

## Tasks

- [x] Add a boundary test for `app.db.models.creative_library`.
- [x] Move `ReferenceData` and `ReferenceCategory` into `server/app/db/models/creative_library.py`.
- [x] Re-export both names from `server/app/db_models.py`.
- [x] Update creative library domain imports and README.
- [x] Run focused reference data tests.

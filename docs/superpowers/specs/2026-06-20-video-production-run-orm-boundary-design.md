# VideoProductionRun ORM Boundary Design

## Goal

Move `VideoProductionRun` into the video production ORM module while preserving the legacy `app.db_models` import contract.

## Scope

- `VideoProductionRun` is defined in `server/app/db/models/video_production.py`.
- `server/app/db_models.py` re-exports `VideoProductionRun` from the new module.
- Video production domain code imports `VideoProductionRun` from `app.db.models.video_production`.
- Non-owner domains and tests can keep compatibility imports from `app.db_models`.

## Acceptance Criteria

- `from app.db.models.video_production import VideoProductionRun` works in a clean Python process.
- `app.db_models.VideoProductionRun is app.db.models.video_production.VideoProductionRun`.
- `VideoProductionRun.__module__ == "app.db.models.video_production"`.
- `video_production_runs` remains registered on shared `Base.metadata`.
- No video production domain module imports `VideoProductionRun` from `app.db_models`.

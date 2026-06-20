# VideoProductionAsset ORM Boundary Design

## Goal

Move `VideoProductionAsset` into the video production ORM module while preserving the legacy `app.db_models` compatibility import.

## Scope

- `VideoProductionAsset` is defined in `server/app/db/models/video_production.py`.
- `server/app/db_models.py` re-exports `VideoProductionAsset` from the new module.
- Video production owner-domain modules import `VideoProductionAsset` from `app.db.models.video_production`.
- Tests and non-owner domains can keep using `app.db_models`.

## Acceptance Criteria

- `from app.db.models.video_production import VideoProductionAsset` works in a clean Python process.
- `app.db_models.VideoProductionAsset is app.db.models.video_production.VideoProductionAsset`.
- `VideoProductionAsset.__module__ == "app.db.models.video_production"`.
- `video_production_assets` remains registered on shared `Base.metadata`.
- No video production owner-domain module imports `VideoProductionAsset` from `app.db_models`.

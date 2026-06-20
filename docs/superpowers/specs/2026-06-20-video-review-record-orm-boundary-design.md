# VideoReviewRecord ORM Boundary Design

## Goal

Move `VideoReviewRecord` into the video production ORM module while keeping `app.db_models` as the legacy compatibility import.

## Scope

- `VideoReviewRecord` is defined in `server/app/db/models/video_production.py`.
- `server/app/db_models.py` re-exports `VideoReviewRecord`.
- Video production owner-domain review, router, segment-detail, and service modules import it from `app.db.models.video_production`.
- Tests and non-owner domains may continue to import from `app.db_models`.

## Acceptance Criteria

- `from app.db.models.video_production import VideoReviewRecord` works in a clean Python process.
- `app.db_models.VideoReviewRecord is app.db.models.video_production.VideoReviewRecord`.
- `VideoReviewRecord.__module__ == "app.db.models.video_production"`.
- `video_review_records` remains registered on shared `Base.metadata`.
- No video production owner-domain module imports `VideoReviewRecord` from `app.db_models`.

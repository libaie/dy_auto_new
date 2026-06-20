# Production Shot ORM Boundary Design

## Context

`ProductionPlan`, `ProductionPlanVersion`, `ProductionEpisode`, and `ProductionScene` now live in `app.db.models.video_production`. `ProductionShot` is the next node in the same production plan tree and is still defined in `app.db_models`.

## Approved Approach

Move only `ProductionShot` in this slice.

The alternatives were:
- Move `ProductionShot` and `ProductionSegment` together. This saves one pass but touches more hot production code.
- Leave `ProductionShot` until the whole tree can move. This keeps `ProductionScene` pointing at a child class in the legacy module.
- Move `ProductionShot` alone. This keeps the diff small and extends the tree boundary one level.

Chosen: move `ProductionShot` alone.

## Requirements

- Define `ProductionShot` in `server/app/db/models/video_production.py`.
- Keep `app.db_models.ProductionShot` as the same class via compatibility import.
- Keep table metadata unchanged: `production_shots` remains registered on the shared `Base.metadata`.
- Update `server/app/domains/video_production` imports so owner-domain code imports `ProductionShot` from `app.db.models.video_production`.
- Leave tests and non-owner modules free to use `app.db_models` compatibility imports for now.

## Non-Goals

- Do not move `ProductionSegment`, jobs, runs, assets, reviews, provider tasks, cost events, or image-production ORM classes in this slice.
- Do not change schema, migrations, API behavior, or production workflow logic.

## Verification

- Boundary test proves `app.db.models.video_production.ProductionShot` exists, is the same class as `app.db_models.ProductionShot`, and reports `__module__ == "app.db.models.video_production"`.
- Focused video-production tests still pass.
- `server/app/domains/video_production` has no remaining `ProductionShot` import from `app.db_models`.

# Production Segment ORM Boundary Design

## Context

The video production plan tree is being moved out of the legacy `app.db_models` module. `ProductionPlan`, `ProductionPlanVersion`, `ProductionEpisode`, `ProductionScene`, and `ProductionShot` already live in `app.db.models.video_production`. `ProductionSegment` is the remaining plan-tree node still defined in `app.db_models`.

## Approved Approach

Move only `ProductionSegment` in this slice.

The alternatives were:
- Move segments plus jobs/runs/assets together. This reduces the number of commits but creates a wide, risky diff across queueing and provider code.
- Stop after shots. This leaves the production tree split between the new module and the legacy module.
- Move `ProductionSegment` alone. This completes the plan-tree ORM boundary while keeping runtime/queue/asset tables for later slices.

Chosen: move `ProductionSegment` alone.

## Requirements

- Define `ProductionSegment` in `server/app/db/models/video_production.py`.
- Keep `app.db_models.ProductionSegment` as the same class via compatibility import.
- Keep table metadata unchanged: `production_segments` remains registered on the shared `Base.metadata`.
- Update `server/app/domains/video_production` imports so owner-domain code imports `ProductionSegment` from `app.db.models.video_production`.
- Leave tests and non-owner modules free to use `app.db_models` compatibility imports for now.

## Non-Goals

- Do not move `ProductionJob`, `VideoProductionRun`, `VideoProductionAsset`, `VideoReviewRecord`, provider tasks, cost events, or image-production ORM classes in this slice.
- Do not change schema, migrations, API behavior, or production workflow logic.

## Verification

- Boundary test proves `app.db.models.video_production.ProductionSegment` exists, is the same class as `app.db_models.ProductionSegment`, and reports `__module__ == "app.db.models.video_production"`.
- Focused video-production tests still pass.
- `server/app/domains/video_production` has no remaining `ProductionSegment` import from `app.db_models`.

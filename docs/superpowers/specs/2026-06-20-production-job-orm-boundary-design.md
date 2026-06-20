# Production Job ORM Boundary Design

## Context

The video production plan tree now lives in `app.db.models.video_production`. `ProductionJob` is the queue record that drives the same video production pipeline, but it is still defined in the legacy `app.db_models` module.

## Approved Approach

Move only `ProductionJob` in this slice.

The alternatives were:
- Move queue, provider, cost, run, asset, and review tables together. This would be broad and hard to verify in one pass.
- Leave `ProductionJob` in `app.db_models` until the rest of runtime state moves. This keeps core queue code tied to the legacy bucket.
- Move `ProductionJob` alone. This gives the queue owner a clear ORM boundary while keeping provider/runtime tables for later slices.

Chosen: move `ProductionJob` alone.

## Requirements

- Define `ProductionJob` in `server/app/db/models/video_production.py`.
- Keep `app.db_models.ProductionJob` as the same class via compatibility import.
- Keep table metadata unchanged: `production_jobs` remains registered on the shared `Base.metadata`.
- Update `server/app/domains/video_production` imports so owner-domain code imports `ProductionJob` from `app.db.models.video_production`.
- Leave tests and non-owner modules free to use `app.db_models` compatibility imports for now.

## Non-Goals

- Do not move provider tasks, reservations, cost events, runs, assets, reviews, or image-production ORM classes in this slice.
- Do not change queue semantics, worker behavior, schema, migrations, or API behavior.

## Verification

- Boundary test proves `app.db.models.video_production.ProductionJob` exists, is the same class as `app.db_models.ProductionJob`, and reports `__module__ == "app.db.models.video_production"`.
- Focused video-production queue/tree/worker tests still pass.
- `server/app/domains/video_production` has no remaining `ProductionJob` import from `app.db_models`.

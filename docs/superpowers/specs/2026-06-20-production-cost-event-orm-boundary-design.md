# Production Cost Event ORM Boundary Design

## Context

Provider stage tasks and cost reservations now live in `app.db.models.video_production`. `ProductionCostEvent` is the video production cost ledger row, but it still lives in the legacy `app.db_models` module.

## Approved Approach

Move only `ProductionCostEvent` in this slice.

The alternatives were:
- Move runtime, asset, review, and cost event tables together. That is too broad for one safe refactor.
- Leave cost events in `app.db_models`. That keeps cost services tied to the legacy bucket after reservations moved.
- Move `ProductionCostEvent` alone. This completes the provider/cost ORM cluster while keeping run/asset/review for later slices.

Chosen: move `ProductionCostEvent` alone.

## Requirements

- Define `ProductionCostEvent` in `server/app/db/models/video_production.py`.
- Keep `app.db_models.ProductionCostEvent` as the same class via compatibility import.
- Keep table metadata unchanged: `production_cost_events` remains registered on the shared `Base.metadata`.
- Update `server/app/domains/video_production` imports so owner-domain code imports `ProductionCostEvent` from `app.db.models.video_production`.
- Leave tests and non-owner modules free to use `app.db_models` compatibility imports for now.

## Non-Goals

- Do not move `VideoProductionRun`, `VideoProductionAsset`, `VideoReviewRecord`, or image-production ORM classes in this slice.
- Do not change cost recording behavior, schema, migrations, API behavior, or summary math.

## Verification

- Boundary test proves `app.db.models.video_production.ProductionCostEvent` exists, is the same class as `app.db_models.ProductionCostEvent`, and reports `__module__ == "app.db.models.video_production"`.
- Focused production cost tests still pass.
- `server/app/domains/video_production` has no remaining `ProductionCostEvent` import from `app.db_models`.

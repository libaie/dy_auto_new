# Production Scene ORM Boundary Design

## Context

`server/app/db_models.py` is being split into business-owned ORM modules. The video production plan models already live in `app.db.models.video_production`, with `app.db_models` kept as the legacy compatibility import surface.

## Approved Approach

Move only `ProductionScene` in this slice.

The alternatives were:
- Move the whole production tree at once. This is faster on paper but creates a large diff across hot video-production code.
- Leave `ProductionScene` in `app.db_models` until later. This stalls the production-tree split after `ProductionEpisode`.
- Move `ProductionScene` alone. This keeps the diff small and preserves a clean rollback point.

Chosen: move `ProductionScene` alone.

## Requirements

- Define `ProductionScene` in `server/app/db/models/video_production.py`.
- Keep `app.db_models.ProductionScene` as the same class via compatibility import.
- Keep table metadata unchanged: `production_scenes` remains registered on the shared `Base.metadata`.
- Update `server/app/domains/video_production` imports so owner-domain code imports `ProductionScene` from `app.db.models.video_production`.
- Leave tests and non-owner modules free to use `app.db_models` compatibility imports for now.

## Non-Goals

- Do not move `ProductionShot`, `ProductionSegment`, jobs, runs, assets, reviews, provider tasks, cost events, or image-production ORM classes in this slice.
- Do not change schema, migrations, API behavior, or production workflow logic.

## Verification

- Boundary test proves `app.db.models.video_production.ProductionScene` exists, is the same class as `app.db_models.ProductionScene`, and reports `__module__ == "app.db.models.video_production"`.
- Focused video-production tests still pass.
- `server/app/domains/video_production` has no remaining `ProductionScene` import from `app.db_models`.

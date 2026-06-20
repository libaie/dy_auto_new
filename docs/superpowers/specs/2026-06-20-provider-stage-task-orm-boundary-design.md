# Provider Stage Task ORM Boundary Design

## Context

Video production plan, queue, and segment models now live in `app.db.models.video_production`. `ProviderStageTask` tracks provider submission/sync state for the same pipeline but is still defined in the legacy `app.db_models` module.

## Approved Approach

Move only `ProviderStageTask` in this slice.

The alternatives were:
- Move provider tasks and cost reservations together. They are related, but that makes one diff cover both provider state and cost accounting.
- Leave provider tasks in `app.db_models` until all runtime tables move. This keeps provider execution code tied to the legacy bucket.
- Move `ProviderStageTask` alone. This gives provider execution a clear ORM home and keeps cost accounting for the next slice.

Chosen: move `ProviderStageTask` alone.

## Requirements

- Define `ProviderStageTask` in `server/app/db/models/video_production.py`.
- Keep `app.db_models.ProviderStageTask` as the same class via compatibility import.
- Keep table metadata unchanged: `provider_stage_tasks` remains registered on the shared `Base.metadata`.
- Update `server/app/domains/video_production` imports so owner-domain code imports `ProviderStageTask` from `app.db.models.video_production`.
- Leave non-owner modules free to use `app.db_models` compatibility imports for now.

## Non-Goals

- Do not move `ProviderCostReservation`, `ProductionCostEvent`, runs, assets, reviews, or image-production ORM classes in this slice.
- Do not change provider execution behavior, schema, migrations, API behavior, or cost accounting.

## Verification

- Boundary test proves `app.db.models.video_production.ProviderStageTask` exists, is the same class as `app.db_models.ProviderStageTask`, and reports `__module__ == "app.db.models.video_production"`.
- Focused provider stage tests still pass.
- `server/app/domains/video_production` has no remaining `ProviderStageTask` import from `app.db_models`.

# Provider Cost Reservation ORM Boundary Design

## Context

`ProviderStageTask` now lives in `app.db.models.video_production`. `ProviderCostReservation` is the cost reservation record attached to provider stage tasks, but it still lives in the legacy `app.db_models` module.

## Approved Approach

Move only `ProviderCostReservation` in this slice.

The alternatives were:
- Move `ProviderCostReservation` and `ProductionCostEvent` together. This is tempting, but it mixes reservation lifecycle with cost ledger history.
- Leave `ProviderCostReservation` in `app.db_models`. This keeps provider execution and cost reservation services split across ORM modules.
- Move `ProviderCostReservation` alone. This keeps the provider task/reservation pair in the video production ORM module while leaving the cost event ledger for a later slice.

Chosen: move `ProviderCostReservation` alone.

## Requirements

- Define `ProviderCostReservation` in `server/app/db/models/video_production.py`.
- Keep `app.db_models.ProviderCostReservation` as the same class via compatibility import.
- Keep table metadata unchanged: `provider_cost_reservations` remains registered on the shared `Base.metadata`.
- Update `server/app/domains/video_production` imports so owner-domain code imports `ProviderCostReservation` from `app.db.models.video_production`.
- Leave non-owner modules free to use `app.db_models` compatibility imports for now.

## Non-Goals

- Do not move `ProductionCostEvent`, runs, assets, reviews, or image-production ORM classes in this slice.
- Do not change reservation lifecycle behavior, schema, migrations, API behavior, or cost accounting.

## Verification

- Boundary test proves `app.db.models.video_production.ProviderCostReservation` exists, is the same class as `app.db_models.ProviderCostReservation`, and reports `__module__ == "app.db.models.video_production"`.
- Focused provider cost and provider stage tests still pass.
- `server/app/domains/video_production` has no remaining `ProviderCostReservation` import from `app.db_models`.

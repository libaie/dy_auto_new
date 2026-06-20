# Image Production Cost Domain Design

Date: 2026-06-20

## Goal

Move image generation cost event recording out of the flat `app.services`
folder and into the `image_generation` domain without changing behavior.

## Design

`app.domains.image_generation.image_production_cost_service` owns
`record_estimated_cost_event`, `record_actual_cost_event`, cost event keys,
provider usage extraction, and `ImageProductionCostEvent` persistence.

`app.services.image_production_cost_service` remains a compatibility facade
that aliases the domain module through `sys.modules`. This keeps old imports
and monkeypatches pointed at the same module object while the dirty
`image_creation_service` WIP keeps its approved legacy import.

## Boundaries

- Keep `ImageCreationTask` and `ImageProductionCostEvent` ORM classes in
  `app.db_models`.
- Keep existing commit/rollback/refresh behavior for cost event writes.
- Keep duplicate event handling through `IntegrityError` recovery.
- Do not edit `server/app/services/image_creation_service.py` in this slice.

## Verification

- Add a boundary test for domain file ownership, legacy facade identity,
  README registration, approved legacy import inventory, and cost event
  behavior through the legacy path.
- Run the existing image production cost service tests.
- Run `test_image_creation_strategy_snapshot.py` because image creation uses
  these cost events when strategy snapshots are recorded.

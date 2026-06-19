# Image Generation Metrics Service Domain Design

Status: auto-approved.

## Context

The image generation domain owns the image production router, but that router
still imports `app.services.image_production_metrics_service` for strategy
metric aggregation and refresh. The metrics service is image-generation-specific
business logic, while A/B and recommendation services still need the old import
path until their own domain migrations happen.

## Decision

Move the implementation to
`app.domains.image_generation.image_production_metrics_service` and keep
`app.services.image_production_metrics_service` as a thin `sys.modules`
compatibility facade.

This lets the domain router use a domain-owned metrics service without breaking
existing flat service imports.

## Scope

In scope:

- Create `server/app/domains/image_generation/image_production_metrics_service.py`
  with the current implementation.
- Replace `server/app/services/image_production_metrics_service.py` with a
  compatibility facade.
- Update `server/app/domains/image_generation/image_production_router.py` to
  import metrics helpers from the domain path.
- Update `server/app/domains/image_generation/README.md` to document metrics
  service ownership, facade mapping, and cleanup gates.
- Add focused boundary tests proving old and new metrics service imports resolve
  to the same module object.

Out of scope:

- No behavior changes to task counting, cost event selection, review counting,
  aggregate weighting, low-sample flags, or metric payload shape.
- No cleanup of legacy imports in `image_ab_test_service.py`,
  `image_production_recommendation_service.py`, or existing metrics tests in
  this step.

## Architecture

The domain metrics service owns:

- `refresh_image_strategy_metrics`
- `refresh_all_image_strategy_metrics`
- `aggregate_strategy_metrics_payload`
- `strategy_metrics_payload`
- `_actual_costs`
- `_weighted_average`
- `SUCCESS_TASK_STATUSES`

The legacy service module imports the domain metrics service module, replaces
itself in `sys.modules`, and updates globals so existing imports and monkeypatches
keep targeting the same module object.

## Data Flow

The image production router refreshes metrics through the domain service. The
service still reads image creation tasks, assets, review records, cost events,
and existing metrics through the same SQLAlchemy session, then writes or updates
`ImageProductionMetric` rows exactly as before.

## Error Handling

Error behavior is unchanged. The service continues to flush refreshed metrics
without committing unrelated work, and callers remain responsible for route-level
transaction handling.

## Testing

Add `server/tests/test_image_generation_metrics_service_facade.py` to verify:

- this spec and plan mention
  `app.domains.image_generation.image_production_metrics_service`,
  `app.services.image_production_metrics_service`,
  `refresh_image_strategy_metrics`,
  `refresh_all_image_strategy_metrics`,
  `aggregate_strategy_metrics_payload`, and `strategy_metrics_payload`;
- the domain metrics service file exists;
- the legacy service file is a thin facade with no copied implementation;
- old and new imports resolve to the same module object and expose identical
  key functions/constants;
- the domain image production router imports the domain metrics path;
- the image generation README records metrics ownership, facade mapping, and
  cleanup gate.

Run focused verification:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_metrics_service_facade.py server/tests/test_image_production_metrics_service.py server/tests/test_image_production_migration.py -q
```

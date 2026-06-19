# Image Generation Recommendation Service Domain Design

Status: auto-approved.

## Context

The image generation domain owns the image production router, but strategy
recommendation and A/B winner recommendation logic still live in
`app.services.image_production_recommendation_service`. That service is specific
to image production strategies, metrics, A/B attempts, and approved image
assets, so it belongs with the image generation domain.

## Decision

Move the implementation to
`app.domains.image_generation.image_production_recommendation_service` and keep
`app.services.image_production_recommendation_service` as a thin `sys.modules`
compatibility facade.

This lets the domain router import recommendation logic from the domain while
preserving old imports used by the not-yet-migrated A/B service and tests.

## Scope

In scope:

- Create
  `server/app/domains/image_generation/image_production_recommendation_service.py`
  with the current implementation.
- Replace `server/app/services/image_production_recommendation_service.py` with
  a compatibility facade.
- Update `server/app/domains/image_generation/image_production_router.py` to
  import `strategy_recommendation_payload` from the domain path.
- Update the moved recommendation service to import
  `aggregate_strategy_metrics_payload` from the domain metrics path.
- Update `server/app/domains/image_generation/README.md` to document
  recommendation service ownership, facade mapping, and cleanup gates.
- Add focused boundary tests proving old and new recommendation service imports
  resolve to the same module object.

Out of scope:

- No behavior changes to quality scores, confidence levels, recommendation
  codes, A/B winner eligibility, or approved-asset selection.
- No cleanup of legacy imports in `image_ab_test_service.py` or existing
  recommendation tests in this step.

## Architecture

The domain recommendation service owns:

- `strategy_recommendation_payload`
- `ab_winner_recommendation_payload`
- `_quality_score`
- `_recommendations`
- `_ab_attempt_score`
- `_ab_recommendation_payload`
- recommendation thresholds such as `LOW_SAMPLE_ATTEMPTS` and
  `HIGH_CONFIDENCE_ATTEMPTS`

The legacy service module imports the domain recommendation service module,
replaces itself in `sys.modules`, and updates globals so existing imports and
monkeypatches keep targeting the same module object.

## Data Flow

The image production router asks the domain service for strategy recommendation
payloads. The service still reads strategy rows, metric rows, A/B attempts, and
approved image assets through the same SQLAlchemy session, then returns the same
payload shape to callers.

## Error Handling

Error behavior is unchanged. Missing strategies and unauthorized or missing A/B
groups still raise the same image errors through `image_error`.

## Testing

Add `server/tests/test_image_generation_recommendation_service_facade.py` to
verify:

- this spec and plan mention
  `app.domains.image_generation.image_production_recommendation_service`,
  `app.services.image_production_recommendation_service`,
  `strategy_recommendation_payload`, and
  `ab_winner_recommendation_payload`;
- the domain recommendation service file exists;
- the legacy service file is a thin facade with no copied implementation;
- old and new imports resolve to the same module object and expose identical
  key functions/constants;
- the moved domain recommendation service imports domain metrics;
- the domain image production router imports the domain recommendation path;
- the image generation README records recommendation ownership, facade mapping,
  and cleanup gate.

Run focused verification:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_recommendation_service_facade.py server/tests/test_image_production_recommendation_service.py server/tests/test_image_production_recommendation_api.py -q
```

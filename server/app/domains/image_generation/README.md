# Image Generation Domain

This domain owns the admin image creation and image production route boundary,
plus image production strategy business logic.

## Owned Routes

- `/api/image-creation/*`
- `/api/image-production/*`

## Current Modules

- `image_creation_service.py` owns image creation task idempotency, provider
  payload preparation, Pixelle submit/sync, asset payloads, review decisions,
  cost writes, selection preview validation, and source/reference image
  resolution.
- `image_creation_router.py` owns upload, Pixelle file proxy, task create/read,
  task sync/dispatch, asset list/review, and asset edit endpoints.
- `image_creation_storage.py` owns `IMAGE_CREATION_ROOT`, `save_upload`,
  `save_output_bytes`, public image URLs, and image storage content-type/size
  validation.
- `image_production_cost_service.py` owns `record_estimated_cost_event`,
  `record_actual_cost_event`, image generation cost event keys, provider usage
  extraction, and `ImageProductionCostEvent` writes.
- `image_creation_errors.py` owns `image_error` and structured image API error
  payload construction.
- `image_production_router.py` owns image strategies, metrics refresh, selection
  preview, A/B tests, winner decisions, image-to-video promotion, and strategy
  recommendations.
- `image_ab_test_service.py` owns `preview_ab_group`, `create_ab_group`,
  `refresh_ab_group`, `recommend_ab_winner`, `adopt_ab_winner`,
  `mark_ab_no_winner`, and `serialize_ab_group`.
- `image_asset_bridge_service.py` owns `promote_image_asset_to_video_asset`,
  `video_asset_payload`, image review gate enforcement, scope validation, and
  video asset promotion metadata.
- `image_review_gate_service.py` owns `asset_review_gate`,
  `review_gate_passed`, and `review_gate_rescue_actions`.
- `image_production_strategy_service.py` owns `seed_default_image_strategies`,
  strategy validation, CRUD/version writes, status transitions, and
  `strategy_payload`.
- `image_production_policy_runtime.py` owns `estimate_image_cost`,
  `preview_image_capacity`, `preview_review_gate`, and image production policy
  preview defaults.
- `image_production_metrics_service.py` owns `refresh_image_strategy_metrics`,
  `refresh_all_image_strategy_metrics`, `aggregate_strategy_metrics_payload`,
  and `strategy_metrics_payload`.
- `image_production_recommendation_service.py` owns
  `strategy_recommendation_payload`, `ab_winner_recommendation_payload`, and
  image strategy/A-B recommendation scoring.
- `image_selection_preview_service.py` owns `create_selection_preview`,
  provider-option validation, model/cost/capacity/review preview assembly,
  request hashing, and `ImageSelectionPreview` persistence.
- `image_selection_preview_hash.py` owns `selection_preview_hash_inputs`,
  `selection_preview_request_hash`, and deterministic selection preview request
  hash normalization.
- `image_model_selection_service.py` owns `resolve_image_model_selection`,
  image model capability diagnostics, preferred model handling, fallback
  candidates, warnings, and rescue actions.

## Canonical Imports

The retired router, service, and ORM import packages have been removed. Runtime code, tests, scripts, and new docs must import domain modules directly and use `app.db.models` / `app.db.models.<domain>` for ORM models.

## Boundaries

- Keep image route paths, methods, auth dependencies, response shapes, and route
  function names stable.
- Do not move video production, agency review, AI config, or Pixelle proxy
  ownership into this domain unless a later plan explicitly expands scope.

## Legacy Import Guard

The cleanup gate is complete. Keep the retired import-path and AST inventory tests passing so removed paths stay unavailable.

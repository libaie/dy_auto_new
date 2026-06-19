# Image Generation Domain

This domain owns the admin image creation and image production route boundary,
plus image production strategy business logic.

## Owned Routes

- `/api/image-creation/*`
- `/api/image-production/*`

## Current Modules

- `image_creation_router.py` owns upload, Pixelle file proxy, task create/read,
  task sync/dispatch, asset list/review, and asset edit endpoints.
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

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.image_creation` | `app.domains.image_generation.image_creation_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |
| `app.routers.image_production` | `app.domains.image_generation.image_production_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |
| `app.services.image_ab_test_service` | `app.domains.image_generation.image_ab_test_service` | Domain modules import the domain service path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.services.image_asset_bridge_service` | `app.domains.image_generation.image_asset_bridge_service` | Domain modules import the domain service path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.services.image_review_gate_service` | `app.domains.image_generation.image_review_gate_service` | Domain modules import the domain service path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.services.image_production_strategy_service` | `app.domains.image_generation.image_production_strategy_service` | Domain modules import the domain service path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.services.image_production_policy_runtime` | `app.domains.image_generation.image_production_policy_runtime` | Domain modules import the domain service path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.services.image_production_metrics_service` | `app.domains.image_generation.image_production_metrics_service` | Domain modules import the domain service path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.services.image_production_recommendation_service` | `app.domains.image_generation.image_production_recommendation_service` | Domain modules import the domain service path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.services.image_selection_preview_service` | `app.domains.image_generation.image_selection_preview_service` | Domain modules import the domain service path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.services.image_model_selection_service` | `app.domains.image_generation.image_model_selection_service` | Domain modules import the domain service path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.services.image_selection_preview_hash` | `app.domains.image_generation.image_selection_preview_hash` | Domain modules import the domain helper path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |

## Boundaries

- Keep image route paths, methods, auth dependencies, response shapes, and route
  function names stable.
- Keep remaining service implementations in `app.services.*` until their
  service-split plans are approved.
- Keep ORM models in `app.db_models` during this route-boundary migration.
- Do not move video production, agency review, AI config, or Pixelle proxy
  ownership into this domain unless a later plan explicitly expands scope.

## Compatibility Cleanup Gates

Do not remove legacy router facades until all of these are true:

- `app.main` imports image routers from `app.domains.image_generation`.
- Route/auth snapshots pass against domain endpoint modules.
- Legacy and domain imports resolve to the same module objects during the alias
  phase.
- Existing image creation and image production API tests pass.
- Import inventory shows no unapproved production imports of
  `app.routers.image_creation` or `app.routers.image_production`.

Do not remove the legacy image A/B test service facade until all of these are true:

- `rg "app\.services\.image_ab_test_service" server/app server/tests` returns only compatibility tests, migration docs, or service modules whose domains have not moved yet.
- `test_image_generation_ab_test_service_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.image_generation.image_ab_test_service` directly.

Do not remove the legacy image asset bridge service facade until all of these are true:

- `rg "app\.services\.image_asset_bridge_service" server/app server/tests` returns only compatibility tests, migration docs, or service modules whose domains have not moved yet.
- `test_image_generation_asset_bridge_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.image_generation.image_asset_bridge_service` directly.

Do not remove the legacy image review gate service facade until all of these are true:

- `rg "app\.services\.image_review_gate_service" server/app server/tests` returns only compatibility tests, migration docs, or service modules whose domains have not moved yet.
- `test_image_generation_review_gate_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.image_generation.image_review_gate_service` directly.

Do not remove the legacy image strategy service facade until all of these are true:

- `rg "app\.services\.image_production_strategy_service" server/app server/tests` returns only compatibility tests and migration docs.
- `test_image_generation_strategy_service_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.image_generation.image_production_strategy_service` directly.

Do not remove the legacy image policy runtime facade until all of these are true:

- `rg "app\.services\.image_production_policy_runtime" server/app server/tests` returns only compatibility tests, migration docs, or service modules whose domains have not moved yet.
- `test_image_generation_policy_runtime_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.image_generation.image_production_policy_runtime` directly.

Do not remove the legacy image metrics service facade until all of these are true:

- `rg "app\.services\.image_production_metrics_service" server/app server/tests` returns only compatibility tests, migration docs, or service modules whose domains have not moved yet.
- `test_image_generation_metrics_service_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.image_generation.image_production_metrics_service` directly.

Do not remove the legacy image recommendation service facade until all of these are true:

- `rg "app\.services\.image_production_recommendation_service" server/app server/tests` returns only compatibility tests, migration docs, or service modules whose domains have not moved yet.
- `test_image_generation_recommendation_service_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.image_generation.image_production_recommendation_service` directly.

Do not remove the legacy selection preview service facade until all of these are true:

- `rg "app\.services\.image_selection_preview_service" server/app server/tests` returns only compatibility tests and migration docs.
- `test_image_generation_selection_preview_service_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.image_generation.image_selection_preview_service` directly.

Do not remove the legacy image model selection service facade until all of these are true:

- `rg "app\.services\.image_model_selection_service" server/app server/tests` returns only compatibility tests and migration docs.
- `test_image_generation_model_selection_service_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.image_generation.image_model_selection_service` directly.

Do not remove the legacy selection preview hash facade until all of these are true:

- `rg "app\.services\.image_selection_preview_hash" server/app server/tests` returns only compatibility tests, migration docs, or service modules whose domains have not moved yet.
- `test_image_generation_selection_preview_hash_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.image_generation.image_selection_preview_hash` directly.

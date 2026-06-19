# Video Production Domain

This domain owns the video production control-plane HTTP routes.

## Owned Routes

- `/api/video-production/*`

## Not Owned

- Production ORM models stay in `app.db_models`.
- Database session helpers stay in `app.database`.
- Auth dependencies stay in `app.deps`.
- Production orchestration, worker execution, queues, retries, reviews, costs,
  readiness, and text artifacts stay in `app.services.*`.
- Video library routes stay in `app.domains.video_library`.

## Current Modules

- `production_action_result.py` owns `ProductionActionResult` and action result
  HTTP detail serialization.
- `production_errors.py` owns `ProductionErrorCode`,
  `ProductionRepairableError`, and `to_http_detail`.
- `production_state_contract.py` owns provider task status constants, cost
  reservation status constants, `asset_is_reviewable`,
  `provider_task_is_active`, and `validate_transition`.
- `production_review_service.py` owns `SUPPORTED_BULK_REVIEW_ACTIONS`,
  `GATED_ASSET_TYPES`, `SUPPORTED_BULK_ASSET_TYPES`, and
  `apply_bulk_review_action`.
- `production_segment_detail_service.py` owns `_asset_payload` and
  `get_segment_detail` for segment detail route payloads.
- `production_segment_service.py` owns `retry_segment`, the domain-level retry
  entry point for individual production segments.
- `production_cost_summary_service.py` owns `_ZERO_RESERVATION_COSTS`,
  `_ACTIVE_RESERVATION_STATUSES`, and `get_run_costs`.
- `production_cost_service.py` owns `assert_budget_available`,
  `record_cost_event`, and `pause_plan_for_budget`.
- `production_status.py` owns plan, job, segment, stage, continuity, and
  reference constants such as `JOB_QUEUED` and
  `REFERENCE_CHARACTER_ANCHOR`.
- `production_status_aggregation.py` owns `_parent_status` and
  `recompute_from_segment`, which roll segment status changes up to shots,
  scenes, episodes, and plans.
- `video_production_run_types.py` owns `REAL_SHORT_E2E`,
  `MOCK_SERIES_SCALE`, `LEGACY_EPISODE_RUN`, `validate_run_type`, and run type
  classification helpers.
- `provider_cost_reservation_service.py` owns
  `_ACTIVE_RESERVATION_STATUSES`, `_PLAN_LOCKS`, `active_reserved_cost`,
  `create_cost_reservation`, `settle_reservation`, and reservation lifecycle
  transitions.
- `asset_storage_guard.py` owns `ALLOWED_PROVIDER_SCHEMES`,
  `ALLOWED_IMAGE_MAGIC`, `ALLOWED_VIDEO_MAGIC`, and
  `persist_provider_asset`.
- `provider_capability_service.py` owns `DEFAULT_REAL_PROVIDER_CAPABILITY`,
  `capability_from_model_config`, and `assert_real_paid_allowed`.
- `provider_stage_task_service.py` owns `request_hash`,
  `provider_stage_idempotency_key`, `get_or_create_stage_task`,
  `set_task_status`, and `claim_stage_task_for_submit`.
- `video_production_router.py` owns route request models such as
  `StartRunRequest` and `OneSentenceVideoRequest`, payload helpers such as
  `_run_payload`, `_asset_payload`, and `_provider_stage_task_payload`,
  HTTP error mapping helpers, and all `/api/video-production/*` route handlers.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.video_production` | `app.domains.video_production.video_production_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |
| `app.services.asset_storage_guard` | `app.domains.video_production.asset_storage_guard` | Domain modules import the domain helper path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.services.production_action_result` | `app.domains.video_production.production_action_result` | Domain modules import the domain helper path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.services.production_cost_service` | `app.domains.video_production.production_cost_service` | Domain modules import the domain helper path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.services.production_cost_summary_service` | `app.domains.video_production.production_cost_summary_service` | Domain modules import the domain helper path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.services.production_errors` | `app.domains.video_production.production_errors` | Domain modules import the domain helper path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.services.production_review_service` | `app.domains.video_production.production_review_service` | Domain modules import the domain helper path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.services.production_segment_detail_service` | `app.domains.video_production.production_segment_detail_service` | Domain modules import the domain helper path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.services.production_segment_service` | `app.domains.video_production.production_segment_service` | Domain modules import the domain helper path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.services.production_status` | `app.domains.video_production.production_status` | Domain modules import the domain helper path directly, and legacy imports remain only in compatibility tests, migration docs, approved cross-domain consumers, or service modules whose domains have not moved yet. |
| `app.services.production_status_aggregation` | `app.domains.video_production.production_status_aggregation` | Domain modules import the domain helper path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.services.video_production_run_types` | `app.domains.video_production.video_production_run_types` | Domain modules import the domain helper path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.services.provider_capability_service` | `app.domains.video_production.provider_capability_service` | Domain modules import the domain helper path directly, and legacy imports remain only in compatibility tests, migration docs, approved cross-domain consumers, or service modules whose domains have not moved yet. |
| `app.services.provider_cost_reservation_service` | `app.domains.video_production.provider_cost_reservation_service` | Domain modules import the domain helper path directly, and legacy imports remain only in compatibility tests, migration docs, approved cross-domain consumers, or service modules whose domains have not moved yet. |
| `app.services.provider_stage_task_service` | `app.domains.video_production.provider_stage_task_service` | Domain modules import the domain helper path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.services.production_state_contract` | `app.domains.video_production.production_state_contract` | Domain modules import the domain helper path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |

## Boundaries

- Preserve route paths, route names, auth dependencies, and response shapes.
- Preserve admin-role protection on every route.
- Preserve monkeypatch compatibility for `app.routers.video_production`, notably
  helpers like `edit_image_asset`.
- Preserve service-layer ownership of production state transitions.
- Preserve background helpers for one-sentence references and real worker steps.

## Compatibility Cleanup Gates

Do not remove the legacy router facade until all of these are true:

- `app.main` imports `video_production_router` from
  `app.domains.video_production`.
- Route/auth snapshots pass against the domain endpoint module.
- Legacy and domain imports resolve to the same module object during the alias
  phase.
- Focused video production API, start-flow, worker, readiness, and mocked E2E
  tests pass.
- Import inventory shows no unapproved production imports of
  `app.routers.video_production`.

Do not remove the legacy production action result facade until all of these are true:

- `rg "app\.services\.production_action_result" server/app server/tests` returns only compatibility tests, migration docs, or service modules whose domains have not moved yet.
- `test_video_production_action_result_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.video_production.production_action_result` directly.

Do not remove the legacy asset storage guard facade until all of these are true:

- `rg "app\.services\.asset_storage_guard" server/app server/tests` returns only compatibility tests, migration docs, or service modules whose domains have not moved yet.
- `test_video_production_asset_storage_guard_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.video_production.asset_storage_guard` directly.
- Direct domain storage coverage proves `ALLOWED_PROVIDER_SCHEMES` and
  `persist_provider_asset` behavior without legacy imports.

Do not remove the legacy production cost summary service facade until all of these are true:

- `rg "app\.services\.production_cost_summary_service" server/app server/tests` returns only compatibility tests, migration docs, or service modules whose domains have not moved yet.
- `test_video_production_cost_summary_service_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.video_production.production_cost_summary_service` directly.
- Direct domain cost summary coverage proves `_ZERO_RESERVATION_COSTS` and
  `get_run_costs` behavior without legacy imports.

Do not remove the legacy production cost service facade until all of these are true:

- `rg "app\.services\.production_cost_service" server/app server/tests` returns only compatibility tests, migration docs, or service modules whose domains have not moved yet.
- `test_video_production_cost_service_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.video_production.production_cost_service` directly.
- Direct domain cost coverage proves `record_cost_event` and
  `pause_plan_for_budget` behavior without legacy imports.

Do not remove the legacy production status facade until all of these are true:

- `rg "app\.services\.production_status" server/app server/tests` returns only compatibility tests, migration docs, approved cross-domain consumers, or service modules whose domains have not moved yet.
- `test_video_production_status_contract_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.video_production.production_status` directly.
- Direct domain status coverage proves representative constants such as
  `JOB_QUEUED` and `REFERENCE_CHARACTER_ANCHOR` without legacy imports.

Do not remove the legacy production status aggregation facade until all of these are true:

- `rg "app\.services\.production_status_aggregation" server/app server/tests` returns only compatibility tests, migration docs, or service modules whose domains have not moved yet.
- `test_video_production_status_aggregation_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.video_production.production_status_aggregation` directly.
- Direct domain status aggregation coverage proves `recompute_from_segment` behavior without legacy imports.

Do not remove the legacy video production run types facade until all of these are true:

- `rg "app\.services\.video_production_run_types" server/app server/tests` returns only compatibility tests, migration docs, or service modules whose domains have not moved yet.
- `test_video_production_run_types_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.video_production.video_production_run_types` directly.
- Direct domain run type coverage proves `REAL_SHORT_E2E`,
  `MOCK_SERIES_SCALE`, and `validate_run_type` behavior without legacy imports.

Do not remove the legacy production state contract facade until all of these are true:

- `rg "app\.services\.production_state_contract" server/app server/tests` returns only compatibility tests, migration docs, or service modules whose domains have not moved yet.
- `test_video_production_state_contract_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.video_production.production_state_contract` directly.

Do not remove the legacy production review service facade until all of these are true:

- `rg "app\.services\.production_review_service" server/app server/tests` returns only compatibility tests, migration docs, or service modules whose domains have not moved yet.
- `test_video_production_review_service_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.video_production.production_review_service` directly.
- Direct domain review coverage proves `SUPPORTED_BULK_REVIEW_ACTIONS` and
  `apply_bulk_review_action` behavior without legacy imports.

Do not remove the legacy production segment service facade until all of these are true:

- `rg "app\.services\.production_segment_service" server/app server/tests` returns only compatibility tests, migration docs, or service modules whose domains have not moved yet.
- `test_video_production_segment_service_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.video_production.production_segment_service` directly.
- Direct domain segment coverage proves `retry_segment` behavior without legacy imports.

Do not remove the legacy production segment detail service facade until all of these are true:

- `rg "app\.services\.production_segment_detail_service" server/app server/tests` returns only compatibility tests, migration docs, or service modules whose domains have not moved yet.
- `test_video_production_segment_detail_service_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.video_production.production_segment_detail_service` directly.
- Direct domain segment detail coverage proves `get_segment_detail` behavior without legacy imports.

Do not remove the legacy provider stage task service facade until all of these are true:

- `rg "app\.services\.provider_stage_task_service" server/app server/tests` returns only compatibility tests, migration docs, or service modules whose domains have not moved yet.
- `test_video_production_provider_stage_task_service_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.video_production.provider_stage_task_service` directly.
- Direct domain task helper coverage proves `get_or_create_stage_task` and
  `claim_stage_task_for_submit` behavior without legacy imports.

Do not remove the legacy provider cost reservation service facade until all of these are true:

- `rg "app\.services\.provider_cost_reservation_service" server/app server/tests` returns only compatibility tests, migration docs, approved cross-domain consumers, or service modules whose domains have not moved yet.
- `test_video_production_provider_cost_reservation_service_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.video_production.provider_cost_reservation_service` directly.
- Direct domain reservation coverage proves `_PLAN_LOCKS`,
  `active_reserved_cost`, and `settle_reservation` behavior without legacy
  imports.

Do not remove the legacy provider capability service facade until all of these are true:

- `rg "app\.services\.provider_capability_service" server/app server/tests` returns only compatibility tests, migration docs, approved cross-domain consumers, or service modules whose domains have not moved yet.
- `test_video_production_provider_capability_service_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.video_production.provider_capability_service` directly.
- Direct domain capability coverage proves `capability_from_model_config` and
  `assert_real_paid_allowed` behavior without legacy imports.

Do not remove the legacy production errors facade until all of these are true:

- `rg "app\.services\.production_errors" server/app server/tests` returns only compatibility tests, migration docs, or service modules whose domains have not moved yet.
- `test_video_production_error_helper_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.video_production.production_errors` directly.

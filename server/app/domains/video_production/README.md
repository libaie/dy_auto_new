# Video Production Domain

This domain owns the video production control-plane HTTP routes.

## Owned Routes

- `/api/video-production/*`

## Not Owned

- `VideoCollection` lives in `app.db.models.video_production`.
- Database session helpers stay in `app.database`.
- Auth dependencies stay in `app.deps`.
- Video library routes stay in `app.domains.video_library`.

## Current Modules

- `production_action_result.py` owns `ProductionActionResult` and action result
  HTTP detail serialization.
- `production_errors.py` owns `ProductionErrorCode`,
  `ProductionRepairableError`, and `to_http_detail`.
- `production_gate_evaluator.py` owns `STAGE_ASSET_TYPES` and
  `evaluate_stage_gate` for image, video, and compose stage readiness gates.
- `production_state_contract.py` owns provider task status constants, cost
  reservation status constants, `asset_is_reviewable`,
  `provider_task_is_active`, and `validate_transition`.
- `production_review_service.py` owns `SUPPORTED_BULK_REVIEW_ACTIONS`,
  `GATED_ASSET_TYPES`, `SUPPORTED_BULK_ASSET_TYPES`, and
  `apply_bulk_review_action`.
- `production_retry_service.py` owns `get_retry_impact`,
  `retry_segment_with_impact`, and retry job enqueue handoff for production
  segments.
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
- `production_plan_service.py` owns `create_episode_production_plan`,
  `ensure_episode_production_plan`, and `ensure_shot_segments` for converting
  locked style and episode storyboards into production plans.
- `production_run_service.py` owns linked run creation, episode production
  start orchestration, storyboard retiming, text artifact preparation, and
  production observability events for run starts.
- `production_queue_service.py` owns production job enqueue, claim, completion,
  retry-wait, pause, and resume helpers.
- `production_worker_service.py` owns real provider worker-step execution,
  claimed job processing, deferred agency stage gates, provider result
  persistence, and run status updates after stage jobs.
- `production_collection_service.py` owns `create_collection_from_approved_episodes`
  for packaging approved episode videos into draft collections.
- `app.db.models.video_production` owns the `VideoCollection` ORM class body.
- `production_tree_service.py` owns `get_run_tree` and tree payload helpers for
  plan and run production hierarchy endpoints.
- `review_asset_edit_service.py` owns `ReviewAssetEditError`,
  `edit_image_asset`, and `void_asset_version` for review-time asset edits and
  voiding.
- `video_production_run_types.py` owns `REAL_SHORT_E2E`,
  `MOCK_SERIES_SCALE`, `LEGACY_EPISODE_RUN`, `validate_run_type`, and run type
  classification helpers.
- `video_production_state.py` owns `IMAGE_READY_STATUS`,
  `VIDEO_READY_STATUS`, `production_segment_frame_ids`, and
  `recompute_run_gate` for run stage gate state.
- `video_production_readiness.py` owns `build_run_readiness` and readiness
  block payload helpers for run control-plane routes.
- `one_sentence_video_service.py` owns one-sentence-to-video orchestration,
  placeholder episodes, style/storyboard reviews, reference generation
  scheduling, text artifact writes, and run startup handoff.
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
- `provider_stage_executor.py` owns `ProviderStageExecutor`,
  `PROVIDER_THROTTLE_DEPLOYMENT_CONTRACT`, and real provider submit/sync
  throttle execution.
- `mock_scale_scheduler_service.py` owns `create_mock_scale_run` and
  `advance_mock_scheduler` for provider-free mock scale production runs.
- `video_production_router.py` owns route request models such as
  `StartRunRequest` and `OneSentenceVideoRequest`, payload helpers such as
  `_run_payload`, `_asset_payload`, and `_provider_stage_task_payload`,
  HTTP error mapping helpers, and all `/api/video-production/*` route handlers.
- `video_production_service.py` owns staged video production orchestration,
  provider stage submission and sync, AI and final audits, asset approval and
  regeneration, creative patch gates, backtrack triggers, and linked plan stage
  payload construction.

## Canonical Imports

The retired router, service, and ORM import packages have been removed. Runtime code, tests, scripts, and new docs must import domain modules directly and use `app.db.models` / `app.db.models.<domain>` for ORM models.

## Boundaries

- Preserve route paths, route names, auth dependencies, and response shapes.
- Preserve admin-role protection on every route.
- Preserve video production domain ownership of production state transitions.
- Preserve background helpers for one-sentence references and real worker steps.

## Legacy Import Guard

The cleanup gate is complete. Keep the retired import-path and AST inventory tests passing so removed paths stay unavailable.

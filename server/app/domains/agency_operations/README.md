# Agency Operations Domain

This domain owns agency transparency, creative patch, multimodal review, and
repair task routes.

## Owned Routes

- `/api/agency/*`

## Not Owned

- Agency ORM models such as `AgencyExpertInvocation` and `AgencyCreativePatch`
- Database session helpers stay in `app.database`.
- Auth dependencies stay in `app.deps`.
- Creative patch mutation lives in
  `app.domains.agency_operations.agency_creative_patch_service`.
- Debate audit logic lives in
  `app.domains.agency_operations.agency_debate_audit`.
- Provider reservation accounting lives in
  `app.domains.video_production.provider_cost_reservation_service`.

## Current Modules

- `agency_console.py` owns read-only agency transparency payloads for series
  detail, including expert status, decision log, repair summary, creative patch
  summary, readiness, quality report, and current episode context.
- `agency_orchestrator.py` owns `STAGE_DAG`, `AgencyOrchestrator`, staged expert
  review execution, invocation persistence handoff, and optional debate audit
  merging.
- `agency_router.py` owns all `/api/agency/*` route handlers, agency response
  shaping, `_redact_model_config_snapshot`, repair task summaries, retry action
  decisions, `repair-tasks` endpoints, and paid repair authorization endpoints.
- `agency_manifest.py` owns `AgencyManifest`, `AgencyManifestError`,
  `EXPERT_IDS`, manifest loading, expert markdown hash checks, legacy expert
  lookup, and manifest verification.
- `agency_contracts.py` owns agency status enums and Pydantic response models
  such as `AgencyConsoleResponse` and `AgencyInvocationSummary`.
- `agency_repair_contracts.py` owns agency auto-repair constants, repair task
  models, repair classification results, and repair action helper labels.
- `agency_repair_classifier.py` owns repair-task classification from expert
  output summaries into repair tasks and manual gates.
- `agency_repair_orchestrator.py` owns converting repair tasks into manual
  audit events or auto-repair production jobs.
- `agency_scorecard_contracts.py` owns `normalize_scorecard` and
  `scorecard_blocks_stage` for agency scorecard verdict contracts.
- `agency_debate_policy.py` owns stage-specific debate role policies for
  critic, defender, arbiter, and business focus checklists.
- `agency_multimodal_review.py` owns `build_multimodal_asset_context` and
  `run_multimodal_asset_review` for real generated asset review handoff.
- `agency_creative_patch_contracts.py` owns creative patch enums,
  `CreativePatchProposal`, and `normalize_patch_payload`.
- `agency_backtrack_policy.py` owns `trigger_backtrack_if_needed` for repeated
  asset review failure backtracking into upstream auto-repair jobs.
- `agency_repair_executor.py` owns agency auto-repair production job execution,
  including manual paid-reference gates, recheck audit events, and segment
  prompt micro-tuning handoff back to image generation.
- `agency_prompting.py` owns `ExpertPrompt` and `build_expert_prompt` for
  agency expert prompt safety, schema, and multimodal user payload construction.
- `agency_runtime.py` owns `AgencySkillRuntime`, default OpenAI-compatible
  expert model calls, expert output parsing, scorecard normalization, and
  runtime secret redaction.
- `agency_persistence.py` owns agency expert invocation idempotency, retryable
  resume state, finalization, repair task classification, creative patch
  creation, and production audit event mirroring.
- `video_agency_team.py` owns the embedded video agency team definition,
  current team version checks, role summaries, and agency context building for
  story, style, and production review stages.

## Canonical Imports

The retired router, service, and ORM import packages have been removed. Runtime code, tests, scripts, and new docs must import domain modules directly and use `app.db.models` / `app.db.models.<domain>` for ORM models.

## Boundaries

- Preserve route paths, route names, auth dependencies, and response shapes.
- Preserve admin-only access checks for expert, invocation, creative patch,
  multimodal review, and repair task endpoints.
- Preserve secret redaction for model snapshots.
- Preserve repair retry and paid authorization budget semantics.

## Legacy Import Guard

The cleanup gate is complete. Keep the retired import-path and AST inventory tests passing so removed paths stay unavailable.

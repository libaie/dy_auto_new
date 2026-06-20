# Agency Operations Domain

This domain owns agency transparency, creative patch, multimodal review, and
repair task routes.

## Owned Routes

- `/api/agency/*`

## Not Owned

- Agency ORM models such as `AgencyExpertInvocation` and `AgencyCreativePatch`
  stay in `app.db_models`.
- Database session helpers stay in `app.database`.
- Auth dependencies stay in `app.deps`.
- Creative patch mutation stays in `app.services.agency_creative_patch_service`.
- Provider reservation accounting stays in
  `app.services.provider_cost_reservation_service`.

## Current Modules

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
- `agency_multimodal_review.py` owns `build_multimodal_asset_context` and
  `run_multimodal_asset_review` for real generated asset review handoff.
- `agency_creative_patch_contracts.py` owns creative patch enums,
  `CreativePatchProposal`, and `normalize_patch_payload`.
- `agency_backtrack_policy.py` owns `trigger_backtrack_if_needed` for repeated
  asset review failure backtracking into upstream auto-repair jobs.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.agency` | `app.domains.agency_operations.agency_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |
| `app.services.agency_manifest` | `app.domains.agency_operations.agency_manifest` | Keep while dirty service modules have approved compatibility imports; remove only after import inventory shows no production legacy imports. |
| `app.services.agency_contracts` | `app.domains.agency_operations.agency_contracts` | Keep while legacy tests or dirty service modules import agency response contracts from `app.services`; remove after import inventory is clean. |
| `app.services.agency_repair_contracts` | `app.domains.agency_operations.agency_repair_contracts` | Keep while dirty service modules import repair contracts from `app.services`; remove after import inventory is clean. |
| `app.services.agency_repair_classifier` | `app.domains.agency_operations.agency_repair_classifier` | Keep while dirty service modules import the repair classifier from `app.services`; remove after import inventory is clean. |
| `app.services.agency_repair_orchestrator` | `app.domains.agency_operations.agency_repair_orchestrator` | Keep while dirty service modules import repair orchestration from `app.services`; remove after import inventory is clean. |
| `app.services.agency_scorecard_contracts` | `app.domains.agency_operations.agency_scorecard_contracts` | Keep while dirty agency service modules import scorecard contracts from `app.services`; remove after import inventory is clean. |
| `app.services.agency_multimodal_review` | `app.domains.agency_operations.agency_multimodal_review` | Keep while legacy tests monkeypatch multimodal review through `app.services`; remove after import inventory is clean. |
| `app.services.agency_creative_patch_contracts` | `app.domains.agency_operations.agency_creative_patch_contracts` | Keep while dirty creative patch service code imports contracts from `app.services`; remove after import inventory is clean. |
| `app.services.agency_backtrack_policy` | `app.domains.agency_operations.agency_backtrack_policy` | Keep while dirty video production service code imports backtrack policy from `app.services`; remove after import inventory is clean. |

## Boundaries

- Preserve route paths, route names, auth dependencies, and response shapes.
- Preserve admin-only access checks for expert, invocation, creative patch,
  multimodal review, and repair task endpoints.
- Preserve secret redaction for model snapshots.
- Preserve repair retry and paid authorization budget semantics.
- Preserve monkeypatch compatibility for `app.routers.agency` during the alias
  phase.
- Preserve monkeypatch compatibility for `app.services.agency_manifest` while
  dirty service modules keep approved compatibility imports.

## Compatibility Cleanup Gates

Do not remove the legacy router facade until all of these are true:

- `app.main` imports `agency_router` from `app.domains.agency_operations`.
- Route/auth snapshots pass against the domain endpoint module.
- Legacy and domain imports resolve to the same module object during the alias
  phase.
- Existing agency API, console, repair, and runtime tests pass.
- Import inventory shows no unapproved production imports of `app.routers.agency`.

Do not remove the legacy agency manifest facade until all of these are true:

- `rg "app\.services\.agency_manifest" server/app server/tests` returns only
  compatibility tests, migration docs, or service modules whose domains have not
  moved yet.
- Direct domain manifest coverage proves `AgencyManifest`, expert lookup,
  markdown hash checks, legacy expert lookup, and `verify_manifest` behavior.
- Domain-owned production modules import
  `app.domains.agency_operations.agency_manifest` directly.

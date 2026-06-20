# Agency Persistence Domain Design

Date: 2026-06-20

## Goal

Move agency invocation persistence and audit finalization from
`app.services.agency_persistence` into
`app.domains.agency_operations.agency_persistence` without changing behavior or
public import compatibility.

## Current Context

`server/app/services/agency_persistence.py` owns two persistence functions:

- `create_or_resume_invocation`
- `finalize_invocation_and_audit`

It has no current diff in the worktree. Production callers still import the
legacy service path from `agency_orchestrator.py` and
`ai_video_series/story_generator_expert.py`, so the old import path must remain
valid during migration.

## Design

Use the same compatibility pattern as the existing agency domain migrations:

1. Copy the current implementation into
   `server/app/domains/agency_operations/agency_persistence.py`.
2. Replace `server/app/services/agency_persistence.py` with a module-alias
   facade to the domain module.
3. Document ownership and the facade exit condition in
   `server/app/domains/agency_operations/README.md`.

No database schema, route, API response, audit payload, creative patch, repair
task, or production-event behavior changes are included.

## Dependencies Kept In Place

- ORM classes stay in `app.db_models`.
- `record_production_event` is imported from
  `app.domains.production_observability.production_observability_service`.
- Creative patch creation stays in
  `app.services.agency_creative_patch_service`.
- Repair classification and orchestration are imported directly from
  `app.domains.agency_operations.agency_repair_classifier` and
  `app.domains.agency_operations.agency_repair_orchestrator`.

## Verification

- New facade test proves the spec, plan, README, domain file, and legacy module
  alias.
- Existing `server/tests/test_agency_persistence.py` proves invocation
  idempotency, audit mirroring, creative patch rows, terminal idempotency, and
  failure repair details still work through the legacy import path.
- App import smoke proves the server still imports after the module move.

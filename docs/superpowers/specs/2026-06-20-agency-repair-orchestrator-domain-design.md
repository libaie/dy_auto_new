# Agency Repair Orchestrator Domain Design

## Goal

Move agency auto-repair orchestration from
`app.services.agency_repair_orchestrator` into the `agency_operations` domain
while keeping the legacy import path working.

## Decision

Use `app.domains.agency_operations.agency_repair_orchestrator` as the canonical
module. The service turns agency repair tasks into manual-required audit events
or production repair jobs, which is agency repair workflow logic.

## Scope

In scope:

- Create `server/app/domains/agency_operations/agency_repair_orchestrator.py`
  with the existing implementation.
- Update canonical imports to use
  `app.domains.agency_operations.agency_repair_contracts`,
  `app.domains.video_production.production_status`, and
  `app.domains.video_production.provider_cost_reservation_service`.
- Replace `server/app/services/agency_repair_orchestrator.py` with a
  compatibility facade.
- Register the facade in the agency-operations README.
- Add a boundary test for module identity, implementation location, and basic
  manual-required repair behavior.

Out of scope:

- No repair scheduling behavior changes.
- No production queue/status behavior changes.
- No edits to dirty agency persistence or worker modules.
- No cleanup of legacy imports in existing tests or service modules.

## Verification

The new test must prove:

- `app.domains.agency_operations.agency_repair_orchestrator` owns
  `enqueue_repair_tasks_for_invocation`.
- Canonical imports use domain paths for agency repair contracts and video
  production helpers.
- `app.services.agency_repair_orchestrator` aliases the domain module.
- Existing manual-required behavior works through the legacy path.
- The README records the facade.

# Agency Repair Contracts Domain Design

## Goal

Move agency repair contract models from `app.services.agency_repair_contracts`
into the `agency_operations` domain while keeping the legacy import path
working.

## Decision

Use `app.domains.agency_operations.agency_repair_contracts` as the canonical
module. The file defines auto-repair stage constants, repair task Pydantic
models, repair classification result models, and repair action helpers used by
agency repair workflows. Those are agency domain contracts.

## Scope

In scope:

- Create `server/app/domains/agency_operations/agency_repair_contracts.py` with
  the existing implementation.
- Replace `server/app/services/agency_repair_contracts.py` with a compatibility
  facade.
- Register the facade in the agency-operations README.
- Add a boundary test for module identity, implementation location, and basic
  repair contract behavior.

Out of scope:

- No model field changes.
- No repair policy changes.
- No edits to dirty agency repair service modules.
- No cleanup of legacy imports in service modules or existing tests.

## Verification

The new test must prove:

- `app.domains.agency_operations.agency_repair_contracts` owns
  `AUTO_REPAIR_STAGE`, `AutoRepairPolicy`, `RepairTask`,
  `RepairClassificationResult`, and `action_for_task`.
- `app.services.agency_repair_contracts` aliases the domain module.
- Existing validation behavior still works through the legacy path.
- The README records the facade.

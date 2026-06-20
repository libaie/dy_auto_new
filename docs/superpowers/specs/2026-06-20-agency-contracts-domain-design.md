# Agency Contracts Domain Design

## Goal

Move agency API contract models from `app.services.agency_contracts` into the
`agency_operations` domain while keeping the legacy import path working.

## Decision

Use `app.domains.agency_operations.agency_contracts` as the canonical module.
The file contains status enums and Pydantic response models for agency routes
and console payloads, so it belongs with the agency route domain.

## Scope

In scope:

- Create `server/app/domains/agency_operations/agency_contracts.py` with the
  existing implementation.
- Keep `AgencyConsoleResponse`, `AgencyInvocationSummary`,
  `AgencyExecutionStatus`, and the other agency contract models unchanged.
- Replace `server/app/services/agency_contracts.py` with a compatibility
  facade.
- Register the facade in the agency-operations README.
- Add a boundary test for module identity, implementation location, and basic
  model behavior.

Out of scope:

- No schema field changes.
- No route changes.
- No edits to existing dirty agency tests.
- No cleanup of legacy imports in tests or service modules.

## Verification

The new test must prove:

- `app.domains.agency_operations.agency_contracts` owns the agency status enums
  and response models.
- `app.services.agency_contracts` aliases the domain module.
- Existing model behavior still works through the legacy path.
- The README records the facade.

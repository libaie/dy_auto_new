# Agency Repair Classifier Domain Design

## Goal

Move agency repair-task classification from `app.services.agency_repair_classifier`
into the `agency_operations` domain while keeping the legacy import path
working.

## Decision

Use `app.domains.agency_operations.agency_repair_classifier` as the canonical
module. The classifier interprets agency expert output into repair tasks and
manual gates, so it belongs with agency repair workflows.

## Scope

In scope:

- Create `server/app/domains/agency_operations/agency_repair_classifier.py`
  with the existing implementation.
- Update the canonical module to import repair contracts from
  `app.domains.agency_operations.agency_repair_contracts`.
- Replace `server/app/services/agency_repair_classifier.py` with a
  compatibility facade.
- Register the facade in the agency-operations README.
- Add a boundary test for module identity, implementation location, and basic
  classification behavior.

Out of scope:

- No classifier behavior changes.
- No edits to dirty agency persistence or worker modules.
- No cleanup of legacy imports in existing tests or service modules.

## Verification

The new test must prove:

- `app.domains.agency_operations.agency_repair_classifier` owns
  `classify_repair_tasks`.
- The canonical module imports repair contracts from the agency domain.
- `app.services.agency_repair_classifier` aliases the domain module.
- Existing manual fallback and paid repair classification behavior still works.
- The README records the facade.

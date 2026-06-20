# Model Migration Domain Design

## Goal

Move legacy AI model settings migration helpers from `app.services.migration`
into the `model_configuration` domain while keeping the legacy import path
working.

## Decision

Use `app.domains.model_configuration.migration` as the canonical module. The
module creates `AIModel` records from legacy Settings, Pixelle, and Seedance
configuration, so it belongs with model configuration rather than generic
system operations.

## Scope

In scope:

- Create `server/app/domains/model_configuration/migration.py` with the current
  migration implementation.
- Replace `server/app/services/migration.py` with a compatibility facade.
- Update the moved implementation to import crypto helpers from
  `app.domains.system_configuration.crypto`.
- Register the facade in the model-configuration README.
- Add a boundary test for module identity, implementation location, and docs.

Out of scope:

- No migration rule changes.
- No new migration execution path.
- No edits to existing migration behavior tests.
- No cleanup of legacy imports in tests or service compatibility callers.

## Verification

The new boundary test must prove:

- `app.domains.model_configuration.migration` owns
  `migrate_legacy_settings`, `_normalize_model_name`, and `_find_existing`.
- `app.services.migration` aliases the domain module.
- The canonical implementation imports crypto helpers from the
  `system_configuration` domain.
- The README records the facade.

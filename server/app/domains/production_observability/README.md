# Production Observability Domain

This domain owns shared production audit-event writing and secret redaction.

## Owned Routes

- None.

## Not Owned

- `ProductionAuditEvent` ORM model definitions stay in `app.db_models`.
- Database session helpers stay in `app.database`.
- Video production, image generation, and agency operation workflows stay in
  their own domains or services.

## Current Modules

- `production_observability_service.py` owns `SECRET_KEYS`, `_normalize_key`,
  `_redact`, and `record_production_event` for redacted
  `ProductionAuditEvent` persistence without committing caller-owned
  transactions.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.services.production_observability` | `app.domains.production_observability.production_observability_service` | Domain modules import the shared domain path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |

## Boundaries

- Preserve recursive secret redaction for dictionaries and lists.
- Preserve caller-owned transaction behavior; event recording flushes only.
- Keep production workflow ownership in the consuming business domains.

## Compatibility Cleanup Gates

Do not remove the legacy production observability facade until all of these are true:

- `rg "app\.services\.production_observability" server/app server/tests` returns only compatibility tests, migration docs, or service modules whose domains have not moved yet.
- `test_production_observability_domain_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.production_observability.production_observability_service` directly.
- Direct domain observability coverage proves `_normalize_key`, `_redact`, and
  `record_production_event` behavior without legacy imports.

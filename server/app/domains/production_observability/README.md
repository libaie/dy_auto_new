# Production Observability Domain

This domain owns shared production audit-event writing and secret redaction.

## Owned Routes

- None.

## Not Owned

- Database session helpers stay in `app.database`.
- Video production, image generation, and agency operation workflows stay in
  their own domains or services.

## Current Modules

- `production_observability_service.py` owns `SECRET_KEYS`, `_normalize_key`,
  `_redact`, and `record_production_event` for redacted
  `ProductionAuditEvent` persistence without committing caller-owned
  transactions.
- `app.db.models.production_observability` owns the `ProductionAuditEvent` ORM
  class body.

## Canonical Imports

The retired router, service, and ORM import packages have been removed. Runtime code, tests, scripts, and new docs must import domain modules directly and use `app.db.models` / `app.db.models.<domain>` for ORM models.

## Boundaries

- Preserve recursive secret redaction for dictionaries and lists.
- Preserve caller-owned transaction behavior; event recording flushes only.
- Keep production workflow ownership in the consuming business domains.

## Legacy Import Guard

The cleanup gate is complete. Keep the retired import-path and AST inventory tests passing so removed paths stay unavailable.

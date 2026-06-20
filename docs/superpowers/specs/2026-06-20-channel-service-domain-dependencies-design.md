# Channel Service Domain Dependencies Design

Date: 2026-06-20

## Goal

Remove `account_operations.channel_service` imports of legacy `content_service`
and `stats_service` facades.

## Design

`app.domains.account_operations.channel_service` should import:

- `content_service` from `app.domains.content_collection.content_service`.
- `stats_service` from `app.domains.reporting.stats_service`.

Keep `app.services.content_service` and `app.services.stats_service` as
compatibility facades for tests and service modules whose owning domains have
not moved.

## Verification

Add one boundary test proving channel service uses direct domain imports for
content/stats and both legacy facades still resolve to the same module objects
as their domain implementations.

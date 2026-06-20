# Device Reporting Domain Imports Design

Date: 2026-06-20

## Goal

Remove device reporting imports of legacy `stats_service` and
`channel_service` facades.

## Design

`app.domains.device_operations.reporting` should import:

- `stats_service` from `app.domains.reporting.stats_service`.
- `channel_service` from `app.domains.account_operations.channel_service`.

Keep `app.services.stats_service` and `app.services.channel_service` as
compatibility facades for tests and service modules whose owning domains have
not moved.

## Verification

Add one boundary test proving device reporting uses the direct domain imports
and both legacy facades still resolve to the same module objects as their
domain implementations.

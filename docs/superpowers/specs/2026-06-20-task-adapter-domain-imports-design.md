# Task Adapter Domain Imports Design

Date: 2026-06-20

## Goal

Remove task adapter imports of legacy `channel_service` and `content_service`
facades.

## Design

`app.domains.task_operations.adapters` should import:

- `channel_service` from `app.domains.account_operations.channel_service`.
- `content_service` from `app.domains.content_collection.content_service`.

Keep `app.services.task_service` in the adapter because task service ownership
has not moved yet. Keep `app.services.channel_service` and
`app.services.content_service` as compatibility facades for tests and service
modules whose owning domains have not moved.

## Verification

Add one boundary test proving task adapters use direct domain imports for
channel/content while leaving task service on the legacy path. Existing channel
and content facade tests should keep old compatibility for remaining legacy
consumers.

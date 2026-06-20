# DM Sequence Visibility Domain Import Design

Date: 2026-06-20

## Goal

Remove the device polling import of the legacy
`app.services.dm_sequence_visibility` facade.

## Design

`app.domains.device_operations.polling` should import
`get_device_visible_dm_sequences` directly from
`app.domains.content_collection.dm_sequence_visibility`.

Keep `app.services.dm_sequence_visibility` as a compatibility facade for
tests and service modules whose owning domains have not moved.

## Verification

Add one boundary test that proves device polling uses the direct domain import
and the legacy facade still resolves to the same module object as the content
collection implementation.

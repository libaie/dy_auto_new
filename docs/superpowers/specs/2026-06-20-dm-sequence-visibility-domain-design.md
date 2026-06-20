# DM Sequence Visibility Domain Design

Date: 2026-06-20

## Goal

Move the DM sequence visibility rules used by device sync and polling out of
the flat `app.services` folder and into
`app.domains.content_collection.dm_sequence_visibility` without changing DM
sequence API behavior, device polling payloads, task-resume behavior, or legacy
imports.

This keeps DM sequence visibility with the content collection domain that owns
`/api/dm-sequences/*` route assembly and DM sequence mutation orchestration.

## Approved Approach

Move `server/app/services/dm_sequence_visibility.py` to
`server/app/domains/content_collection/dm_sequence_visibility.py`.

Keep `app.services.dm_sequence_visibility` as a temporary `sys.modules`
compatibility facade. Content collection modules import the domain module
directly. Device operations can keep importing the legacy path until the device
bridge handoff has its own cleanup slice.

## Boundaries

- Preserve `get_device_visible_dm_sequences`, `_extract_sequence_id`, and
  `_task_sequence_ids_for_device`.
- Preserve shared sequence visibility for unauthenticated device-sync calls.
- Preserve device-user scoped visibility when a device has a `user_id`.
- Preserve inclusion of DM sequences referenced by pending or running tasks.
- Preserve `extra_sequence_ids` behavior used by device polling for a task that
  is about to be dispatched.
- Preserve `/api/dm-sequences/device/sync` response shape and
  `/api/device/poll` `dm_sequences` payload shape.
- Do not move DM sequence CRUD, variant generation, jitter/randomization,
  device polling route ownership, task service behavior, ORM models, or device
  auth in this slice.
- Do not change route paths, auth dependencies, response dictionaries,
  websocket payloads, logging, or task status semantics.

## Target Structure

```text
server/app/domains/content_collection/
  __init__.py
  README.md
  dm_sequence_visibility.py
  mutations.py

server/app/services/
  dm_sequence_visibility.py  # compatibility facade
```

## Compatibility Strategy

Legacy service imports stay valid through a module alias:

```python
import sys

from app.domains.content_collection import dm_sequence_visibility as _domain_module

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

The legacy and domain imports must resolve to the same module object so tests
and monkeypatches touch the same functions. `mutations.py` moves to the domain
import because it already lives inside `content_collection`. Device polling
keeps the legacy import path as an explicit compatibility bridge.

## Documentation Updates

Update the content collection README to register:

- `app.services.dm_sequence_visibility` ->
  `app.domains.content_collection.dm_sequence_visibility`;
- the current owner of DM sequence visibility rules;
- the cleanup gate for the legacy service facade;
- the fact that device polling may continue through the legacy facade until
  device bridge cleanup.

## Verification

- Add a boundary test proving this spec and plan mention
  `app.domains.content_collection.dm_sequence_visibility`,
  `app.services.dm_sequence_visibility`, and
  `get_device_visible_dm_sequences`.
- Prove the domain service file exists.
- Prove the legacy file is a thin facade with no local visibility-rule
  implementation.
- Prove legacy and domain imports resolve to the same module object and expose
  the same public and helper functions.
- Prove `from app.services import dm_sequence_visibility` resolves to the
  domain module.
- Prove `content_collection.mutations` imports the domain visibility service
  directly.
- Prove `device_operations.polling` stays device-owned and legacy-compatible.
- Run DM sequence API, content collection boundary, and device polling tests
  after migration.

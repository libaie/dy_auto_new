# Image Creation Service Domain Design

## Context

`server/app/services/image_creation_service.py` owns image creation task
idempotency, provider payload preparation, Pixelle submit/sync, asset payloads,
review decisions, cost writes, selection preview validation, and
source/reference image resolution. This is image generation domain behavior.

## Decision

Move the implementation to
`app.domains.image_generation.image_creation_service`. Keep
`app.services.image_creation_service` as a compatibility facade while image
routers, A/B services, storyboard images, reference assets, review asset edits,
and legacy tests still import or monkeypatch the old path.

The new domain module should import image helpers from
`app.domains.image_generation`, runtime model config from
`app.domains.model_configuration`, and Pixelle submit/sync helpers from
`app.domains.pixelle_integration`.

## Scope

- Preserve `create_image_task`, `sync_image_task`, `review_image_asset`,
  `asset_payload`, `task_payload`, request hashing, preview validation, and
  source/reference resolution behavior.
- Preserve the current staged image task behavior and timeout/cost/review
  semantics.
- Remove `image_creation_service.py` from the service implementation inventory.
- Register the domain module and legacy facade in the image generation README.

## Non-Goals

- Do not migrate every caller from `app.services.image_creation_service` in this
  slice.
- Do not rewrite image task idempotency, provider payloads, storage, review
  gate, A/B, cost, or selection preview behavior.
- Do not remove the legacy service import path until downstream callers move.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/tests/test_image_creation_api.py server/tests/test_image_creation_strategy_snapshot.py server/tests/test_image_asset_bridge.py server/tests/test_image_ab_service.py -q
```

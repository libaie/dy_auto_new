# Creative Library Domain Design

Date: 2026-06-20

## Goal

Move the creative asset library route boundary out of the flat `app.routers`
folder and into `app.domains.creative_library` without changing public API
behavior.

This domain groups the routes that manage reusable story assets before they are
attached to series or production jobs: characters, scenes, and reference data
used by their dropdowns and metadata.

## Scope

The new domain owns:

- `/api/characters/*` route assembly;
- `/api/scenes/*` route assembly;
- `/api/reference-categories/*` route assembly;
- `/api/reference-data/*` route assembly;
- request schemas currently local to `app.routers.characters`,
  `app.routers.scenes`, and `app.routers.reference_data`;
- route-local helpers for LLM JSON parsing, reference-asset HTTP error mapping,
  AI rewrite HTTP error mapping, and reference-data seeding.

The migration keeps these modules as compatibility facades:

- `app.routers.characters`;
- `app.routers.scenes`;
- `app.routers.reference_data`.

## Non-Goals

- Do not split `asset_ai_rewrite_service`, `asset_lifecycle_service`,
  `reference_asset_service`, or `ai_generator` in this slice.
- Do not move ORM model class bodies for `Character`, `Scene`,
  `ReferenceData`, or `ReferenceCategory`.
- Do not change public route paths, method names, auth dependencies, response
  payloads, seed behavior, or startup behavior.
- Do not move series character/scene linking; that remains in
  `ai_video_series`.

## Target Structure

```text
server/app/domains/creative_library/
  __init__.py
  README.md
  characters_router.py
  scenes_router.py
  reference_data_router.py
```

The first pass is a route-boundary migration. Later service splits can move
asset rewrite, reference image generation, and lifecycle rules behind this domain
once route ownership is stable.

## Compatibility Strategy

Legacy imports stay valid through module aliases:

```python
from app.domains.creative_library import characters_router as _characters_router
sys.modules[__name__] = _characters_router
globals().update(_characters_router.__dict__)
```

`app.main` can be switched to the domain routers in a separate isolated-index
commit because the working tree currently has unrelated `main.py` changes.

## Tests

The migration adds:

- route/auth snapshot tests for creative library routes;
- boundary tests for metadata, README, facade thickness, and route
  registration;
- facade identity tests proving old and new imports resolve to the same module
  objects while compatibility is active.

# Creative Library Domain

This domain owns reusable creative asset routes for characters, scenes, and
reference dictionaries, plus character and scene reference asset generation.

## Owned Routes

- `/api/characters/*`
- `/api/scenes/*`
- `/api/reference-categories/*`
- `/api/reference-data/*`

## Current Modules

- `characters_router.py` owns character CRUD, character auto-generation,
  character reference image generation, and character AI rewrite endpoints.
- `scenes_router.py` owns scene CRUD, scene auto-generation, scene reference
  image generation, and scene AI rewrite endpoints.
- `reference_data_router.py` owns reference category/item CRUD and default seed
  data.
- `app.db.models.creative_library` owns the `ReferenceData` and
  `ReferenceCategory` ORM class bodies.
- `reference_asset_service.py` owns `ReferenceAssetError`,
  `generate_character_reference_images`, `generate_scene_reference_images`,
  `generate_reference_url`, reference URL usability checks, provider task reuse,
  and character/scene reference row updates.
- `anchor_service.py` owns `AssetAnchorManager`, character/scene anchor prompt
  construction, provider reference payload adaptation, and latest locked anchor
  lookup.
- `asset_lifecycle_service.py` owns `AssetLifecycleError`, series
  delete/archive decisions, character/scene unlinking, and character/scene
  archive-or-delete behavior.
- `asset_ai_rewrite_service.py` owns `AssetAiRewriteError`, character/scene
  candidate-only rewrites, allowed field filtering, and AI output parsing.
- `visual_style_inference_service.py` owns `infer_visual_style_from_story`,
  story-text style inference, visual style merging, prompt constraint
  appending, and stored prompt style matching.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.characters` | `app.domains.creative_library.characters_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |
| `app.routers.scenes` | `app.domains.creative_library.scenes_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |
| `app.routers.reference_data` | `app.domains.creative_library.reference_data_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |
| `app.services.reference_asset_service` | `app.domains.creative_library.reference_asset_service` | Domain modules import the domain service path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.services.anchor_service` | `app.domains.creative_library.anchor_service` | Domain modules import the domain service path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.services.asset_lifecycle_service` | `app.domains.creative_library.asset_lifecycle_service` | Domain modules import the domain service path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.services.asset_ai_rewrite_service` | `app.domains.creative_library.asset_ai_rewrite_service` | Domain modules import the domain service path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.services.visual_style_inference_service` | `app.domains.creative_library.visual_style_inference_service` | Domain modules import the domain service path directly, and legacy imports remain only in compatibility tests, migration docs, or service modules whose domains have not moved yet. |
| `app.db_models.ReferenceData` / `ReferenceCategory` | `app.db.models.creative_library` | Keep as compatibility re-exports until production imports use the domain model path. |

## Boundaries

- Keep series character/scene linking in `ai_video_series`.
- Shared AI generation stays in `app.services.ai_generator`.
- Non-domain service modules may keep importing
  `app.services.reference_asset_service` until their owning domains move.
- Non-domain utility or service modules may keep importing
  `app.services.anchor_service` until their owning domains move.
- Non-domain service modules may keep importing
  `app.services.asset_lifecycle_service` until their owning domains move.
- Non-domain service modules may keep importing
  `app.services.asset_ai_rewrite_service` until their owning domains move.
- Non-domain service modules may keep importing
  `app.services.visual_style_inference_service` until their owning domains
  move.
- Keep the character/scene/anchor ORM graph in `app.db_models` until a
  dedicated graph extraction; reference dictionary models live in
  `app.db.models.creative_library`.
- Keep startup reference data seeding behavior unchanged.

## Compatibility Cleanup Gates

Do not remove legacy router facades until all of these are true:

- `app.main` imports creative library routers from
  `app.domains.creative_library`.
- Route/auth snapshots pass against domain endpoint modules.
- Legacy and domain imports resolve to the same module objects during the alias
  phase.
- Existing series, asset archive, asset rewrite, and reference asset tests pass.
- Import inventory shows no unapproved production imports of
  `app.routers.characters`, `app.routers.scenes`, or
  `app.routers.reference_data`.

Do not remove the legacy reference asset service facade until all of these are true:

- `rg "app\.services\.reference_asset_service" server/app server/tests` returns only compatibility tests and migration docs.
- `test_creative_library_reference_asset_service_facade.py` has been replaced with tests for direct domain imports.
- Domain-owned production modules import `app.domains.creative_library.reference_asset_service` directly.

Do not remove the legacy anchor service facade until all of these are true:

- `rg "app\.services\.anchor_service" server/app server/tests` returns only
  compatibility tests and migration docs.
- `test_creative_library_anchor_service_facade.py` has been replaced with
  tests for direct domain imports.
- Domain-owned production modules import
  `app.domains.creative_library.anchor_service` directly.

Do not remove the legacy asset lifecycle service facade until all of these are
true:

- `rg "app\.services\.asset_lifecycle_service" server/app server/tests` returns
  only compatibility tests and migration docs.
- `test_creative_library_asset_lifecycle_service_facade.py` has been replaced
  with tests for direct domain imports.
- Domain-owned production modules import
  `app.domains.creative_library.asset_lifecycle_service` directly.

Do not remove the legacy asset AI rewrite service facade until all of these are
true:

- `rg "app\.services\.asset_ai_rewrite_service" server/app server/tests`
  returns only compatibility tests and migration docs.
- `test_creative_library_asset_ai_rewrite_service_facade.py` has been replaced
  with tests for direct domain imports.
- Domain-owned production modules import
  `app.domains.creative_library.asset_ai_rewrite_service` directly.

Do not remove the legacy visual style inference service facade until all of
these are true:

- `rg "app\.services\.visual_style_inference_service" server/app server/tests`
  returns only compatibility tests and migration docs.
- `test_creative_library_visual_style_service_facade.py` has been replaced
  with tests for direct domain imports.
- Domain-owned production modules import
  `app.domains.creative_library.visual_style_inference_service` directly.

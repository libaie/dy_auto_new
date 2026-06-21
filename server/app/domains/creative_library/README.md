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
- `app.db.models.creative_library` owns the `Character`, `Scene`,
  `ReferenceData`, `ReferenceCategory`, `CharacterAnchor`, and `SceneAnchor`
  ORM class bodies.
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

## Canonical Imports

The retired router, service, and ORM import packages have been removed. Runtime code, tests, scripts, and new docs must import domain modules directly and use `app.db.models` / `app.db.models.<domain>` for ORM models.

## Boundaries

- Keep series character/scene linking in `ai_video_series`.
- Keep startup reference data seeding behavior unchanged.

## Legacy Import Guard

The cleanup gate is complete. Keep the retired import-path and AST inventory tests passing so removed paths stay unavailable.

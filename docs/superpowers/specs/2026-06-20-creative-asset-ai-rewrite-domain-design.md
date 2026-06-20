# Creative Asset AI Rewrite Domain Design

Date: 2026-06-20

## Goal

Move creative asset AI rewrite candidates into the `creative_library` domain.
The service owns candidate-only rewrites for characters and scenes, including
allowed field filtering and invalid AI output errors.

## Design

`app.domains.creative_library.asset_ai_rewrite_service` becomes the
implementation owner for `AssetAiRewriteError`,
`generate_character_rewrite_candidate`, `generate_scene_rewrite_candidate`,
allowed field lists, AI prompt construction, JSON extraction, and candidate
filtering.

`app.services.asset_ai_rewrite_service` remains a `sys.modules` compatibility
facade so legacy imports and monkeypatches resolve to the same module object.

Creative library routers import the domain path directly:

- `app.domains.creative_library.characters_router`
- `app.domains.creative_library.scenes_router`

## Boundaries

- Keep shared AI model generation in `app.services.ai_generator`.
- Keep ORM models in `app.db_models`.
- Preserve public function names, error codes, allowed fields, JSON parsing,
  no-mutation behavior, and router response shapes.

## Verification

- Add a boundary test for domain ownership, legacy facade identity, direct
  creative router imports, README registration, and legacy monkeypatch
  visibility.
- Run existing asset AI rewrite tests.
- Run app import smoke to catch startup import regressions.

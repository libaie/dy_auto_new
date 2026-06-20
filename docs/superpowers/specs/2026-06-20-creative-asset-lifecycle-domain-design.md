# Creative Asset Lifecycle Domain Design

Date: 2026-06-20

## Goal

Move creative asset lifecycle behavior into the `creative_library` domain. The
service owns series delete/archive decisions, character/scene unlinking, and
character/scene archive-or-delete behavior.

## Design

`app.domains.creative_library.asset_lifecycle_service` becomes the
implementation owner for `AssetLifecycleError`, `delete_or_archive_series`,
`unlink_character_from_series`, `unlink_scene_from_series`, and
`archive_character_or_scene`.

`app.services.asset_lifecycle_service` remains a `sys.modules` compatibility
facade so legacy imports keep resolving to the same module object. Existing
AI video series code may keep the legacy import until that domain is migrated.

Creative library routers import the domain path directly:

- `app.domains.creative_library.characters_router`
- `app.domains.creative_library.scenes_router`

## Boundaries

- Keep ORM models in `app.db_models`.
- Keep series ownership in `ai_video_series`.
- Keep production dependency checks unchanged.
- Preserve public function names, error codes, details payloads, commit
  behavior, and archive timestamp behavior.

## Verification

- Add a boundary test for domain ownership, legacy facade identity, direct
  creative router imports, README registration, and legacy-path API
  compatibility.
- Run existing asset lifecycle tests.
- Run app import smoke to catch startup import regressions.

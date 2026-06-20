# Creative Asset ORM Boundary Design

> Auto-approved spec: proceed without approval pause.

## Scope

Move the `Character` and `Scene` ORM class bodies from `app.db_models` into
`app.db.models.creative_library`.

## Design

- `app.db.models.creative_library` owns `Character`, `Scene`,
  `CharacterAnchor`, `SceneAnchor`, `ReferenceData`, and `ReferenceCategory`.
- `app.db_models.Character` and `app.db_models.Scene` remain compatibility
  re-exports.
- Creative library domain modules import `Character` and `Scene` from the
  domain ORM module.
- Series linking tables and `Character.series_list` / `Scene.series_list`
  wiring stay in `app.db_models` for this slice.

## Out Of Scope

- Do not move `Series`, `Episode`, `series_characters`, or `series_scenes`.
- Do not change route behavior, AI generation behavior, or database schema.

## Verification

- Extend the creative library ORM boundary test to cover `Character` and
  `Scene`.
- Run focused creative library tests for ORM boundaries and character/scene
  routers.

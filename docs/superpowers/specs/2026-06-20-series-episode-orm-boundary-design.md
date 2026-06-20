# Series Episode ORM Boundary Design

> Auto-approved spec: proceed without approval pause.

## Scope

Move `Series`, `Episode`, `series_characters`, and `series_scenes` from
`app.db_models` into `app.db.models.ai_video_series`.

## Design

- `app.db.models.ai_video_series` owns the core series and episode persistence
  definitions.
- `app.db_models` remains the compatibility re-export surface.
- AI video series owner-domain modules import `Series` and `Episode` from the
  domain ORM module.
- Production ORM names that still live in `app.db_models` stay as lazy
  compatibility exports from `app.db.models.ai_video_series`.

## Out Of Scope

- Do not move production plan, production job, video production run, review, or
  image production ORM classes.
- Do not change table names, columns, defaults, relationships, indexes, API
  responses, or production behavior.

## Verification

- Extend the existing AI video series ORM boundary test to prove `Series` and
  `Episode` are owned by `app.db.models.ai_video_series`.
- Run focused AI video series ORM/facade/service tests.
- Confirm AI video series owner-domain code no longer imports `Series` or
  `Episode` from `app.db_models`.

# Video Library Domain

This domain owns admin generated-video library routes.

## Owned Routes

- `/api/videos/*`

## Not Owned

- Pixelle provider and proxy routes stay outside this domain.
- Seedance provider routes stay outside this domain.

## Current Modules

- `videos_router.py` owns generated-video list, detail, download, and delete
  routes.
- `app.db.models.video_library` owns the `GeneratedVideo` ORM class body.

## Canonical Imports

The retired router, service, and ORM import packages have been removed. Runtime code, tests, scripts, and new docs must import domain modules directly and use `app.db.models` / `app.db.models.<domain>` for ORM models.

## Boundaries

- Keep generated-video persistence on `app.db.models.video_library.GeneratedVideo`.
- Keep video production, Pixelle, and Seedance execution flows outside this
  domain.
- Preserve route paths, route names, auth dependencies, response shapes,
  download token fallback behavior, and delete behavior.
- Do not add a service layer in this route-boundary migration.

## Legacy Import Guard

The cleanup gate is complete. Keep the retired import-path and AST inventory tests passing so removed paths stay unavailable.

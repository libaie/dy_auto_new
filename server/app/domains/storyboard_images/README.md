# Storyboard Images Domain

This domain owns storyboard frame image task and promoted image asset routes.

## Owned Routes

- `/api/storyboard-images/episodes/{episode_id}/frames/{frame_id}/tasks`
- `/api/storyboard-images/episodes/{episode_id}/tasks:batch`
- `/api/storyboard-images/episodes/{episode_id}`
- `/api/storyboard-images/assets/{asset_id}/promote`

## Not Owned

- Database session helpers stay in `app.database`.
- Auth dependencies stay in `app.deps`.
- Storyboard image task creation, state listing, and asset promotion logic live
  in `app.domains.storyboard_images.storyboard_image_service`.

## Current Modules

- `storyboard_images_router.py` owns `StoryboardImageTaskRequest`,
  `PromoteStoryboardImageRequest`, `_auth_user_id`, and all
  `/api/storyboard-images/*` route handlers.
- `storyboard_image_service.py` owns storyboard frame image task creation,
  state listing, and promotion to video assets.

## Canonical Imports

The retired router, service, and ORM import packages have been removed. Runtime code, tests, scripts, and new docs must import domain modules directly and use `app.db.models` / `app.db.models.<domain>` for ORM models.

## Boundaries

- Preserve route paths, route names, auth dependencies, and response shapes.
- Preserve admin-role protection on every route.
- Preserve request validation for count and asset version values.
- Preserve the service layer as the owner of storyboard image business logic.

## Legacy Import Guard

The cleanup gate is complete. Keep the retired import-path and AST inventory tests passing so removed paths stay unavailable.

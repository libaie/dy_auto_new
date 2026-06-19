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
- Storyboard image task creation, state listing, and asset promotion logic stay
  in `app.services.storyboard_image_service`.

## Current Modules

- `storyboard_images_router.py` owns `StoryboardImageTaskRequest`,
  `PromoteStoryboardImageRequest`, `_auth_user_id`, and all
  `/api/storyboard-images/*` route handlers.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.storyboard_images` | `app.domains.storyboard_images.storyboard_images_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |

## Boundaries

- Preserve route paths, route names, auth dependencies, and response shapes.
- Preserve admin-role protection on every route.
- Preserve request validation for count and asset version values.
- Preserve the service layer as the owner of storyboard image business logic.
- Preserve compatibility for legacy imports during the alias phase.

## Compatibility Cleanup Gates

Do not remove the legacy router facade until all of these are true:

- `app.main` imports `storyboard_images_router` from
  `app.domains.storyboard_images`.
- Route/auth snapshots pass against the domain endpoint module.
- Legacy and domain imports resolve to the same module object during the alias
  phase.
- Existing storyboard image API, service, and video bridge tests pass.
- Import inventory shows no unapproved production imports of
  `app.routers.storyboard_images`.

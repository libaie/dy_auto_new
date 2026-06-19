# Storyboard Images Domain Design

Status: auto-approved.

## Goal

Move the `/api/storyboard-images/*` HTTP surface into
`app.domains.storyboard_images` while preserving storyboard frame image task
creation, batch creation, state listing, and asset promotion behavior.

## Domain Boundary

The new domain owns:

- `app.domains.storyboard_images.storyboard_images_router`
- `storyboard_images_router.py`
- `/api/storyboard-images/episodes/{episode_id}/frames/{frame_id}/tasks`
- `/api/storyboard-images/episodes/{episode_id}/tasks:batch`
- `/api/storyboard-images/episodes/{episode_id}`
- `/api/storyboard-images/assets/{asset_id}/promote`

The domain continues to call shared service functions:

- `create_storyboard_frame_image_task`
- `create_missing_storyboard_image_tasks`
- `list_storyboard_image_state`
- `promote_storyboard_image_asset`

## Compatibility

Keep `app.routers.storyboard_images` as a thin facade that aliases to
`app.domains.storyboard_images.storyboard_images_router` through `sys.modules`.
Existing imports and monkeypatches must resolve to the same module object while
the facade exists.

## Security And Behavior

- Preserve `require_role("admin")` on every route.
- Preserve `StoryboardImageTaskRequest`, `PromoteStoryboardImageRequest`, and
  `_auth_user_id`.
- Preserve async task creation behavior and synchronous state/promote behavior.
- Preserve request validation for `count` and `asset_version`.

## Exit Criteria

- `app.main` imports `storyboard_images_router` from
  `app.domains.storyboard_images`.
- `app.main` includes `storyboard_images_router.router`, not
  `storyboard_images.router`.
- Route/auth snapshots show endpoint modules under
  `app.domains.storyboard_images.storyboard_images_router`.
- `app.routers.storyboard_images` remains a <=20 line facade with no
  `APIRouter`.
- Focused storyboard image API, service, and video bridge tests pass.

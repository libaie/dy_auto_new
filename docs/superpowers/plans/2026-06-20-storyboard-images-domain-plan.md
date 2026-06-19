# Storyboard Images Domain Plan

Status: auto-approved.

## Success Criteria

Storyboard image routes are available from
`app.domains.storyboard_images.storyboard_images_router` with unchanged paths,
auth dependencies, request models, and response shapes.

## Steps

1. Add boundary tests.
   Verify: spec/plan mention `app.domains.storyboard_images`,
   `storyboard_images_router.py`, `app.routers.storyboard_images`,
   `/api/storyboard-images`, `StoryboardImageTaskRequest`,
   `PromoteStoryboardImageRequest`, `_auth_user_id`,
   `create_storyboard_frame_image_task`, and `promote_storyboard_image_asset`.

2. Add legacy facade tests.
   Verify: importing `app.routers.storyboard_images` and
   `app.domains.storyboard_images.storyboard_images_router` returns the same
   module object and exposes the same four route handlers.

3. Add route/auth parity tests.
   Verify: all routes still use `require_role("admin")` and endpoint modules
   move to `app.domains.storyboard_images.storyboard_images_router`.

4. Move router implementation.
   Verify: create `app.domains.storyboard_images`, copy the current router into
   `storyboard_images_router.py`, and replace the legacy router with a
   `sys.modules` facade.

5. Wire app startup directly to the domain.
   Verify: `app.main` imports and includes `storyboard_images_router.router`.

6. Run focused regression.
   Verify: new domain tests plus existing storyboard image API, service, and
   video bridge tests pass before committing.

# Video Library Domain Design

Date: 2026-06-20

## Goal

Move generated-video library route ownership out of the flat `app.routers`
folder and into `app.domains.video_library` without changing public API
behavior.

This domain owns the admin-facing library for generated videos: listing stored
video records, reading one video record, downloading the saved MP4, and deleting
the database row plus local file.

## Scope

The new domain owns:

- `GET /api/videos`;
- `GET /api/videos/{video_id}`;
- `GET /api/videos/{video_id}/download`;
- `DELETE /api/videos/{video_id}`;
- route-local response models for generated video library responses;
- route assembly and auth dependencies for those endpoints.

The migration keeps `app.routers.videos` as a compatibility facade.

## Non-Goals

- Do not move or refactor `app.routers.video_production`.
- Do not move or refactor Pixelle, Seedance, or provider execution routes.
- Do not change `GeneratedVideo` ORM fields, file storage paths, download token
  fallback behavior, delete behavior, route paths, route names, auth
  dependencies, or response shapes.
- Do not introduce a new service layer in this slice.

## Target Structure

```text
server/app/domains/video_library/
  __init__.py
  README.md
  videos_router.py
```

This is a route-boundary migration. Later work can split file-delete safety and
library query helpers after the domain import boundary is stable.

## Compatibility Strategy

Legacy imports stay valid through a module alias:

```python
from app.domains.video_library import videos_router as _videos_router
sys.modules[__name__] = _videos_router
globals().update(_videos_router.__dict__)
```

This keeps old imports of `app.routers.videos` resolving to the same module
object as `app.domains.video_library.videos_router` during the compatibility
phase.

## Tests

The migration adds:

- route/auth snapshot tests for `/api/videos/*`;
- API behavior tests for list, detail, download auth, and delete behavior;
- boundary tests for metadata, README, facade thickness, route registration,
  main wiring, and non-ownership of video production/provider routes;
- facade identity tests proving old and new imports resolve to the same module
  object while compatibility is active.

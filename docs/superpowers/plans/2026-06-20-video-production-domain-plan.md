# Video Production Domain Plan

Status: auto-approved.

## Success Criteria

The video production control plane is available from
`app.domains.video_production.video_production_router` with unchanged paths,
auth dependencies, request models, helpers, response shapes, and legacy
monkeypatch compatibility.

## Steps

1. Add boundary tests.
   Verify: spec/plan mention `app.domains.video_production`,
   `video_production_router.py`, `app.routers.video_production`,
   `/api/video-production`, `StartRunRequest`, `OneSentenceVideoRequest`,
   `_run_payload`, `_asset_payload`, `_provider_stage_task_payload`,
   `create_one_sentence_video`, and `start_image_stage`.

2. Add legacy facade tests.
   Verify: importing `app.routers.video_production` and
   `app.domains.video_production.video_production_router` returns the same
   module object and exposes the same route table.

3. Add route/auth parity tests.
   Verify: all `/api/video-production/*` routes still use
   `require_role("admin")` and endpoint modules move to
   `app.domains.video_production.video_production_router`.

4. Move router implementation.
   Verify: create `app.domains.video_production`, copy the current router into
   `video_production_router.py`, and replace the legacy router with a
   `sys.modules` facade.

5. Wire app startup directly to the domain.
   Verify: `app.main` imports and includes `video_production_router.router`.

6. Run focused regression.
   Verify: new domain tests plus focused video production API/start-flow/worker
   tests pass before committing.

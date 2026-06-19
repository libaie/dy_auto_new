# AI Text Artifacts Domain Plan

Status: auto-approved.

## Success Criteria

AI text artifact routes are available from
`app.domains.ai_text_artifacts.ai_text_artifacts_router` with unchanged paths,
auth dependencies, request models, and response shapes.

## Steps

1. Add boundary tests.
   Verify: spec/plan mention `app.domains.ai_text_artifacts`,
   `ai_text_artifacts_router.py`, `app.routers.ai_text_artifacts`,
   `/api/ai-text-artifacts`, `ArtifactEditRequest`,
   `ArtifactRegenerateRequest`, `_actor_id`, `_artifact_dict`, and
   `AITextArtifactService`.

2. Add legacy facade tests.
   Verify: importing `app.routers.ai_text_artifacts` and
   `app.domains.ai_text_artifacts.ai_text_artifacts_router` returns the same
   module object and the router exposes the same six route handlers.

3. Add route/auth parity tests.
   Verify: read routes still use `verify_admin_token`; edit, approve, and
   regenerate routes still use `require_role("admin")`.

4. Move router implementation.
   Verify: create `app.domains.ai_text_artifacts`, copy the current router into
   `ai_text_artifacts_router.py`, and replace the legacy router with a
   `sys.modules` facade.

5. Wire app startup directly to the domain.
   Verify: `app.main` imports and includes `ai_text_artifacts_router.router`.

6. Run focused regression.
   Verify: new domain tests plus existing AI text artifact API and service tests
   pass before committing.

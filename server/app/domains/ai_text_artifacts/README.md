# AI Text Artifacts Domain

This domain owns AI text artifact review, edit, approval, lineage, and
regeneration routes.

## Owned Routes

- `/api/ai-text-artifacts`
- `/api/ai-text-artifacts/{artifact_id}`
- `/api/ai-text-artifacts/{artifact_id}/lineage`
- `/api/ai-text-artifacts/{artifact_id}/edit`
- `/api/ai-text-artifacts/{artifact_id}/approve`
- `/api/ai-text-artifacts/{artifact_id}/regenerate`

## Not Owned

- `AITextArtifact` ORM definitions stay in `app.db_models`.
- Database session helpers stay in `app.database`.
- Auth dependencies stay in `app.deps`.
- Versioning, lineage, approval, and AI regeneration business logic stay in
  `app.services.ai_text_artifact_service`.

## Current Modules

- `ai_text_artifacts_router.py` owns `ArtifactEditRequest`,
  `ArtifactRegenerateRequest`, `_actor_id`, `_artifact_dict`, missing artifact
  HTTP mapping, stale approval mapping, and all `/api/ai-text-artifacts/*`
  route handlers.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.ai_text_artifacts` | `app.domains.ai_text_artifacts.ai_text_artifacts_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |

## Boundaries

- Preserve route paths, route names, auth dependencies, and response shapes.
- Preserve read-route `verify_admin_token` auth.
- Preserve edit, approve, and regenerate `require_role("admin")` auth.
- Preserve actor extraction through `_actor_id`.
- Preserve response serialization through `_artifact_dict`.
- Preserve compatibility for legacy imports during the alias phase.

## Compatibility Cleanup Gates

Do not remove the legacy router facade until all of these are true:

- `app.main` imports `ai_text_artifacts_router` from
  `app.domains.ai_text_artifacts`.
- Route/auth snapshots pass against the domain endpoint module.
- Legacy and domain imports resolve to the same module object during the alias
  phase.
- Existing AI text artifact API and service tests pass.
- Import inventory shows no unapproved production imports of
  `app.routers.ai_text_artifacts`.

# AI Text Artifacts Domain

This domain owns AI text artifact review, edit, approval, lineage,
regeneration routes, and the `AITextArtifactService` business logic.

## Owned Routes

- `/api/ai-text-artifacts`
- `/api/ai-text-artifacts/{artifact_id}`
- `/api/ai-text-artifacts/{artifact_id}/lineage`
- `/api/ai-text-artifacts/{artifact_id}/edit`
- `/api/ai-text-artifacts/{artifact_id}/approve`
- `/api/ai-text-artifacts/{artifact_id}/regenerate`

## Not Owned

- Database session helpers stay in `app.database`.
- Auth dependencies stay in `app.deps`.

## Current Modules

- `ai_text_artifacts_router.py` owns `ArtifactEditRequest`,
  `ArtifactRegenerateRequest`, `_actor_id`, `_artifact_dict`, missing artifact
  HTTP mapping, stale approval mapping, and all `/api/ai-text-artifacts/*`
  route handlers.
- `ai_text_artifact_service.py` owns `AITextArtifactService`, artifact
  versioning, approval, lineage, regeneration, consumer binding, and legacy run
  backfill.
- `app.db.models.ai_text_artifacts` owns the `AITextArtifact` and
  `AITextArtifactConsumer` ORM class bodies.

## Canonical Imports

The retired router, service, and ORM import packages have been removed. Runtime code, tests, scripts, and new docs must import domain modules directly and use `app.db.models` / `app.db.models.<domain>` for ORM models.

## Boundaries

- Preserve route paths, route names, auth dependencies, and response shapes.
- Preserve read-route `verify_admin_token` auth.
- Preserve edit, approve, and regenerate `require_role("admin")` auth.
- Preserve actor extraction through `_actor_id`.
- Preserve response serialization through `_artifact_dict`.

## Legacy Import Guard

The cleanup gate is complete. Keep the retired import-path and AST inventory tests passing so removed paths stay unavailable.

# AI Text Artifacts Domain Design

Status: auto-approved.

## Goal

Move the `/api/ai-text-artifacts/*` HTTP surface into
`app.domains.ai_text_artifacts` while preserving the AI text artifact review,
edit, approval, lineage, and regeneration behavior.

## Domain Boundary

The new domain owns:

- `app.domains.ai_text_artifacts.ai_text_artifacts_router`
- `ai_text_artifacts_router.py`
- `/api/ai-text-artifacts`
- `/api/ai-text-artifacts/{artifact_id}`
- `/api/ai-text-artifacts/{artifact_id}/lineage`
- `/api/ai-text-artifacts/{artifact_id}/edit`
- `/api/ai-text-artifacts/{artifact_id}/approve`
- `/api/ai-text-artifacts/{artifact_id}/regenerate`

The domain continues to use shared storage and services:

- `AITextArtifact`
- `AITextArtifactService`
- `get_db`
- `verify_admin_token`
- `require_role("admin")`

## Compatibility

Keep `app.routers.ai_text_artifacts` as a thin facade that aliases to
`app.domains.ai_text_artifacts.ai_text_artifacts_router` through `sys.modules`.
Existing imports and monkeypatches must resolve to the same module object while
the legacy facade exists.

## Security And Behavior

- Preserve read-route auth with `verify_admin_token`.
- Preserve write-route auth with `require_role("admin")`.
- Preserve `ArtifactEditRequest`, `ArtifactRegenerateRequest`, `_actor_id`, and
  `_artifact_dict` behavior.
- Preserve 404 handling for missing artifacts.
- Preserve 409 handling for stale approvals and AI regeneration runtime errors.

## Exit Criteria

- `app.main` imports `ai_text_artifacts_router` from
  `app.domains.ai_text_artifacts`.
- `app.main` includes `ai_text_artifacts_router.router`, not
  `ai_text_artifacts.router`.
- Route/auth snapshots show endpoint modules under
  `app.domains.ai_text_artifacts.ai_text_artifacts_router`.
- `app.routers.ai_text_artifacts` remains a <=20 line facade with no
  `APIRouter`.
- Focused AI text artifact API and service tests pass.

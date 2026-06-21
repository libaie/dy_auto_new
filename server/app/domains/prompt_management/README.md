# Prompt Management Domain

This domain owns admin prompt template management routes.

## Owned Routes

- `/api/prompt-templates/*`

## Not Owned

- `/api/device/prompt-templates` stays in `device_operations`.

## Current Modules

- `prompt_templates_router.py` owns prompt template AI generation, streaming
  generation, rewrite preview, CRUD, toggle, revision versioning, and realtime
  notification endpoints.
- `prompt_template_service.py` owns `PromptTemplateService`,
  `prompt_template_service`, CRUD, revision tracking, device payloads, rewrite
  request validation, rewrite output validation, serialized-size checks, and
  rewrite prompt construction.
- `app.db.models.prompt_management` owns the `PromptTemplate` ORM class body.

## Canonical Imports

The retired router, service, and ORM import packages have been removed. Runtime code, tests, scripts, and new docs must import domain modules directly and use `app.db.models` / `app.db.models.<domain>` for ORM models.

## Boundaries

- Keep prompt template CRUD, revision tracking, and rewrite validation helpers in
  `app.domains.prompt_management.prompt_template_service`.
- Keep device prompt-template polling in `device_operations`.
- Preserve websocket payloads `prompt_templates_updated` and
  `prompt_templates_changed`.

## Legacy Import Guard

The cleanup gate is complete. Keep the retired import-path and AST inventory tests passing so removed paths stay unavailable.

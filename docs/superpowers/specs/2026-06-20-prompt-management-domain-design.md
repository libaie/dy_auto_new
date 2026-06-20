# Prompt Management Domain Design

Date: 2026-06-20

## Goal

Move prompt template management route ownership out of the flat `app.routers`
folder and into `app.domains.prompt_management` without changing public API
behavior.

This domain owns the admin prompt-template workflow: AI template generation,
streaming generation, rewrite preview, CRUD, enable/disable, revision versioning,
and realtime update notifications.

## Scope

The new domain owns:

- `/api/prompt-templates/*` route assembly;
- prompt template request schemas currently local to
  `app.routers.prompt_templates`;
- route-local helpers for SSE payloads, JSON fence stripping, canonical template
  comparison, and prompt rewrite streaming;
- websocket notification payloads for prompt template update events.

The migration keeps `app.routers.prompt_templates` as a compatibility facade.

## Non-Goals

- Do not move device-facing `/api/device/prompt-templates`; that stays in
  `device_operations`.
- Prompt template CRUD, revision tracking, device payloads, rewrite validation,
  rewrite output validation, and rewrite prompt construction now live in
  `app.domains.prompt_management.prompt_template_service`;
  `app.services.prompt_template_service` remains as a temporary compatibility
  facade.
- Do not move prompt template ORM model bodies.
- Do not change route paths, auth dependencies, SSE event shapes, websocket
  payloads, logger behavior, or existing monkeypatch import paths.

## Target Structure

```text
server/app/domains/prompt_management/
  __init__.py
  README.md
  prompt_template_service.py
  prompt_templates_router.py
```

This began as a route-boundary migration. Prompt template CRUD, revision, and
rewrite validation helpers now live in the prompt management domain through
`PromptTemplateService`. Later work can still split rewrite streaming and
realtime event helpers once the domain import boundary is stable.

## Compatibility Strategy

Legacy imports remain valid through a module alias:

```python
from app.domains.prompt_management import prompt_templates_router as _prompt_templates_router
sys.modules[__name__] = _prompt_templates_router
globals().update(_prompt_templates_router.__dict__)
```

The domain router keeps the historical logger name
`app.routers.prompt_templates` because existing security tests assert sensitive
prompt content is not logged through that logger.

The prompt template service follows the same compatibility rule:

- `app.services.prompt_template_service` ->
  `app.domains.prompt_management.prompt_template_service`.
- Keep the facade until the prompt management README cleanup gate passes,
  including `rg "app\.services\.prompt_template_service" server/app server/tests`
  showing only compatibility tests, migration docs, or callers from domains
  that have not moved yet.
- Keep legacy router monkeypatch paths such as
  `app.routers.prompt_templates.prompt_template_service.validate_rewrite_request`
  working during the facade phase.

## Tests

The migration adds:

- route/auth snapshot tests for `/api/prompt-templates/*`;
- boundary tests for metadata, README, facade thickness, and route registration;
- facade identity tests proving old and new imports resolve to the same module
  object while compatibility is active.

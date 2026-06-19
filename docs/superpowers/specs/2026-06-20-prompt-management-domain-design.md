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
- Do not split `prompt_template_service` in this slice.
- Do not move prompt template ORM model bodies.
- Do not change route paths, auth dependencies, SSE event shapes, websocket
  payloads, logger behavior, or existing monkeypatch import paths.

## Target Structure

```text
server/app/domains/prompt_management/
  __init__.py
  README.md
  prompt_templates_router.py
```

The first pass is a route-boundary migration. Later work can split rewrite
streaming and realtime event helpers once the router import boundary is stable.

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

## Tests

The migration adds:

- route/auth snapshot tests for `/api/prompt-templates/*`;
- boundary tests for metadata, README, facade thickness, and route registration;
- facade identity tests proving old and new imports resolve to the same module
  object while compatibility is active.

# Prompt Template Service Domain Design

Date: 2026-06-20

## Goal

Move prompt template CRUD, revision tracking, device-facing template payloads,
rewrite validation, rewrite output validation, and rewrite prompt construction
out of the flat `app.services` folder and into `app.domains.prompt_management`
without changing API behavior, SSE behavior, device polling behavior, or legacy
monkeypatch paths.

This makes prompt management a business-owned domain instead of a route module
that depends on a generic service bucket.

## Approved Approach

Move `server/app/services/prompt_template_service.py` to
`server/app/domains/prompt_management/prompt_template_service.py`.

Keep `app.services.prompt_template_service` as a temporary `sys.modules`
compatibility facade. The prompt management router imports the domain service
directly. Device operations can continue to import the legacy path until their
domain is migrated.

## Boundaries

- Preserve `PromptTemplateService`, `prompt_template_service`,
  `PROMPT_TEMPLATE_REWRITE_MAX_INSTRUCTION_CHARS`,
  `PROMPT_TEMPLATE_REWRITE_MAX_CONTENT_BYTES`, `_get_tmpl_revision`,
  `_set_tmpl_revision`, `_bump_tmpl_revision`, `_to_dict`, and
  `_to_device_dict`.
- Preserve CRUD commit behavior, prompt template revision semantics, device
  payload shape, enabled-only filtering, and admin response dictionaries.
- Preserve no-side-effect rewrite request validation, rewrite output validation,
  serialized content size checks, and rewrite prompt construction.
- Preserve `app.routers.prompt_templates.prompt_template_service.*` patch paths
  through the existing router facade.
- Preserve `/api/device/prompt-templates` ownership in `device_operations`.
- Preserve router logger name `app.routers.prompt_templates`.
- Do not move `ai_generator`, prompt template ORM models, device routes, or SSE
  orchestration in this slice.
- Do not change route paths, auth dependencies, SSE event shapes, websocket
  payloads, logger behavior, or existing monkeypatch import paths.

## Target Structure

```text
server/app/domains/prompt_management/
  __init__.py
  README.md
  prompt_template_service.py
  prompt_templates_router.py

server/app/services/
  prompt_template_service.py  # compatibility facade
```

## Compatibility Strategy

Legacy service imports stay valid through a module alias:

```python
import sys

from app.domains.prompt_management import prompt_template_service as _domain_module

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
```

The legacy and domain imports must resolve to the same module object so tests,
device routes, and monkeypatches touch the same singleton and helper functions.

The existing `app.routers.prompt_templates` router facade remains in place.
Because the domain router keeps a module-level `prompt_template_service`
attribute, existing patch paths such as
`app.routers.prompt_templates.prompt_template_service.validate_rewrite_request`
continue to work during the compatibility phase.

## Documentation Updates

Update the prompt management README and same-day prompt management design and
plan to register:

- `app.services.prompt_template_service` ->
  `app.domains.prompt_management.prompt_template_service`;
- the prompt template service cleanup gate;
- the direct domain import from `prompt_templates_router.py`;
- the invariant that legacy router monkeypatch paths remain compatible.

## Verification

- Add a boundary test proving the new spec and plan mention
  `app.domains.prompt_management.prompt_template_service`,
  `app.services.prompt_template_service`, `PromptTemplateService`,
  `prompt_template_service`, and
  `PROMPT_TEMPLATE_REWRITE_MAX_CONTENT_BYTES`.
- Prove the domain service file exists.
- Prove the legacy file is a thin facade with no local
  `class PromptTemplateService` and no local
  `prompt_template_service = PromptTemplateService()`.
- Prove legacy and domain imports resolve to the same module object and expose
  the same singleton, constants, and helper functions.
- Prove `from app.services import prompt_template_service` resolves to the
  domain module.
- Prove `prompt_templates_router.py` imports the domain prompt template service
  directly.
- Prove the legacy router facade still exposes the same `prompt_template_service`
  object for monkeypatch paths.
- Prove device prompt-template routes still live in `device_operations` and can
  remain on the legacy facade.
- Run prompt template service, prompt rewrite, prompt management route/facade,
  and device prompt-template tests after migration.

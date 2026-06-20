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

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.prompt_templates` | `app.domains.prompt_management.prompt_templates_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |
| `app.services.prompt_template_service` | `app.domains.prompt_management.prompt_template_service` | All prompt template service callers import the domain service directly or belong to domains that have not moved yet. |
| `app.db_models.PromptTemplate` | `app.db.models.prompt_management.PromptTemplate` | Keep as a compatibility re-export until production imports use the domain model path. |

## Boundaries

- Keep prompt template CRUD, revision tracking, and rewrite validation helpers in
  `app.domains.prompt_management.prompt_template_service`.
- Keep device prompt-template polling in `device_operations`.
- Preserve websocket payloads `prompt_templates_updated` and
  `prompt_templates_changed`.
- Preserve logger compatibility for `app.routers.prompt_templates` while tests
  and security checks still patch/capture the legacy path.
- Preserve legacy router patch paths such as
  `app.routers.prompt_templates.prompt_template_service.validate_rewrite_request`
  until callers move to direct domain imports.

## Compatibility Cleanup Gates

Do not remove the legacy router facade until all of these are true:

- `app.main` imports prompt template router from `app.domains.prompt_management`.
- Route/auth snapshots pass against the domain endpoint module.
- Legacy and domain imports resolve to the same module object during the alias
  phase.
- Existing prompt rewrite and device prompt template tests pass.
- Import inventory shows no unapproved production imports of
  `app.routers.prompt_templates`.

Do not remove the legacy prompt template service facade until all of these are true:

- `rg "app\.services\.prompt_template_service" server/app server/tests` returns
  only compatibility tests, migration docs, or modules whose domains have not
  moved yet.
- `test_prompt_template_service_domain_facade.py` has been replaced with tests
  for direct domain imports.
- Domain-owned prompt management modules import
  `app.domains.prompt_management.prompt_template_service` directly.
- Legacy router patch paths such as
  `app.routers.prompt_templates.prompt_template_service.validate_rewrite_request`
  have either been removed or are backed by direct-domain tests.
- Direct domain prompt template service coverage proves `PromptTemplateService`,
  `prompt_template_service`, and `PROMPT_TEMPLATE_REWRITE_MAX_CONTENT_BYTES`
  behavior without legacy imports.

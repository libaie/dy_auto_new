# Prompt Management Domain Implementation Plan

Date: 2026-06-20

## Goal

Create `app.domains.prompt_management` and move admin prompt template route and
service ownership behind compatibility-preserving domain modules.

## PR1: Boundary And Route Snapshot

- Add `server/tests/test_prompt_management_auth_parity.py`.
- Add `server/tests/test_prompt_management_domain_boundary.py`.
- Add `server/tests/test_prompt_management_router_facade.py`.
- Snapshot path, method, route function name, endpoint module, and auth
  dependencies for `/api/prompt-templates/*`.

## PR2: Domain Skeleton And Facade Register

- Add `server/app/domains/prompt_management/__init__.py`.
- Add `server/app/domains/prompt_management/README.md`.
- Document owned route, device-route non-ownership, compatibility facade, logger
  compatibility, and cleanup gates.
- Explicitly keep `/api/device/prompt-templates` in `device_operations`.

## PR3: Router Move With Compatibility Facade

- Copy `server/app/routers/prompt_templates.py` to
  `server/app/domains/prompt_management/prompt_templates_router.py`.
- Preserve logger name `app.routers.prompt_templates`.
- Replace legacy router file with a `sys.modules` compatibility facade.
- Keep `app.routers.prompt_templates` import-compatible with the new domain
  router module.

## PR4: Direct App Wiring

- Wire `app.main` to `app.domains.prompt_management.prompt_templates_router`.
- Keep the legacy facade for tests and old imports.
- Use an isolated index if `server/app/main.py` has unrelated WIP.

## Later Service Splits

- Split rewrite-stream orchestration and websocket notification helpers only
  after this route-boundary migration is stable.
- Prompt template service logic now lives in
  `app.domains.prompt_management.prompt_template_service`; keep
  `app.services.prompt_template_service` as a compatibility facade until
  direct-domain coverage replaces legacy imports.
- Keep legacy router monkeypatch paths such as
  `app.routers.prompt_templates.prompt_template_service.validate_rewrite_request`
  compatible until callers move to direct domain imports.

## Verification

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_prompt_management_auth_parity.py server/tests/test_prompt_management_domain_boundary.py server/tests/test_prompt_management_router_facade.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_prompt_templates_rewrite.py server/tests/test_device_operations_polling_reporting.py server/tests/test_device_operations_uploads.py -q
```

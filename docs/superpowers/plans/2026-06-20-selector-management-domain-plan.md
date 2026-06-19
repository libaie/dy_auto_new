# Selector Management Domain Implementation Plan

Date: 2026-06-20

## Goal

Create `app.domains.selector_management` and move admin selector route ownership
behind a compatibility-preserving domain module.

## PR1: Boundary And Route Snapshot

- Add `server/tests/test_selector_management_auth_parity.py`.
- Add `server/tests/test_selector_management_domain_boundary.py`.
- Add `server/tests/test_selector_management_router_facade.py`.
- Snapshot path, method, route function name, endpoint module, and auth
  dependencies for `/api/selectors/*`.

## PR2: Domain Skeleton And Facade Register

- Add `server/app/domains/selector_management/__init__.py`.
- Add `server/app/domains/selector_management/README.md`.
- Document owned route, device-route non-ownership, compatibility facade,
  websocket payloads, and cleanup gates.
- Explicitly keep `/api/device/selectors` in `device_operations`.
- Preserve websocket payloads `selectors_updated` and `selectors_changed`.

## PR3: Router Move With Compatibility Facade

- Copy `server/app/routers/selectors.py` to
  `server/app/domains/selector_management/selectors_router.py`.
- Replace legacy router file with a `sys.modules` compatibility facade.
- Keep `app.routers.selectors` import-compatible with the new domain router
  module.

## PR4: Direct App Wiring

- Wire `app.main` to `app.domains.selector_management.selectors_router`.
- Keep the legacy facade for tests and old imports.
- Use an isolated index if `server/app/main.py` has unrelated WIP.

## Later Splits

- Split selector CRUD use cases, template image handlers, and realtime event
  helpers only after route ownership is stable.
- Keep `selector_service` and `template_service` stable until a separate
  service-split plan is approved.

## Verification

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_selector_management_auth_parity.py server/tests/test_selector_management_domain_boundary.py server/tests/test_selector_management_router_facade.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_selectors_api.py server/tests/test_selector_service.py server/tests/test_device_operations_polling_reporting.py server/tests/test_device_operations_uploads.py -q
```

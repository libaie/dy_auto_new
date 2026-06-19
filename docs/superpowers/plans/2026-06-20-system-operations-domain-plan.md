# System Operations Domain Implementation Plan

Date: 2026-06-20

## Goal

Create `app.domains.system_operations` and move system health route ownership
behind a compatibility-preserving domain module.

## PR1: Boundary And Route Snapshot

- Add `server/tests/test_system_operations_auth_parity.py`.
- Add `server/tests/test_system_operations_domain_boundary.py`.
- Add `server/tests/test_system_operations_router_facade.py`.
- Snapshot path, method, route function name, endpoint module, and auth
  dependencies for `/api/system/*`.

## PR2: Domain Skeleton And Facade Register

- Add `server/app/domains/system_operations/__init__.py`.
- Add `server/app/domains/system_operations/README.md`.
- Document owned route, Root `/health` non-ownership, compatibility facade, and
  cleanup gates.
- Explicitly keep `/api/system/health` as the public operational readiness
  endpoint owned by this domain.

## PR3: Router Move With Compatibility Facade

- Copy `server/app/routers/system_health.py` to
  `server/app/domains/system_operations/system_health_router.py`.
- Replace legacy router file with a `sys.modules` compatibility facade.
- Keep `app.routers.system_health` import-compatible with the new domain router
  module for existing monkeypatch tests.

## PR4: Direct App Wiring

- Wire `app.main` to `app.domains.system_operations.system_health_router`.
- Keep the legacy facade for tests and old imports.
- Use an isolated index if `server/app/main.py` has unrelated WIP.

## Later Splits

- Split migration health and provider capability read models only after route
  ownership is stable.
- Keep provider services and ORM ownership unchanged in this slice.

## Verification

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_system_operations_auth_parity.py server/tests/test_system_operations_domain_boundary.py server/tests/test_system_operations_router_facade.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_system_health_page_contract.py -q
```

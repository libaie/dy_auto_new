# Image Generation Domain Implementation Plan

Date: 2026-06-20

## Goal

Create `app.domains.image_generation` and move image creation / image production
route ownership behind compatibility-preserving domain modules.

## PR1: Domain Boundary And Route Snapshot

- Add `server/tests/test_image_generation_auth_parity.py`.
- Add `server/tests/test_image_generation_domain_boundary.py`.
- Add `server/tests/test_image_generation_router_facade.py`.
- Snapshot paths, methods, route function names, endpoint module names, and auth
  dependencies for `/api/image-creation/*` and `/api/image-production/*`.

## PR2: Domain Skeleton And Documentation

- Add `server/app/domains/image_generation/__init__.py`.
- Add `server/app/domains/image_generation/README.md`.
- Document ownership, facade register, non-goals, and cleanup gates.

## PR3: Router Move With Compatibility Facades

- Copy `server/app/routers/image_creation.py` to
  `server/app/domains/image_generation/image_creation_router.py`.
- Copy `server/app/routers/image_production.py` to
  `server/app/domains/image_generation/image_production_router.py`.
- Replace legacy router files with `sys.modules` compatibility facades.
- Keep `app.routers.image_creation` and `app.routers.image_production`
  import-compatible with the new domain router modules.
- Keep `app.main` wiring unchanged for this PR.

## PR4: Direct App Wiring

- Inventory production imports of legacy image routers.
- Wire `app.main` to `app.domains.image_generation`.
- Keep the legacy facades until cleanup gates pass.
- Use an isolated index if `server/app/main.py` has unrelated WIP.

## PR5: Service Splits

- Split image creation and image production services only after route ownership is
  stable.
- Preserve service-level monkeypatch paths until facade cleanup is separately
  approved.

## Verification

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_generation_auth_parity.py server/tests/test_image_generation_domain_boundary.py server/tests/test_image_generation_router_facade.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_image_creation_api.py server/tests/test_image_creation_mocked_e2e.py server/tests/test_image_production_strategy_service.py server/tests/test_image_production_recommendation_api.py server/tests/test_image_ab_api.py server/tests/test_image_asset_bridge.py -q
```
